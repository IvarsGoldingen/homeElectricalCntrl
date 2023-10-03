"""
Class that inherits from MqttDevice class
For controllingand monitoring a shelly smart plug
Mqtt must be enabled from the webservice of the device
"""
import time

from devices.mqttDevice import MqttDevice
from devices.device import Device
from typing import Callable
import logging
import os

# Setup logging
log_formatter = logging.Formatter('%(asctime)s:%(name)s:%(levelname)s:%(message)s')
logger = logging.getLogger(__name__)
logger.setLevel(logging.INFO)
# Console debug
stream_handler = logging.StreamHandler()
stream_handler.setFormatter(log_formatter)
stream_handler.setLevel(logging.INFO)
logger.addHandler(stream_handler)
# File logger
file_handler = logging.FileHandler(os.path.join("logs", "shelly_plug_log.log"))
file_handler.setFormatter(log_formatter)
file_handler.setLevel(logging.INFO)
logger.addHandler(file_handler)


def test():
    smart_plug = ShellyPlug(name="Dvieļu žāvētājs",
                            mqtt_publish=test_publish, plug_id="shellyplug-s-80646F840029")
    smart_plug.set_mode(Device.MODE_MAN)
    smart_plug.set_manual_run(True)
    smart_plug.process_received_mqtt_data("Dummy data")
    smart_plug.set_block(True)


def test_publish(topic: str, payload: str):
    print("Test publish")
    print(f"{topic}\t{payload}")


class ShellyPlug(MqttDevice):

    TIME_SINCE_LAST_MSG_TO_CONSIDER_ONLINE_S = 60
    # Value that is received from MQTT when there is no overtemperature
    OVERTEMPERATURE_OK = 0


    def __init__(self, plug_id: str, mqtt_publish: Callable[[str, str], None], name: str = "Test shelly plug"):
        """
        :param plug_id: must be set correct to read correct messages. See device web. Example "shellyplug-s-80646F840029"
        :param mqtt_publish: method to call when a mqtt message should be published
        :param name: device name - for logs and UI
        """
        super().__init__(mqtt_publish, name)
        self.plug_id = plug_id
        # Used to check wether device is available
        self.time_of_last_msg = 0
        # Will be set to true if MQTT msg received recently
        self.state_online = False
        self.base_mqtt_topic = f"shellies/{self.plug_id}"
        # listen to all messages related to this socket
        self.listen_topic = f"{self.base_mqtt_topic}/#"
        self.publish_topic = f"{self.base_mqtt_topic}/relay/0/command"
        # messages that should be reacted upon
        self.t_topic = f"{self.base_mqtt_topic}/temperature"
        self.power_topic = f"{self.base_mqtt_topic}/relay/0/power"
        self.energy_topic = f"{self.base_mqtt_topic}/relay/0/energy"
        self.state_topic = f"{self.base_mqtt_topic}/relay/0"
        self.overtemperature_topic = f"{self.base_mqtt_topic}/overtemperature"
        # Values that will be read from MQTT
        self.power = self.NO_DATA_VALUE
        self.energy = self.NO_DATA_VALUE
        self.temperature = self.NO_DATA_VALUE
        self.state_off_on = False
        self.overtemperature = 0
        # use dictionarry to map variables to topics
        # Define a mapping of topics to data variables and their data types
        self.topic_mapping = {
            self.t_topic: ("temperature", float),
            self.power_topic: ("power", float),
            self.energy_topic: ("energy", float),
            self.state_topic: ("state_off_on", bool),
            self.overtemperature_topic: ("overtemperature", int)
        }

    def loop(self):
        """
        Call periodically
        hecks wether set device status equals set state
        And checks when the last msg received from it to detect device not connected
        :return:
        """
        self.check_status_online_offline()
        self.check_cmd_vs_actual_state()


    def check_status_online_offline(self):
        # Checks wether set device status equals set state
        time_since_last_msg = time.perf_counter() - self.time_of_last_msg
        self.state_online = False if time_since_last_msg > self.TIME_SINCE_LAST_MSG_TO_CONSIDER_ONLINE_S else True

    def check_cmd_vs_actual_state(self):
        if not self.state_online:
            # Only do if device is online
            return
        if self.get_cmd_given() != self.state_off_on:
            logger.warning(f"Device {self.name} state was not equal to set command")
            self._turn_device_off_on(self.get_cmd_given())

    def process_received_mqtt_data(self, topic: str, data: str):
        """
        This will be called by the Mqtt client when a relevant message to this device is published
        :param topic: mqtt topic
        :param data: payload
        :return:
        """
        # logger.debug(f"{self.name} received from mqtt:")
        # logger.debug(f"Topic: {topic} Data: P{data}")
        if topic in self.topic_mapping:
            self.time_of_last_msg = time.perf_counter()
            # The message received corresponds to one of the values
            target_variable, data_type = self.topic_mapping[topic]
            logger.debug(f"found a topic in the topic map variable {target_variable}")
            # Data looks like this: b'81.17' - remove the b''
            clean_data = data.strip("b'")
            if data_type == bool:
                # handle bools differently because if cast from string they will always be true
                if topic == self.state_topic:
                    # For state the data is either "on" or "off"
                    if clean_data == "on":
                        self.state_off_on = True
                    elif clean_data == "off":
                        self.state_off_on = False
                    else:
                        logger.error("Unknown value for bool variable")
            else:
                # All other are int, real values that have to be cast from str
                try:
                    new_value = data_type(clean_data)
                    logger.debug(f"New Value is {new_value}")
                    setattr(self, target_variable, new_value)
                    self.check_for_overtemperature()
                except ValueError:
                    # Handle conversion errors if needed
                    logger.debug(f"Value error {data} in topic {topic}")
                    pass
        else:
            # Handle unrecognized topics if needed
            logger.debug("Unhandled MQTT msg:")
            logger.debug(f"{topic}\t{data}")
        logger.debug(f"{self.temperature} {self.power} {self.energy} {self.state_off_on}")

    def check_for_overtemperature(self):
        "If msg of overtemperature received, block device"
        if self.overtemperature != self.OVERTEMPERATURE_OK:
            logger.warning(f"Overtemperature {self.name}")
            self.set_block(True)

    def _turn_device_off_on(self, off_on: bool):
        """
        To turn on a shelly plug from mqtt by pyublishing to a certain topic, example:
        self.publish("shellies/shellyplug-s-80646F840029/relay/0/command", "on")
        :param off_on: false = turn off, true = turn on
        :return:
        """
        publish_payload = "on" if off_on else "off"
        self.mqtt_publish(self.publish_topic, publish_payload)


if __name__ == '__main__':
    test()
