"""
Class that inherits from MqttDevice class
For controlling and monitoring a shelly smart relay ShellyPlus
Mqtt must be enabled from the webservice of the device
"""
import time
from typing import Callable
import logging
import os
import json
from devices.deviceTypes import DeviceType
from devices.mqttDevice import MqttDevice
from devices.device import Device
from helpers.mqtt_client import MyMqttClient
import secrets

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
file_handler = logging.FileHandler(os.path.join("logs", "shelly_plus_log.log"))
file_handler.setFormatter(log_formatter)
file_handler.setLevel(logging.INFO)
logger.addHandler(file_handler)


def test():
    print("Start")
    client = MyMqttClient()
    smart_relay = ShellyPlus(name="Shelly plus",
                             mqtt_publish=client.publish, plug_id="shellyplus1-441793ab3fb4")
    client.add_listen_topic(smart_relay.listen_topic, smart_relay.process_received_mqtt_data)
    client.start(secrets.MQTT_SERVER, secrets.MQTT_PORT, user=secrets.MQTT_USER, psw=secrets.MQTT_PSW)
    test_cntr = 0
    try:
        smart_relay.set_mode(Device.MODE_MAN)
        print("Entering loop")
        while True:
            time.sleep(0.5)
            client.loop()
            smart_relay.loop()
            if test_cntr % 10 == 0:
                print(smart_relay)
            if test_cntr % 60 == 0:
                smart_relay.set_manual_run(not smart_relay.state_off_on)
            test_cntr += 1
    except KeyboardInterrupt:
        print("\nKeyboardInterrupt caught. Exiting gracefully.")
    finally:
        client.stop()


class ShellyPlus(MqttDevice):
    # If last msg older than  this, device will be considered offline
    TIME_SINCE_LAST_MSG_TO_CONSIDER_ONLINE_S = 60
    # How often to request status of device
    STATUS_REQ_FREQUENCY_S = 30
    # Output state and temperature info
    event_name_new_extra_data = "device_new_extra_data"
    # Digital input state change
    event_name_input_state_change = "device_input_state_change"

    def __init__(self, plug_id: str, mqtt_publish: Callable[[str, str], None],
                 name: str = "Test shelly plus",
                 device_type: DeviceType = DeviceType.SHELLY_PLUS):
        """
        :param plug_id: must be set correct to read correct messages. See device web.
        :param mqtt_publish: method to call when a mqtt message should be published
        :param name: device name - for logs and UI
        """
        super().__init__(mqtt_publish, name=name, device_type=device_type)
        self.plug_id = plug_id
        # Used to check wether device is available
        self.time_of_last_msg = 0
        self.time_of_last_status_req = 0
        # Will be set to true if MQTT msg received recently
        self.state_online = False
        self.base_mqtt_topic = f"{self.plug_id}"
        # listen to all messages related to this socket
        self.listen_topic = f"{self.base_mqtt_topic}/#"
        self.sw_cntrl_topic = f"{self.base_mqtt_topic}/command/switch:0"
        self.req_status_topic = f"{self.base_mqtt_topic}/command"
        # messages that should be reacted upon
        self.input_topic = f"{self.base_mqtt_topic}/status/input:0"
        self.output_topic = f"{self.base_mqtt_topic}/status/switch:0"
        # Values that will be read from MQTT
        self.di_off_on = False
        self.temperature = self.NO_DATA_VALUE
        # State of outpuut
        self.state_off_on = False
        # To indicate to program that device state should not be checked until next msg received
        self.cmd_sent_out = True

    def loop(self):
        """
        Call periodically
        Checks wether set device status equals set state
        Checks when the last msg received from it to detect device not connected
        :return:
        """
        self.check_status_online_offline()
        self.check_cmd_vs_actual_state()
        self.request_status()

    def request_status(self):
        """
        Request status updates of device in regular intervals
        """
        time_since_last_status_req = time.perf_counter() - self.time_of_last_status_req
        if time_since_last_status_req >= self.STATUS_REQ_FREQUENCY_S:
            logger.debug("Requesting device status")
            self.mqtt_publish(self.req_status_topic, "status_update")
            self.time_of_last_status_req = time.perf_counter()

    def check_status_online_offline(self):
        # Checks wether set device status equals set state
        time_since_last_msg = time.perf_counter() - self.time_of_last_msg
        online = False if time_since_last_msg > self.TIME_SINCE_LAST_MSG_TO_CONSIDER_ONLINE_S else True
        if online != self.state_online:
            logger.debug(f"{self.name} went online" if online else f"{self.name} went offline")
            self.state_online = online
            self.device_notify(self.event_name_new_extra_data, self.name, self.device_type)

    def check_cmd_vs_actual_state(self):
        if not self.state_online:
            # Only do if device is online
            return
        if self.cmd_sent_out:
            # cmd was just given, wait for reply from device
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
        logger.debug(f"Topic: {topic} Data: {data}")
        relevant_msg_received = False
        clean_data = data.strip("b'")
        if topic == self.output_topic:
            relevant_msg_received = True
            self.state_off_on, self.temperature = self.handle_output_json(clean_data)
            self.device_notify(self.event_name_new_extra_data, self.name, self.device_type)
            self.cmd_sent_out = False
        elif topic == self.input_topic:
            relevant_msg_received = True
            input_off_on = self.handle_input_json(clean_data)
            if input_off_on != self.di_off_on:
                self.di_off_on = input_off_on
                # Notify listening devices off input state change
                self.device_notify(self.event_name_input_state_change, self.name, self.device_type)
        else:
            # Handle unrecognized topics if needed
            pass
            # logger.debug("Unhandled MQTT msg:")
            # logger.debug(f"Topic: {topic}\tData: {data}")
        if relevant_msg_received:
            self.time_of_last_msg = time.perf_counter()
            logger.debug(self.__str__())

    def handle_output_json(self, data: str) -> (bool, float):
        """
        Handle json data received from mqtt
        @param data: String data holding data about devices relay output
        '{"id":0, "source":"init", "output":false,"temperature":{"tC":37.7, "tF":99.8}}
        @return: boolean representing if the output is on or off and devices temperature
        """
        logger.debug("Handling JSON output data")
        try:
            data_dict = json.loads(data)
            logger.debug(f"Data dict = {data_dict}")
            output_on_off = data_dict["output"]
            t = data_dict["temperature"]["tC"]
            logger.debug(f"Temperature is {t} output is {output_on_off}")
            return output_on_off, t
        except json.decoder.JSONDecodeError:
            logger.error(f"Failed to parce output json data: {data}")
        except Exception as e:
            logger.error(f"Error reading json output data. Error: {e} Data:{data}")
        return False, self.NO_DATA_VALUE

    def handle_input_json(self, data: str) -> bool:
        """
        Handle json data received from mqtt
        @param data: String data holding data about devices input
        '{"id":0,"state":false}'
        @return: boolean representing if the input is on or off
        """
        logger.debug(f"Handling JSON input data {data}")
        try:
            data_dict = json.loads(data)
            input_off_on = data_dict["state"]
            return input_off_on
        except json.decoder.JSONDecodeError:
            logger.error(f"Failed to parce input json data: {data}")
        except Exception as e:
            logger.error(f"Error reading json input data. Error: {e} Data:{data}")
        return False

    def _turn_device_off_on(self, off_on: bool):
        """
        To turn on a shelly plug from mqtt by pyublishing to a certain topic, example:
        self.publish("shellies/shellyplug-s-80646F840029/relay/0/command", "on")
        :param off_on: false = turn off, true = turn on
        :return:
        """
        if self.state_online and self.get_cmd_given() == self.state_off_on:
            # Device state equal to cmd, no need to send msg to mqtt
            return
        publish_payload = "on" if off_on else "off"
        self.mqtt_publish(self.sw_cntrl_topic, publish_payload)
        self.cmd_sent_out = True

    def __str__(self):
        return (f"Name: {self.name} Online: {self.state_online} Output: {self.state_off_on} Input: {self.di_off_on} "
                f"Temperature: {self.temperature}")


if __name__ == '__main__':
    test()

"""
DATA FROM MANUAL TESTS:
Send to:
client.add_listen_topic("shellies/shellyplus1-441793ab3fb4/#", test_cb)
client.publish("shellyplus1-441793ab3fb4/command", "status_update")
client.publish("shellyplus1-441793ab3fb4/command/switch:0", "on")
client.publish("shellyplus1-441793ab3fb4/command/switch:0", "off")

Reveive from when turning on or off:
shellyplus1-441793ab3fb4/online b'true'
shellyplus1-441793ab3fb4/events/rpc b'{"src":"shellyplus1-441793ab3fb4","dst":"shellyplus1-441793ab3fb4/events","method":"NotifyStatus","params":{"ts":1708179956.30,"switch:0":{"id":0,"temperature":{"tC":37.67,"tF":99.81}}}}'
shellyplus1-441793ab3fb4/status/switch:0 b'{"id":0, "source":"init", "output":false,"temperature":{"tC":37.7, "tF":99.8}}'
When using DI on device
shellyplus1-441793ab3fb4/events/rpc b'{"src":"shellyplus1-441793ab3fb4","dst":"shellyplus1-441793ab3fb4/events","method":"NotifyStatus","params":{"ts":1708180040.62,"input:0":{"id":0,"state":false}}}'
shellyplus1-441793ab3fb4/status/input:0 b'{"id":0,"state":false}'
When requesting status
shellyplus1-441793ab3fb4/command b'status_update'
shellyplus1-441793ab3fb4/status b'{"ble":{},"cloud":{"connected":false},"input:0":{"id":0,"state":false},"mqtt":{"connected":true},"switch:0":{"id":0, "source":"mqtt", "output":true,"temperature":{"tC":54.6, "tF":130.2}},"sys":{"mac":"441793AB3FB4","restart_required":false,"time":"16:48","unixtime":1708181319,"uptime":1497,"ram_size":246264,"ram_free":147424,"fs_size":458752,"fs_free":147456,"cfg_rev":9,"kvs_rev":0,"schedule_rev":0,"webhook_rev":0,"available_updates":{"stable":{"version":"1.2.0"}},"reset_reason":1},"wifi":{"sta_ip":"172.31.0.3","status":"got ip","ssid":"it_burns_when_IP_2G","rssi":-52},"ws":{"connected":false}}'
shellyplus1-441793ab3fb4/status/ble b'{}'
shellyplus1-441793ab3fb4/status/cloud b'{"connected":false}'
shellyplus1-441793ab3fb4/status/input:0 b'{"id":0,"state":false}'
shellyplus1-441793ab3fb4/status/mqtt b'{"connected":true}'
shellyplus1-441793ab3fb4/status/switch:0 b'{"id":0, "source":"mqtt", "output":true,"temperature":{"tC":54.6, "tF":130.2}}'
shellyplus1-441793ab3fb4/status/sys b'{"mac":"441793AB3FB4","restart_required":false,"time":"16:48","unixtime":1708181319,"uptime":1497,"ram_size":246196,"ram_free":145564,"fs_size":458752,"fs_free":147456,"cfg_rev":9,"kvs_rev":0,"schedule_rev":0,"webhook_rev":0,"available_updates":{"stable":{"version":"1.2.0"}},"reset_reason":1}'
shellyplus1-441793ab3fb4/status/wifi b'{"sta_ip":"172.31.0.3","status":"got ip","ssid":"it_burns_when_IP_2G","rssi":-52}'
shellyplus1-441793ab3fb4/status/ws b'{"connected":false}'
"""
