import datetime
from datetime import date
import math
import logging
import requests
from nordpool import elspot, elbas
from typing import List, Dict, Tuple
import os
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
file_handler = logging.FileHandler(os.path.join("../logs", "nordpool.log"))
file_handler.setFormatter(log_formatter)
file_handler.setLevel(settings.FILE_LOG_LEVEL)
logger.addHandler(file_handler)


def test():
    print(NordpoolGetter.get_tomorrow_price_list())


class NordpoolGetter:

    # Get prices from nordpool
    @staticmethod
    def get_tomorrow_price_list() -> Tuple[List[float], datetime.date]:
        """
        :return: list of floats representing price values, and date and time for those prices
        """
        logger.info("Attempting to get data from Nordpool")
        prices_spot = elspot.Prices()
        success = False
        try:
            prices_dict = prices_spot.hourly(areas=['LV'])
            if prices_dict is not None:
                success = True
            else:
                logger.exception("Prices dictionary empty")
        except requests.exceptions.ReadTimeout:
            logger.exception("Request timed out. The server took too long to respond.")
        except requests.exceptions.JSONDecodeError:
            logger.exception("Nordpool: no data yet available")
        except requests.exceptions.ConnectionError:
            logger.exception("Failed to connect to Nordpool")
        except Exception as e:
            logger.exception("Unknown exception when trying to connect to Nordpool")
        if not success:
            return None, None
        hourly_price_list = prices_dict.get("areas").get("LV").get("values")
        logger.debug(f'{len(hourly_price_list)} items in hourly prices list')
        list_of_prices = []
        for hourly_price_dict in hourly_price_list:
            hour_rate = float(hourly_price_dict.get("value"))
            if math.isinf(hour_rate):
                logger.error("Price list not yet available")
                # If prices not yet available inf returned
                return None, None
            list_of_prices.append(hour_rate)
        date_time_of_prices = prices_dict.get("end")
        date_of_prices = date(date_time_of_prices.year, date_time_of_prices.month, date_time_of_prices.day)
        logger.info(f'Read data from Nordpool for {date_of_prices}:')
        logger.info(f'{list_of_prices}')
        return list_of_prices, date_of_prices


if __name__ == '__main__':
    test()
