import os
import datetime
import logging
import time
import random
import re
from xmlrpc.client import DateTime

from helpers.get_nordpool import NordpoolGetter
from helpers.observer_pattern import Subject
import settings
from price_objects import DayPrices, HourPrice

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
file_handler = logging.FileHandler(os.path.join("../logs", "script_file_manager.log"))
file_handler.setFormatter(log_formatter)
file_handler.setLevel(settings.FILE_LOG_LEVEL)
logger.addHandler(file_handler)


def test():
    test_loc = "C:\\py_related\\home_el_cntrl\\price_lists"
    day_prices = DayPrices(datetime.date.today() + datetime.timedelta(days=1))
    random_real_list = [random.uniform(0.00, 300.0) for _ in range(96)]
    day_prices.load_from_flat_list(random_real_list)
    mngr = PriceFileManager(test_loc)
    mngr.create_files_from_nordpool_price_list(day_prices)
    # list_of_prices, date_of_prices = NordpoolGetter.get_price_list()
    # mngr.create_files_from_nordpool_price_list(random_real_list, date)
    # mngr.delete_old_incorrect_price_files()
    # prices_today, prices_tomorrow = mngr.get_prices_today_tomorrow()


class PriceFileManager(Subject):
    """
    TODO:
    Possibly hold all available prices in global variables since the prices may be accessed often
    """
    PRICE_FILE_EXTENSION = ".prc"
    NORDPOOL_PRICE_OFSET_HOURS = 1
    # Time at which tomorrow's NP prices expected to be available
    TOMORROW_AVAILABLE_EARLIEST_HOUR = 15
    TOMORROW_AVAILABLE_EARLIEST_MINUTE = 55
    # To limit how often np gets polled
    MIN_NP_POLL_TIME_SEC = 900  # 900 = 15 min
    # event names as this class extends from subject
    # new prices, either from file or np. Also can mean new day.
    event_name_prices_changed = "prices_changed"
    # new prices from np available
    event_name_new_prices = "new_prices_available"

    def __init__(self, file_loc: str):
        super().__init__()
        self.file_loc = file_loc
        self.datetime_now = None
        self.tomorrow_prices_available = False
        # For limitting np polls
        self.time_of_last_np_poll = 0

    def loop(self):
        """
        Call periodically to automatically retrieve tomorrow prices from Nordpool
        To move tomorrow's prices in today at midnight
        :return:
        """
        self.check_if_new_day()
        self.check_for_tomorrows_prices()

    def check_if_new_day(self):
        """
        On new day move tomorrows schedule to today, and clear it
        """
        actual_today = datetime.date.today()
        if actual_today == self.datetime_now:
            # date has not changed
            return
        if self.datetime_now:
            # Check if this is none, this is the first cycle for the application
            # If this exists and not equal to actual today, its a new day
            logger.debug("New day, tomorrows prices cannot be available")
            # Tomorrows prices can not be available since new day just now
            # Check if datetime_now is not None, that would mean first cycle
            self.tomorrow_prices_available = False
        # new day
        self.delete_old_incorrect_price_files()
        self.datetime_now = actual_today
        self.notify_observers(self.event_name_prices_changed)

    def get_prices_today_tomorrow(self) -> [dict, dict]:
        """
        today and tomorrow prices are the prices in the dictionary. Key is hour, value is price for that hour
        :return:
        """
        # For today just try to read the file, if it does not exist there will be an empty dict
        date_today = datetime.date.today()
        prices_today = self.get_prices_from_file(self.create_date_file_path(date_today), date_today)
        logger.debug(f"Getting prices:")
        logger.debug(f"Prices today {prices_today}")
        # For tomorrow it is possible to check if nordpool has the prices if there is no file yet or if the file has too
        # few values
        prices_tomorrow = self.get_prices_tomorrow_from_file()
        logger.debug(f"Prices tomorrow {prices_tomorrow}")
        return prices_today, prices_tomorrow

    def get_prices_tomorrow_from_file(self) -> DayPrices:
        date_tomorrow = datetime.date.today() + datetime.timedelta(days=1)
        prices_tomorrow = self.get_prices_from_file(self.create_date_file_path(date_tomorrow), date_tomorrow)
        return prices_tomorrow

    def check_for_tomorrows_prices(self):
        if self.tomorrow_prices_available:
            # tomorrow's prices available, no need to do anything
            return
        if not self.check_tomorrow_could_be_available_time():
            # no prices available but also too early to look for
            return
        if self.check_if_tomorrows_prices_in_file():
            # Tomorrow's prices availabel in file
            logger.debug("Tomorrow's prices available in file")
            self.notify_observers(self.event_name_prices_changed)
            return
        if self.get_prices_tomorrow_from_np():
            logger.info("Got prices from Nordpool")
            self.notify_observers(self.event_name_prices_changed)
            self.notify_observers(self.event_name_new_prices)
            return
        logger.debug("Did NOT get prices from Nordpool")

    def check_tomorrow_could_be_available_time(self):
        # Check if late enough in the day for the tommorrow prices to be available
        time_h = datetime.datetime.now().hour
        time_min = datetime.datetime.now().minute
        if time_h > self.TOMORROW_AVAILABLE_EARLIEST_HOUR:
            return True
        if time_h == self.TOMORROW_AVAILABLE_EARLIEST_HOUR and \
                time_min >= self.TOMORROW_AVAILABLE_EARLIEST_MINUTE:
            return True
        return False

    def check_if_tomorrows_prices_in_file(self):
        prices_tomorrow = self.get_prices_tomorrow_from_file()
        if len(prices_tomorrow.hours) < (24 - self.NORDPOOL_PRICE_OFSET_HOURS):
            self.tomorrow_prices_available = False
            return False
        # Tomorrows prices in file
        self.tomorrow_prices_available = True
        return True

    def get_prices_tomorrow_from_np(self) -> DayPrices:
        if not self.check_new_np_req_allowed():
            # New NP req not allowed
            return None
        self.time_of_last_np_poll = time.perf_counter()
        tomorrow_prices = NordpoolGetter.get_tomorrow_price_list()
        if tomorrow_prices is None:
            logger.debug("Failed to get prices from nordpool")
            return None
        else:
            logger.debug("Succesfully got prices from nordpool")
            self.create_files_from_nordpool_price_list(tomorrow_prices)
            self.tomorrow_prices_available = True
            return tomorrow_prices

    def check_new_np_req_allowed(self):
        time_now = time.perf_counter()
        time_since_last_poll = time_now - self.time_of_last_np_poll
        if time_since_last_poll >= self.MIN_NP_POLL_TIME_SEC:
            logger.debug("New NP poll allowed")
            return True
        logger.debug("New NP poll NOT allowed")
        return False

    def get_prices_from_file(self, file_path: str, date: datetime.date) -> DayPrices:
        """
        Read price file and create a DayPrices object
        :param file_path:
        :return:
        """
        prices = DayPrices(date)
        if os.path.exists(file_path):
            with open(file_path, 'r') as file:
                for line in file:
                    line = line.strip()
                    # Match "13: [10.5, 10.8, 11.0, 10.9]"
                    match = re.match(r"(\d+):\s*\[(.*?)]", line)
                    if match:
                        hour_str, quarter_values = match.groups()
                        current_hour = int(hour_str)
                        values = [float(x.strip()) for x in quarter_values.split(",")]
                        # Ensure valid structure
                        if len(values) != 4:
                            raise ValueError(f"Expected 4 quarter values, got {len(values)} in line: {line}")
                        # Assign prices to corresponding hour slot
                        if 0 <= current_hour < 24:
                            for q, v in enumerate(values):
                                prices.set_price(current_hour, q, v)
                return prices
        return None

    def delete_old_incorrect_price_files(self):
        """
        Only price lists of today, tomorrow, and day after tomorrow saved
        :return:
        """
        files = os.listdir(self.file_loc)
        valid_file_names = self.get_list_of_valid_price_file_names()
        for file in files:
            # loop throug files in price file folder
            file_path = os.path.join(self.file_loc, file)
            if os.path.isfile(file_path):
                # file is a file and not a folder
                file_extension = os.path.splitext(file)[1]
                if file_extension == self.PRICE_FILE_EXTENSION:
                    # file is a prices file
                    delete = True
                    for valid_name in valid_file_names:
                        if file == valid_name:
                            # file is valid
                            delete = False
                    if delete:
                        # the file name was not one of the valid ones, delete
                        os.remove(file_path)

    def get_list_of_valid_price_file_paths(self):
        """
        Get file paths of today's, tomorrow's and day after tomorrow's price files
        :return:
        """
        # Get dates
        today = datetime.date.today()
        tomorrow = today + datetime.timedelta(days=1)
        day_after_tomorrow = today + datetime.timedelta(days=2)
        today_file_path = self.create_date_file_path(tomorrow)
        tomorrow_file_path = self.create_date_file_path(today)
        day_after_tomorrow_file_path = self.create_date_file_path(day_after_tomorrow)
        return [today_file_path, tomorrow_file_path, day_after_tomorrow_file_path]

    def get_list_of_valid_price_file_names(self):
        """
        Get file names of today's, tomorrow's and day after tomorrow's price files
        :return:
        """
        # Get dates
        today = datetime.date.today()
        tomorrow = today + datetime.timedelta(days=1)
        day_after_tomorrow = today + datetime.timedelta(days=2)
        today_file_path = self.create_date_file_name(today)
        tomorrow_file_path = self.create_date_file_name(tomorrow)
        day_after_tomorrow_file_path = self.create_date_file_name(day_after_tomorrow)
        return [today_file_path, tomorrow_file_path, day_after_tomorrow_file_path]

    def create_files_from_nordpool_price_list(self, prices: DayPrices):
        """
        :param prices from Nordpool
        Nordpool prices come ofset to local time, so price list must be devided between the date from nordpool and
        the next day
        """
        self.delete_old_incorrect_price_files()
        # Nordpool gives prices with ofset from local time.
        # In Latvia 23 hour for next day received and 1 hour for the day after
        list_for_day_of = prices.hours[:(24 - self.NORDPOOL_PRICE_OFSET_HOURS)]
        list_for_next_day = prices.hours[-self.NORDPOOL_PRICE_OFSET_HOURS:]
        date_for_next_day = prices.date + datetime.timedelta(days=1)
        today_file_path = self.create_date_file_path(prices.date)
        next_day_file_path = self.create_date_file_path(date_for_next_day)
        # Todays file can have values from the previous day's nordpool prices
        self.check_prices_file(today_file_path, self.NORDPOOL_PRICE_OFSET_HOURS)
        self.write_prices_file(list_for_day_of, today_file_path, self.NORDPOOL_PRICE_OFSET_HOURS)
        # The next days file can not exist
        self.delete_file(next_day_file_path)
        self.write_prices_file(list_for_next_day, next_day_file_path, 0)

    def write_prices_file(self, price_list: list[HourPrice], file_path: str, start_hour: int):
        """
        :param price_list: price list to write
        :param file_path: file path
        :param start_hour: hour form which the prices start
        :return:
        """
        hour = start_hour
        try:
            with open(file_path, "a+") as file:
                for hour_prices in price_list:
                    # Format: 13 -> [10.5, 11.0, 9.8, 10.1]
                    formatted_quarters = ", ".join(str(p) for p in hour_prices.quarters)
                    file.write(f"{hour}:{formatted_quarters}\n")
                    hour += 1
        except FileNotFoundError:
            logger.error("No folder to write price list")

    def delete_file(self, file_path):
        if os.path.exists(file_path):
            os.remove(file_path)

    def check_prices_file(self, file_path: str, max_nr_of_prices_in_file: int) -> int:
        """
        Check prices file, delete if it is not valid
        :param max_nr_of_prices_in_file: max number of expected prices in price file
        :param file_path: path to price file
        :return: number of prices in file.
        """
        nr_of_prices = 0
        if os.path.exists(file_path):
            delete_file = True
            with open(file_path, 'r') as file:
                expected_hour = 0
                for line in file:
                    # go through price file line by line
                    stripped_line = line.strip()
                    if stripped_line != "":
                        # line not empty
                        try:
                            hour_str, price_str = stripped_line.split(":")
                            hour = int(hour_str)
                            if hour == expected_hour:
                                nr_of_prices += 1
                                if nr_of_prices > max_nr_of_prices_in_file:
                                    break
                                expected_hour += 1
                            else:
                                # Unexpected hour in file
                                break
                        except ValueError:
                            logger.error(f"Price file not valid {file_path}")
                            break
                else:
                    logger.debug(f"File {file_path} is valid")
                    # break was not executed, line valid
                    delete_file = False
            if delete_file:
                nr_of_prices = -1
                self.delete_file(file_path)
        # file does not exist return 0
        return nr_of_prices

    def create_date_file_name(self, date: datetime.date):
        return "{:04d}_{:02d}_{:02d}".format(date.year, date.month, date.day) + self.PRICE_FILE_EXTENSION

    def create_date_file_path(self, date: datetime.date):
        file_name = self.create_date_file_name(date)
        return os.path.join(self.file_loc, file_name)


if __name__ == '__main__':
    test()
