import os
import datetime
import logging
from get_nordpool import NordpoolGetter

# Setup logging
log_formatter = logging.Formatter('%(asctime)s:%(name)s:%(levelname)s:%(message)s')
logger = logging.getLogger(__name__)
logger.setLevel(logging.DEBUG)
# Console debug
stream_handler = logging.StreamHandler()
stream_handler.setFormatter(log_formatter)
logger.addHandler(stream_handler)

# File logger
file_handler = logging.FileHandler(os.path.join("logs", "script_file_manager.log"))
file_handler.setFormatter(log_formatter)
file_handler.setLevel(logging.DEBUG)
logger.addHandler(file_handler)


def test():
    test_loc = "C:\\py_related\\home_el_cntrl\\price_lists"
    # random_real_list = [random.uniform(0.00, 300.0) for _ in range(24)]
    # date = datetime.date.today() + datetime.timedelta(days=3)
    # list_of_prices, date_of_prices = NordpoolGetter.get_price_list()
    mngr = PriceFileManager(test_loc)
    #mngr.create_files_from_nordpool_price_list(random_real_list, date)
    # mngr.delete_old_incorrect_price_files()
    prices_today, prices_tomorrow = mngr.get_prices_today_tomorrow()
    print("Today")
    for hour, price in prices_today.items():
        print(f"{hour}\t{price}")
    print("Tomorrow")
    for hour, price in prices_tomorrow.items():
        print(f"{hour}\t{price}")


class PriceFileManager:
    PRICE_FILE_EXTENSION = ".prc"
    NORDPOOL_PRICE_OFSET_HOURS = 1

    def __init__(self, file_loc: str):
        self.file_loc = file_loc

    def get_prices_today_tomorrow(self) -> [dict, dict]:
        """
        today and tomorrow prices are the prices in the dictionary
        :return:
        """
        self.delete_old_incorrect_price_files()
        # For today just try to read the file, if it does not exist there will be an empty dict
        date_today = datetime.date.today()
        prices_today = self.read_prices_file_into_dict(self.create_date_file_path(date_today))
        logger.debug(f"Prices today {prices_today}")
        # For tomorrow it is possible to check if nordpool has the prices if there is no file yet or if the file has too
        # few values
        prices_tomorrow = self.get_prices_tomorrow_from_file()
        logger.debug(f"Prices tomorrow {prices_tomorrow}")
        return prices_today, prices_tomorrow

    def get_prices_tomorrow_from_file(self) -> dict:
        date_tomorrow = datetime.date.today() + datetime.timedelta(days=1)
        prices_tomorrow = self.read_prices_file_into_dict(self.create_date_file_path(date_tomorrow))
        if len(prices_tomorrow) < (24 - self.NORDPOOL_PRICE_OFSET_HOURS):
            logger.debug("Tomorrow prices not in files, attempting getting them from nordpool")
            # tomorrows file does not have all values, attempt to get them from nordpool
            # TODO: do this only if we can expect Nordpool to have the prices (use time)
            list_of_prices, date_of_prices = NordpoolGetter.get_tomorrow_price_list()
            if list_of_prices is not None and date_of_prices is not None:
                self.create_files_from_nordpool_price_list(list_of_prices, date_of_prices)
                prices_tomorrow = self.read_prices_file_into_dict(self.create_date_file_path(date_tomorrow))
        return prices_tomorrow

    def read_prices_file_into_dict(self, file_path) -> dict:
        """
        Read price file and create a dictionary of a days prices
        Key being  the hour price is for and the value being the price itself
        :param file_path:
        :return:
        """
        price_dict = {}
        if os.path.exists(file_path):
            with open(file_path, 'r') as file:
                for line in file:
                    # go through price file line by line
                    stripped_line = line.strip()
                    if stripped_line != "":
                        # line not empty
                        try:
                            hour_str, price_str = stripped_line.split(":")
                            hour = int(hour_str)
                            price = float(price_str)
                            price_dict[hour] = price
                        except ValueError:
                            logger.error(f"Price file not valid {file_path}")
                            return {}
        return price_dict

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

    def create_files_from_nordpool_price_list(self, price_list: list, date: datetime.date):
        """
        :param price_list: list of electricity prices
        :param date: date from Nordpool of the price list
        :return:
        Nordpool prices come ofset to local time, so price list must be devided between the date from nordpool and
        the next day
        """
        self.delete_old_incorrect_price_files()
        list_for_day_of = price_list[:(24 - self.NORDPOOL_PRICE_OFSET_HOURS)]
        list_for_next_day = price_list[-self.NORDPOOL_PRICE_OFSET_HOURS:]
        date_for_next_day = date + datetime.timedelta(days=1)
        today_file_path = self.create_date_file_path(date)
        next_day_file_path = self.create_date_file_path(date_for_next_day)
        # Todays file can have values from the previous day's nordpool prices
        self.check_prices_file(today_file_path, self.NORDPOOL_PRICE_OFSET_HOURS)
        self.write_prices_file(list_for_day_of, today_file_path, self.NORDPOOL_PRICE_OFSET_HOURS)
        # The next days file can not exist
        self.delete_file(next_day_file_path)
        self.write_prices_file(list_for_next_day, next_day_file_path, 0)

    def write_prices_file(self, price_list: list, file_path: str, start_hour: int):
        """
        :param price_list: price list to write
        :param file_path: file path
        :param start_hour: hour form which the prices start
        :return:
        """
        hour = start_hour
        try:
            with open(file_path, "a+") as file:
                for price in price_list:
                    file.write(f"{hour}:{price}\n")
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
                            # not used but check if can be cast to float
                            price = float(price_str)
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
