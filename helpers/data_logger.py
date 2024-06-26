import logging
import os
from enum import Enum, auto
from threading import Timer
import queue
import time
import threading
from datetime import datetime, timedelta
from typing import Callable, Dict, Tuple
from helpers.observer_pattern import Observer
from helpers.price_file_manager import PriceFileManager
from devices.device import Device
from devices.deviceTypes import DeviceType
from helpers.sensor import Sensor
from helpers.database_mngr import DbMngr

# Setup logging
log_formatter = logging.Formatter('%(asctime)s:%(name)s:%(levelname)s:%(message)s')
logger = logging.getLogger(__name__)
logger.setLevel(logging.INFO)
# Console debug
stream_handler = logging.StreamHandler()
stream_handler.setFormatter(log_formatter)
stream_handler.setLevel(logging.INFO)
logger.addHandler(stream_handler)
# File logger
file_handler = logging.FileHandler(os.path.join("../logs", "data_logger.log"))
file_handler.setFormatter(log_formatter)
file_handler.setLevel(logging.INFO)
logger.addHandler(file_handler)


def main_fc():
    pass


class DataLogger(Observer):
    """
    Class for logging historical data of home automation program
    Periodical and on data change logging
    """

    class LogType(Enum):
        PRICE_LOG = auto()
        SHELLY_LOG = auto()
        SENSOR_LOG = auto()
        STOP_LOG = auto()

    def __init__(self, get_prices_method: Callable[[], Tuple[Dict, Dict]], device_list: list[Device],
                 sensor_list: list[Sensor], periodical_log_interval_s: float = 3600.0):
        """
        :param get_prices_method: Method to call for this class to get the prices of electricity
        :param device_list: list of devices whose data is to be logged
        :param sensor_list: list of sensors to be logged
        :param periodical_log_interval_s: how often to periodically log device data
        """
        self.periodical_log_interval_s = periodical_log_interval_s
        self.get_prices_method = get_prices_method
        self.device_list = device_list
        self.sensor_list = sensor_list
        self.data_queue = queue.Queue()
        self.periodical_log_thread = Timer(self.periodical_log_interval_s, self.periodical_log)
        self.periodical_log_thread.start()
        self.db_thread = threading.Thread(target=self.db_mngr_thread_method, args=(self.data_queue,))
        self.db_thread.start()

    def periodical_log(self):
        self.periodical_device_log()
        self.periodical_sensor_log()
        self.periodical_log_thread = Timer(self.periodical_log_interval_s, self.periodical_log)
        self.periodical_log_thread.start()

    def periodical_sensor_log(self):
        self.data_queue.put({"log_type": self.LogType.SENSOR_LOG, "data": self.sensor_list})

    def periodical_device_log(self):
        # log device data
        logger.debug("periodical_device_log")
        # Execute this function in regular intervals
        for dev in self.device_list:
            if dev.get_cmd_given():
                logger.debug(f"Device {dev.name} is on, executing periodical log")
                self.log_device_data(dev)

    def handle_subject_event(self, event_type: str, *args, **kwargs):
        # Handle events initiated by devices this class is listening to
        if event_type == PriceFileManager.event_name_prices_changed:
            self.get_and_store_prices()
        elif event_type == Device.event_name_actual_state_changed:
            device_type = kwargs.get('device_type')
            device_name = kwargs.get('device_name')
            if not device_type or not device_name:
                logger.error("Device status changed event does not have all required event data")
                for key, value in kwargs.items():
                    logger.error(f"{key}: {value}")
                return
            self.handle_device_event(device_name)

    def handle_device_event(self, device_name: str):
        # Log data for different devices
        logger.debug(f"Handling device event name {device_name}")
        dev_to_log = self.get_device_by_name(device_name)
        if not dev_to_log:
            logger.error("Device with specific name not in device list")
            return
        self.log_device_data(dev_to_log)

    def log_device_data(self, dev: Device):
        device_type = dev.device_type
        if device_type == DeviceType.SHELLY_PLUG or \
                device_type == DeviceType.SHELLY_PLUS or \
                device_type == DeviceType.URL_CONTROLLED_SHELLY_PLUG or \
                device_type == DeviceType.SHELLY_PLUS_PM:
            self.data_queue.put({"log_type": self.LogType.SHELLY_LOG, "data": dev})
        else:
            logger.warning(f"Device type not recognised {device_type}")

    def get_device_by_name(self, device_name):
        # get device object by name
        for dev in self.device_list:
            if dev.name == device_name:
                return dev
        return None

    def get_and_store_prices(self):
        # get prices of today and tomorrow and insert them in the database
        today_date = datetime.today().date()
        tomorrows_date = today_date + timedelta(days=1)
        prices_today, prices_tomorrow = self.get_prices_method()
        self.data_queue.put({"log_type": self.LogType.PRICE_LOG, "data": (prices_today, today_date)})
        self.data_queue.put({"log_type": self.LogType.PRICE_LOG, "data": (prices_tomorrow, tomorrows_date)})

    def stop(self):
        logger.info("Stopping data logger")
        # Stop periodicall logging
        self.periodical_log_thread.cancel()
        # Stop database thread
        self.data_queue.put({"log_type": self.LogType.STOP_LOG})
        logger.info("Join start")
        self.db_thread.join()
        logger.info("Join end")

    def db_mngr_thread_method(self, data_queue):
        """
        Worker running on seperate thread. handles data storage in database.
        :param data_queue: queue for data exchange with main thread
        :return:
        """
        self.db_mngr = DbMngr()
        run = True
        while run:
            while not data_queue.empty():
                data = self.data_queue.get()
                if data["log_type"] == self.LogType.SHELLY_LOG:
                    # receive data shelly plug data
                    self.log_shelly_data(data["data"])
                elif data["log_type"] == self.LogType.PRICE_LOG:
                    # Received price data
                    prices_dic, price_date = data["data"]
                    self.db_mngr.insert_prices(prices_dic, price_date)
                elif data["log_type"] == self.LogType.SENSOR_LOG:
                    sensor_list = data["data"]
                    self.db_mngr.insert_sensor_list_data(sensor_list)
                elif data["log_type"] == self.LogType.STOP_LOG:
                    # Stopping data base thread
                    run = False
            time.sleep(0.5)
        # close db manager
        self.db_mngr.stop()

    def log_shelly_data(self, dev: Device):
        # Different shelly devices have different data available, but all data stored in single table. Fill missing data
        # with fake value
        if dev.device_type == DeviceType.SHELLY_PLUG:
            self.db_mngr.insert_shelly_data_w_type(dev.name, dev.state_off_on,
                                                   dev.get_status(), dev.power, dev.energy, )
        elif dev.device_type == DeviceType.SHELLY_PLUS:
            self.db_mngr.insert_shelly_data_w_type(dev.name, dev.state_off_on,
                                                   dev.get_status())
        elif dev.device_type == DeviceType.SHELLY_PLUS_PM:
            self.db_mngr.insert_shelly_data_w_type(dev.name, dev.state_off_on,
                                                   dev.get_status(), dev.power, dev.energy,
                                                   dev.voltage, dev.current)
        elif dev.device_type == DeviceType.URL_CONTROLLED_SHELLY_PLUG:
            self.db_mngr.insert_shelly_data_w_type(dev.name, dev.state_off_on,
                                                   dev.get_status())


if __name__ == '__main__':
    main_fc()
