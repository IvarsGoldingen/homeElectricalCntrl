import logging
import os
from datetime import datetime, timedelta
from typing import Callable, Dict, Tuple
from observer_pattern import Observer
from price_file_manager import PriceFileManager
from devices.device import Device
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

    def __init__(self, get_prices_method: Callable[[], Tuple[Dict, Dict]]):
        self.get_prices_method = get_prices_method
        self.db_mngr = DbMngr()

    def handle_subject_event(self, event_type: str):
        logger.debug(f"Received event {event_type}")
        if event_type == PriceFileManager.event_name_prices_changed:
            self.get_and_store_prices()
        elif event_type == Device.event_name_status_changed:
            self.get_and_store_device_data()

    def get_and_store_device_data(self):
        #TODO: To implement this refactor observer patte so that it is possible to detect which device
        # triggered an event as well as know the device type
        pass

    def get_and_store_prices(self):
        # get prices of today and tomorrow and insert them in the database
        today_date = datetime.today().date()
        tomorrows_date = today_date + timedelta(days=1)
        prices_today, prices_tomorrow = self.get_prices_method()
        self.db_mngr.insert_prices(prices_today, today_date)
        self.db_mngr.insert_prices(prices_tomorrow, tomorrows_date)



if __name__ == '__main__':
    main_fc()
