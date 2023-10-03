"""
Class that inherits from device class
For controlling/monitoring a mqtt device
"""

from devices.device import Device
from typing import Callable
from abc import abstractmethod


class MqttDevice(Device):
    # Value for
    NO_DATA_VALUE = -99.99

    def __init__(self, mqtt_publish: Callable[[str, str], None],
                 name: str = "Test mqtt device"):
        """
        :param mqtt_publish: callback method to publish mqtt messages related to this device
        :param name: name of device
        """
        super().__init__(name)
        self.mqtt_publish = mqtt_publish

    @abstractmethod
    def process_received_mqtt_data(self, topic: str, data: str):
        """
        :param topic: topic to which the data was published
        :param data: payload
        :return:
        """
        pass
