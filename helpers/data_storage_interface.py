from abc import ABC, abstractmethod
from datetime import datetime

from devices.deviceTypes import DeviceType
from helpers.sensor import Sensor
import global_var

class DataStoreInterface(ABC):
    """Abstract base class for logging data."""

    NO_DATA_VALUE = global_var.NO_DATA_VALUE

    @abstractmethod
    def insert_shelly_data(self, name: str, off_on: bool, status: int, power: float = NO_DATA_VALUE,
                                  energy: float = NO_DATA_VALUE, voltage: float = NO_DATA_VALUE,
                                  current: float = NO_DATA_VALUE):
        pass

    @abstractmethod
    def insert_sensor_list_data(self, sensor_list: list[Sensor]):
        pass

    @abstractmethod
    def insert_current_hour_price(self, current_price:float, timestamp:datetime):
        """
        :param current_price:
        :param timestamp:
        For when electricity price is inserted every hour
        """
        pass

    @abstractmethod
    def insert_prices(self, prices: dict, date: datetime.date):
        """
        :param prices:
        :param date:
        For when electricity prices are inserted for whole day
        """
        pass

    @abstractmethod
    def stop(self):
        pass
