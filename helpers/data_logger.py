import logging
import os
from enum import Enum, auto
from threading import Timer
import queue
from time import sleep
import threading
from datetime import datetime, timedelta, timezone, time
from typing import Callable, Dict, Tuple
from helpers.grafana_cloud_data_storage import GrafanaCloud
from helpers.observer_pattern import Observer
from helpers.price_file_manager import PriceFileManager
from devices.device import Device
from devices.deviceTypes import DeviceType
from helpers.sensor import Sensor
from helpers.database_mngr import DbMngr
import secrets
import settings

# Setup logging
log_formatter = logging.Formatter('%(asctime)s:%(name)s:%(levelname)s:%(message)s')
logger = logging.getLogger(__name__)
logger.setLevel(settings.BASE_LOG_LEVEL)
# Console debug
stream_handler = logging.StreamHandler()
stream_handler.setFormatter(log_formatter)
stream_handler.setLevel(settings.CONSOLE_LOG_LEVEL)
logger.addHandler(stream_handler)
# File logger
file_handler = logging.FileHandler(os.path.join("../logs", "data_logger.log"))
file_handler.setFormatter(log_formatter)
file_handler.setLevel(settings.FILE_LOG_LEVEL)
logger.addHandler(file_handler)


def main_fc():
    pass


class DataLogger(Observer):
    """
    Class for logging historical data of home automation program
    Periodical and on data change logging
    """
    ON_TIME_LOG_CHECK_INTERVAL_S = 0.5

    class LogType(Enum):
        PRICE_LOG = auto()
        PRICE_LOG_GRAFANA = auto()
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
        # To periodically execute logging
        self.periodical_log_thread = Timer(self.periodical_log_interval_s, self.periodical_log)
        self.periodical_log_thread.start()
        # To execute logging on time - for example exact hour, exact minute etc
        self.on_time_log_thread = Timer(self.ON_TIME_LOG_CHECK_INTERVAL_S, self.on_time_log)
        self.on_time_log_thread.start()
        self.hour_old = datetime.now().hour
        # Thread that will handle putting data in storage locations
        self.data_storage_thread = threading.Thread(target=self.data_storage_thread_method, args=(self.data_queue,))
        self.data_storage_thread.start()

    def on_time_log(self):
        """
        Executes often for logging of data on exact times - on hour, on minute etc.
        """
        self.on_new_hour_log()
        self.on_time_log_thread = Timer(self.ON_TIME_LOG_CHECK_INTERVAL_S, self.on_time_log)
        self.on_time_log_thread.start()

    def periodical_log(self):
        self.periodical_device_log()
        self.periodical_sensor_log()
        self.periodical_log_thread = Timer(self.periodical_log_interval_s, self.periodical_log)
        self.periodical_log_thread.start()

    def on_new_hour_log(self):
        if self.hour_old != datetime.now().hour:
            self.hour_old = datetime.now().hour
            self.log_electricity_price_hourly(self.hour_old)

    def log_electricity_price_hourly(self, current_hour: int):
        """
        Needed because Grafana does not allow inserting of future prices
        :param current_hour:
        :return:
        """
        # TODO: delete info log statements after test
        logger.info("Logging price hourly")
        prices_today, prices_tomorrow = self.get_prices_method()
        try:
            current_price = prices_today[current_hour]
        except KeyError:
            logger.info("No price for hour")
            return
        # Get the timestamp of exact hour
        # Get today's date
        datetime_now = datetime.now()
        datetime_now = datetime_now.replace(minute=0, second=0, microsecond=0)
        # Combine with a specific time (16:00:00)
        # Convert to UTC
        timestamp = datetime_now.astimezone(timezone.utc)
        logger.info(f"current_price {current_price}, timestamp {timestamp}")
        self.data_queue.put({"log_type": self.LogType.PRICE_LOG_GRAFANA, "data": (current_price, timestamp)})



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
        self.on_time_log_thread.cancel()
        # Stop database thread
        self.data_queue.put({"log_type": self.LogType.STOP_LOG})
        logger.info("Waiting for data handle thread to stop")
        self.data_storage_thread.join()
        logger.info("Data handling thread stopped")

    def data_storage_thread_method(self, data_queue):
        """
        Worker running on seperate thread. handles data storage in database.
        :param data_queue: queue for data exchange with main thread
        :return:
        """
        # Store in sqlite database
        self.db_mngr = DbMngr()
        # Store in grafana cloud
        self.grafana_cloud = GrafanaCloud(endpoint=secrets.GRAFANA_ENDPOINT,
                                 username=secrets.GRAFANA_USERNAME,
                                 password=secrets.GRAFANA_API_TOKEN,
                                 source_tag="home_data")
        # List of all storage locations
        self.storage_list = (self.db_mngr, self.grafana_cloud)
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
                elif data["log_type"] == self.LogType.PRICE_LOG_GRAFANA:
                    # New hour, log price to Grafana
                    current_price, timestamp = data["data"]
                    self.grafana_cloud.insert_current_hour_price(current_price,timestamp)
                elif data["log_type"] == self.LogType.SENSOR_LOG:
                    sensor_list = data["data"]
                    for storage in self.storage_list:
                        storage.insert_sensor_list_data(sensor_list)
                elif data["log_type"] == self.LogType.STOP_LOG:
                    # Stopping data base thread
                    run = False
                else:
                    log_type = data["log_type"]
                    logger.error(f"Unknown value in queue {log_type}")
            sleep(0.5)
        # close sqlite database
        self.db_mngr.stop()

    def log_shelly_data(self, dev: Device):
        # Different shelly devices have different data available, but all data stored in single table. Fill missing data
        # with fake value
        if dev.device_type == DeviceType.SHELLY_PLUG:
            for storage in self.storage_list:
                storage.insert_shelly_data(dev.name, dev.state_off_on,
                                                   dev.get_status(), dev.power, dev.energy, )
        elif dev.device_type == DeviceType.SHELLY_PLUS:
            for storage in self.storage_list:
                storage.insert_shelly_data(dev.name, dev.state_off_on,
                                                   dev.get_status())
        elif dev.device_type == DeviceType.SHELLY_PLUS_PM:
            for storage in self.storage_list:
                storage.insert_shelly_data(dev.name, dev.state_off_on,
                                                   dev.get_status(), dev.power, dev.energy,
                                                   dev.voltage, dev.current)
        elif dev.device_type == DeviceType.URL_CONTROLLED_SHELLY_PLUG:
            for storage in self.storage_list:
                storage.insert_shelly_data(dev.name, dev.state_off_on,
                                                   dev.get_status())


if __name__ == '__main__':
    main_fc()
