from datetime import date
import os
import logging
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
file_handler = logging.FileHandler(os.path.join("../logs", "device_setup.log"))
file_handler.setFormatter(log_formatter)
file_handler.setLevel(settings.FILE_LOG_LEVEL)
logger.addHandler(file_handler)



class DayPrices:
    """
    List of prices for certain date
    """
    def __init__(self, price_date: date):
        self.date = price_date            # <-- Holds the date of prices
        self.hours = [HourPrice(hour) for hour in range(24)]

    def set_price(self, hour: int, quarter: int, price: float):
        self.hours[hour].set_price(quarter, price)

    def get_price(self, hour: int, quarter: int) -> float:
        return self.hours[hour].get_price(quarter)

    def get_price_by_period_number(self, period_nr:int) -> float:
        return self.hours[period_nr//4].get_price(period_nr%4)

    def load_from_flat_list(self, flat_prices: list[float]):
        """
        Populate all hour/quarter prices from a list of 96 values.
        Index = hour * 4 + quarter.
        """
        if len(flat_prices) != 96:
            raise ValueError("Expected 96 price values (24 hours * 4 quarters).")

        for index, price in enumerate(flat_prices):
            hour = index // 4
            quarter = index % 4
            self.set_price(hour, quarter, price)

    def __repr__(self):
        return f"Prices for {self.date}:\n" + "\n".join(str(h) for h in self.hours)

class HourPrice:
    """
    Prices in hour for each quarter
    """
    def __init__(self, hour: int):
        self.hour = hour
        # 4 quarters → Index 0 = 00-15, 1 = 15-30, etc.
        self.quarters = [0.0, 0.0, 0.0, 0.0]

    def set_price(self, quarter: int, price: float):
        """quarter: 0–3"""
        self.quarters[quarter] = price

    def get_price(self, quarter: int) -> float:
        return self.quarters[quarter]

    def __repr__(self):
        return f"Hour {self.hour}: {self.quarters}"