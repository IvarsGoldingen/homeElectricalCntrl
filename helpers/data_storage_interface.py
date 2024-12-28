from abc import ABC, abstractmethod
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
    def stop(self):
        pass
