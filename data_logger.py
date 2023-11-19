import logging
import os
from datetime import datetime, timedelta
from typing import Callable, Dict, Tuple
from observer_pattern import Observer
from price_file_manager import PriceFileManager
from devices.device import Device
from devices.shellyPlugMqtt import ShellyPlug
from devices.deviceTypes import DeviceType
from database_mngr import DbMngr

# Setup logging
log_formatter = logging.Formatter('%(asctime)s:%(name)s:%(levelname)s:%(message)s')
logger = logging.getLogger(__name__)
logger.setLevel(logging.DEBUG)
# Console debug
stream_handler = logging.StreamHandler()
stream_handler.setFormatter(log_formatter)
stream_handler.setLevel(logging.DEBUG)
logger.addHandler(stream_handler)
# File logger
file_handler = logging.FileHandler(os.path.join("logs", "data_logger.log"))
file_handler.setFormatter(log_formatter)
file_handler.setLevel(logging.DEBUG)
logger.addHandler(file_handler)


def main_fc():
    pass


class DataLogger(Observer):
    """
    Class for logging historical data of home automation program
    Periodical and on data change logging
    """

    def __init__(self, get_prices_method: Callable[[], Tuple[Dict, Dict]], device_list: list[Device]):
        self.get_prices_method = get_prices_method
        self.db_mngr = DbMngr()
        self.device_list = device_list

    def handle_subject_event(self, event_type: str, *args, **kwargs):
        logger.debug(f"Received event {event_type}")
        if event_type == PriceFileManager.event_name_prices_changed:
            self.get_and_store_prices()
        elif event_type == Device.event_name_status_changed:
            device_type = kwargs.get('device_type')
            device_name = kwargs.get('device_name')
            if not device_type or not device_name:
                logger.error("Device status changed event does not have all required event data")
                for key, value in kwargs.items():
                    logger.error(f"{key}: {value}")
                return
            self.handle_device_event(device_type, device_name)

    def handle_device_event(self, device_type: DeviceType, device_name: str):
        logger.debug(f"Handling device event type {device_type}, name {device_name}")
        dev_to_log = self.get_device_by_name(device_name)
        if not dev_to_log:
            logger.error("Device with specific name not in device list")
            return
        if device_type == DeviceType.SHELLY_PLUG:
            self.log_shelly_data(dev_to_log)
        else:
            logger.error(f"Device type not recognised {device_type}")

    def log_shelly_data(self, dev: ShellyPlug):
        logger.debug("Logging shelly data")
        self.db_mngr.insert_shelly_data(dev.name, dev.state_off_on, dev.power,
                                        dev.get_status(), dev.energy)

    def get_device_by_name(self, device_name):
        for dev in self.device_list:
            if dev.name == device_name:
                return dev
        return None

    def get_and_store_prices(self):
        # get prices of today and tomorrow and insert them in the database
        today_date = datetime.today().date()
        tomorrows_date = today_date + timedelta(days=1)
        prices_today, prices_tomorrow = self.get_prices_method()
        self.db_mngr.insert_prices(prices_today, today_date)
        self.db_mngr.insert_prices(prices_tomorrow, tomorrows_date)



if __name__ == '__main__':
    main_fc()
