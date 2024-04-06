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
from devices.shellyPlus import ShellyPlus

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
file_handler = logging.FileHandler(os.path.join("../logs", "shelly_plus_log.log"))
file_handler.setFormatter(log_formatter)
file_handler.setLevel(logging.INFO)
logger.addHandler(file_handler)

def test():
    print("Start")
    client = MyMqttClient()
    smart_relay = ShellyPlusPM(name="Shelly plus PM",
                             mqtt_publish=client.publish, plug_id="shellyplus1pm-d48afc417d58")
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

class ShellyPlusPM(ShellyPlus):

    def __init__(self, plug_id: str, mqtt_publish: Callable[[str, str], None],
                 name: str = "Shelly plus PM",
                 device_type: DeviceType = DeviceType.SHELLY_PLUS_PM):
        super().__init__(plug_id, mqtt_publish, name, device_type)
        self.power = self.NO_DATA_VALUE # W
        self.voltage = self.NO_DATA_VALUE
        self.current = self.NO_DATA_VALUE
        self.energy = self.NO_DATA_VALUE #kWh

    def process_received_mqtt_data(self, topic: str, data: str):
        """
        self.power
        self.voltage
        self.current
        self.energy
        """
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
            self.state_off_on, self.temperature, self.power, self.voltage, self.current, self.energy = (
                self.handle_output_json(clean_data))
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

    def handle_output_json(self, data: str) -> (bool, float, float, float, float, float):
        """
        Handle json data received from mqtt
        @param data: String data holding data about devices relay output
        '{"id":0, "source":"init", "output":false, "apower":0.0, "voltage":233.6, "current":0.000,
        "aenergy":{"total":0.000,"by_minute":[0.000,0.000,0.000],"minute_ts":1710094020},
        "temperature":{"tC":47.6, "tF":117.6}}
        @return: boolean representing if the output is on or off and devices temperature
        """

        logger.debug("Handling JSON output data")
        try:
            data_dict = json.loads(data)
            logger.debug(f"Data dict = {data_dict}")
            output_on_off = data_dict["output"]
            power = data_dict["apower"]
            voltage = data_dict["voltage"]
            current = data_dict["current"]
            energy = data_dict["aenergy"]["total"] / 1000.0
            t = data_dict["temperature"]["tC"]
            logger.debug(f"Temperature is {t} output is {output_on_off}")
            return output_on_off, t, power, voltage, current, energy
        except json.decoder.JSONDecodeError:
            logger.error(f"Failed to parce output json data: {data}")
        except Exception as e:
            logger.error(f"Error reading json output data. Error: {e} Data:{data}")
        return False, self.NO_DATA_VALUE, self.NO_DATA_VALUE, self.NO_DATA_VALUE, self.NO_DATA_VALUE, self.NO_DATA_VALUE

    def __str__(self):
        return (f"Name: {self.name} Online: {self.state_online} Output: {self.state_off_on} Input: {self.di_off_on} "
                f"Temperature: {self.temperature} Power: {self.power} Voltage: {self.voltage} Current: {self.current} "
                f"Energy: {self.energy}")

if __name__ == '__main__':
    test()

"""
Callback shellyplus1pm-d48afc417d58/command b'status_update'
Callback shellyplus1pm-d48afc417d58/status b'{"ble":{},"cloud":{"connected":true},"input:0":{"id":0,"state":false},"mqtt":{"connected":true},"switch:0":{"id":0, "source":"init", "output":false, "apower":0.0, "voltage":233.6, "current":0.000, "aenergy":{"total":0.000,"by_minute":[0.000,0.000,0.000],"minute_ts":1710094020},"temperature":{"tC":47.6, "tF":117.6}},"sys":{"mac":"D48AFC417D58","restart_required":false,"time":"20:07","unixtime":1710094030,"uptime":2401,"ram_size":245708,"ram_free":142084,"fs_size":458752,"fs_free":143360,"cfg_rev":18,"kvs_rev":0,"schedule_rev":0,"webhook_rev":0,"available_updates":{},"reset_reason":3},"wifi":{"sta_ip":"172.31.0.247","status":"got ip","ssid":"it_burns_when_IP_2G","rssi":-37},"ws":{"connected":false}}'
Callback shellyplus1pm-d48afc417d58/status/ble b'{}'
Callback shellyplus1pm-d48afc417d58/status/cloud b'{"connected":true}'
Callback shellyplus1pm-d48afc417d58/status/input:0 b'{"id":0,"state":false}'
Callback shellyplus1pm-d48afc417d58/status/mqtt b'{"connected":true}'
Callback shellyplus1pm-d48afc417d58/status/switch:0 b'{"id":0, "source":"init", "output":false, "apower":0.0, "voltage":233.6, "current":0.000, "aenergy":{"total":0.000,"by_minute":[0.000,0.000,0.000],"minute_ts":1710094020},"temperature":{"tC":47.6, "tF":117.6}}'
Callback shellyplus1pm-d48afc417d58/status/sys b'{"mac":"D48AFC417D58","restart_required":false,"time":"20:07","unixtime":1710094030,"uptime":2401,"ram_size":245640,"ram_free":139752,"fs_size":458752,"fs_free":143360,"cfg_rev":18,"kvs_rev":0,"schedule_rev":0,"webhook_rev":0,"available_updates":{},"reset_reason":3}'
Callback shellyplus1pm-d48afc417d58/status/wifi b'{"sta_ip":"172.31.0.247","status":"got ip","ssid":"it_burns_when_IP_2G","rssi":-37}'
Callback shellyplus1pm-d48afc417d58/status/ws b'{"connected":false}'
"""