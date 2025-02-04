import time
from typing import Callable
import json
import logging
import os
from dataclasses import dataclass
from helpers.sensor import Sensor
from devices.deviceTypes import DeviceType
from devices.mqttDevice import MqttDevice
from helpers.mqtt_client import MyMqttClient
import settings
import secrets
from helpers.observer_pattern import Observer

# Setup logging
log_formatter = logging.Formatter('%(asctime)s:%(name)s:%(levelname)s:%(message)s')
logger = logging.getLogger(__name__)
logger.setLevel(settings.BASE_LOG_LEVEL)
# Console debug
stream_handler = logging.StreamHandler()
stream_handler.setFormatter(log_formatter)
# TODO:stream_handler.setLevel(settings.CONSOLE_LOG_LEVEL)
stream_handler.setLevel(logging.DEBUG)
logger.addHandler(stream_handler)
# File logger
file_handler = logging.FileHandler(os.path.join("../logs", "shelly_energy_meter.log"))
file_handler.setFormatter(log_formatter)
file_handler.setLevel(settings.FILE_LOG_LEVEL)
logger.addHandler(file_handler)


def test_fc():
    class TestObserver(Observer):
        def handle_subject_event(self, event_type: str, *args, **kwargs):
            print(f"{event_type}")

    print("Start")
    client = MyMqttClient()
    test_observer = TestObserver()
    em = ShellyEnergyMeter3em(name="Energy meter",
                              mqtt_publish=client.publish,
                              device_id="shellypro3em-34987a446e54")
    client.add_listen_topic(em.listen_topic, em.process_received_mqtt_data)
    client.start(settings.MQTT_SERVER, settings.MQTT_PORT, user=secrets.MQTT_USER, psw=secrets.MQTT_PSW)
    em.register(test_observer, ShellyEnergyMeter3em.event_name_new_extra_data)
    test_cntr = 0
    try:
        print("Entering loop")
        while True:
            time.sleep(0.5)
            client.loop()
            em.loop()
            if test_cntr % 20 == 0:
                print(em.sensor_data)
            test_cntr += 1
    except KeyboardInterrupt:
        print("\nKeyboardInterrupt caught. Exiting gracefully.")
    finally:
        client.stop()


@dataclass()
class EnergyMeterData:
    voltage: dict[1:Sensor, 2:Sensor, 3:Sensor]
    current: dict[1:Sensor, 2:Sensor, 3:Sensor]
    freq: dict[1:Sensor, 2:Sensor, 3:Sensor]
    power: dict[1:Sensor, 2:Sensor, 3:Sensor]
    pf: dict[1:Sensor, 2:Sensor, 3:Sensor]
    energy: dict[1:Sensor, 2:Sensor, 3:Sensor]

    def __str__(self):
        def format_dict(name, data):
            return f"{name}:\n" + "\n".join(f"  Phase {key}: {value}" for key, value in data.items())
        return "\n\n".join([
            format_dict("Voltage", self.voltage),
            format_dict("Current", self.current),
            format_dict("Frequency", self.freq),
            format_dict("Power", self.power),
            format_dict("Power Factor", self.pf),
            format_dict("Energy", self.energy),
        ])


class ShellyEnergyMeter3em(MqttDevice):
    """

    Class that inherits from MqttDevice class
    For monitoring of shelly Pro 3EM energy meter
    Made as a device since it is possible to add a relay output to the device. This will not be implemented
    for initial commit.
    Mqtt must be enabled from the webservice of the device

    TODO:
    handle UI, create widget
    data logging
    """

    TIME_SINCE_LAST_MSG_TO_CONSIDER_ONLINE_S = 60
    event_name_new_extra_data = "device_new_extra_data"

    def __init__(self, device_id: str, mqtt_publish: Callable[[str, str], None], name: str = "Energy meter"):
        """
        :param device_id: must be set correct to read correct messages. See device web. Example "shellyplug-s-80646F840029"
        :param mqtt_publish: method to call when a mqtt message should be published
        :param name: device name - for logs and UI
        """
        super().__init__(mqtt_publish, name=name, device_type=DeviceType.SHELLY_PRO_3EM)
        self.device_id = device_id
        # Used to check wether device is available
        self.time_of_last_msg = 0
        # Will be set to true if MQTT msg received recently
        self.state_online = False
        self.base_mqtt_topic = f"{self.device_id}"
        # listen to all messages related to this MQTT device
        self.listen_topic = f"{self.base_mqtt_topic}/#"
        # Only one MQTT topic relevant for energy meter
        self.data_mqtt_topic = f"{self.base_mqtt_topic}/events/rpc"
        # Received data is dictionaries with one of the following keys in them
        self.phase_mapping_real_time_data = {"em1:0": 1, "em1:1": 2, "em1:2": 3}
        self.phase_mapping_energy_data = {"em1data:0": 1, "em1data:1": 2, "em1data:2": 3}
        # Values that will be read from MQTT
        self.sensor_data = self.setup_sensor_obj()

    def loop(self) -> None:
        """
        Call periodically
        Checks when the last msg received from it to detect device not connected
        :return:
        """
        self.check_status_online_offline()

    def setup_sensor_obj(self) -> EnergyMeterData:
        """
        :return: EnergyMeterData object containing all sensors
        """
        current_sensor_list = []
        power_sensor_list = []
        energy_sensor_list = []
        voltage_sensor_list = []
        pf_sensor_list = []
        freq_sensor_list = []
        for i in range(3):
            current_sensor_list.append(
                Sensor(name=f"ph{i + 1}_current", value=Sensor.NO_DATA_VALUE, group_name=self.name))
            power_sensor_list.append(Sensor(name=f"ph{i + 1}_power", value=Sensor.NO_DATA_VALUE, group_name=self.name))
            energy_sensor_list.append(
                Sensor(name=f"ph{i + 1}_energy", value=Sensor.NO_DATA_VALUE, group_name=self.name))
            voltage_sensor_list.append(
                Sensor(name=f"ph{i + 1}_voltage", value=Sensor.NO_DATA_VALUE, group_name=self.name))
            pf_sensor_list.append(
                Sensor(name=f"ph{i + 1}_pf", value=Sensor.NO_DATA_VALUE, group_name=self.name))
            freq_sensor_list.append(
                Sensor(name=f"ph{i + 1}_freq", value=Sensor.NO_DATA_VALUE, group_name=self.name))
        sensor_data = EnergyMeterData(
            voltage={1: voltage_sensor_list[0], 2: voltage_sensor_list[1], 3: voltage_sensor_list[2]},
            current={1: current_sensor_list[0], 2: current_sensor_list[1], 3: current_sensor_list[2]},
            freq={1: freq_sensor_list[0], 2: freq_sensor_list[1], 3: freq_sensor_list[2]},
            power={1: power_sensor_list[0], 2: power_sensor_list[1], 3: power_sensor_list[2]},
            pf={1: pf_sensor_list[0], 2: pf_sensor_list[1], 3: pf_sensor_list[2]},
            energy={1: energy_sensor_list[0], 2: energy_sensor_list[1], 3: energy_sensor_list[2]})
        return sensor_data

    def check_status_online_offline(self) -> None:
        # Checks wether device last message recent enough to consider it online
        time_since_last_msg = time.perf_counter() - self.time_of_last_msg
        online = False if time_since_last_msg > self.TIME_SINCE_LAST_MSG_TO_CONSIDER_ONLINE_S else True
        if online != self.state_online:
            logger.debug(f"{self.name} went online" if online else f"{self.name} went offline")
            self.state_online = online
            self.device_notify(self.event_name_new_extra_data, self.name, self.device_type)

    def process_received_mqtt_data(self, topic: str, data: str) -> None:
        """
        This will be called by the Mqtt client when a relevant message to this device is published
        :param topic: mqtt topic
        :param data: payload
        :return:
        """
        if topic == self.data_mqtt_topic:
            # Received topic is as expected
            self.time_of_last_msg = time.perf_counter()
            # Data looks like this: b'81.17' - remove the b''
            clean_data = data.strip("b'")
            self.extract_data_from_message(clean_data)
        else:
            logger.debug(f"Unhandled MQTT topic for energy meter {self.name}")

    def extract_data_from_message(self, data: str) -> None:
        """
        Update sensor class instance variable with read data
        :param data: receiving string message from MQTT
        :return:
        """
        new_data = False
        try:
            # Convert JSON string to dictionary
            dict_data = json.loads(data)
            # Access params
            params = dict_data.get("params", {})
            if not params:
                logger.error(f"Message without params key {dict_data}")
                return
            # params exist
            if any(key in params for key in self.phase_mapping_real_time_data.keys()):
                # Check for keys that identify real time value data
                new_data = self.handle_real_time_values(params)
            elif any(key in params for key in self.phase_mapping_energy_data.keys()):
                # Check for keys that identify energy value data
                new_data = self.handle_energy_data(params)
            else:
                logger.debug(f"Unused data received {data}")
        except json.JSONDecodeError as e:
            logger.error(f"JSON decoding error: {e}")
        if new_data:
            self.device_notify(self.event_name_new_extra_data, self.name, self.device_type)

    def handle_energy_data(self, data: dict) -> bool:
        """
        :param data: dictionary holding energy data like this:
        {"ts":1738256760.23,"em1data:0":{"id":0,"total_act_energy":6737.72,"total_act_ret_energy":1.78}
        :return: True if sensor data read
        """
        # return value
        new_data = False
        # Find the key and phase number of the data
        key, phase = next(((k, v) for k, v in self.phase_mapping_energy_data.items() if k in data), (None, -1))
        try:
            inner_data = data.get(key)
            energy_wmin_str = inner_data.get("total_act_energy")
            energy_wh = float(energy_wmin_str)
            energy_kwh = energy_wh / 1000
            self.sensor_data.energy[phase].value = energy_kwh
            new_data = True
        except KeyError as e:
            logger.error(f"Key error when handling energy meter energy data: {e}")
            logger.error(data)
        except ValueError as e:
            logger.error(f"Failed to cast data: {e}")
        return new_data

    def handle_real_time_values(self, data: dict) -> bool:
        """
        :param data: dictionary holding real time data like this:
        {"ts":1738256744.19,"em1:0":{"id":0,"act_power":1.2,"aprt_power":19.0,
        "current":0.081,"freq":50.0,"pf":0.07,"voltage":235.2}}
        :return: True if sensor data read
        """
        # return value
        new_data = False
        # Find the key and phase number of the data
        key, phase = next(((k, v) for k, v in self.phase_mapping_real_time_data.items() if k in data), (None, -1))
        try:
            inner_data = data.get(key)
            # Get voltage
            voltage_str = inner_data.get("voltage")
            voltage = float(voltage_str)
            self.sensor_data.voltage[phase].value = voltage
            # If at least one data point received return that data has been changed
            new_data = True
            # Get power
            power_str = inner_data.get("act_power")
            power = float(power_str)
            self.sensor_data.power[phase].value = power
            # Get current
            current_str = inner_data.get("current")
            current = float(current_str)
            self.sensor_data.current[phase].value = current
            # Get frequency
            freq_str = inner_data.get("freq")
            freq = float(freq_str)
            self.sensor_data.freq[phase].value = freq
            # Get power factor
            pf_str = inner_data.get("pf")
            pf = float(pf_str)
            self.sensor_data.pf[phase].value = pf
        except KeyError as e:
            logger.error(f"Key error when handling energy meter real time data: {e}")
            logger.error(data)
        except ValueError as e:
            logger.error(f"Failed to cast data: {e}")
        return new_data

    def get_sensors_as_list(self) -> list[Sensor]:
        """
        class EnergyMeterData:
       voltage: dict[1:Sensor, 2:Sensor, 3:Sensor]
       current: dict[1:Sensor, 2:Sensor, 3:Sensor]
       freq: dict[1:Sensor, 2:Sensor, 3:Sensor]
       power: dict[1:Sensor, 2:Sensor, 3:Sensor]
       pf: dict[1:Sensor, 2:Sensor, 3:Sensor]
       energy: dict[1:Sensor, 2:Sensor, 3:Sensor]
        :return:
        """
        sensor_list = []
        for ph in range(1,4):
            sensor_list.append(self.sensor_data.voltage[ph])
            sensor_list.append(self.sensor_data.current[ph])
            sensor_list.append(self.sensor_data.freq[ph])
            sensor_list.append(self.sensor_data.power[ph])
            sensor_list.append(self.sensor_data.pf[ph])
            sensor_list.append(self.sensor_data.energy[ph])
        return sensor_list

    def _turn_device_off_on(self, off_on: bool):
        """
        Could be relevant as a relay add on can be added to the energy meter
        :param off_on:
        :return:
        """
        raise Exception("On off for energy meter not implemented")


if __name__ == "__main__":
    test_fc()

"""
Received MQTT messages:

Messages that contain energy data hav e a key like this: em1data:0, em1data:1, em1data:2
hellypro3em-34987a446e54/events/rpc b'{"src":"shellypro3em-34987a446e54","dst":"shellypro3em-34987a446e54/events","method":"NotifyStatus","params":
{"ts":1738256760.23,"em1data:0":{"id":0,"total_act_energy":6737.72,"total_act_ret_energy":1.78}}}'

shellypro3em-34987a446e54/events/rpc b'{"src":"shellypro3em-34987a446e54","dst":"shellypro3em-34987a446e54/events","method":"NotifyStatus","params":
{"ts":1738256760.29,"em1data:1":{"id":1,"total_act_energy":26084.47,"total_act_ret_energy":0.00}}}'

shellypro3em-34987a446e54/events/rpc b'{"src":"shellypro3em-34987a446e54","dst":"shellypro3em-34987a446e54/events","method":"NotifyStatus","params":
{"ts":1738256760.36,"em1data:2":{"id":2,"total_act_energy":4262.62,"total_act_ret_energy":0.00}}}'

Messages that contain current, voltage, power have topics like this: em1:0, em1:1, em1:2
shellypro3em-34987a446e54/events/rpc b'{"src":"shellypro3em-34987a446e54","dst":"shellypro3em-34987a446e54/events","method":"NotifyStatus","params":
{"ts":1738256744.19,"em1:0":{"id":0,"act_power":1.2,"aprt_power":19.0,"current":0.081,"freq":50.0,"pf":0.07,"voltage":235.2}}}'

shellypro3em-34987a446e54/events/rpc b'{"src":"shellypro3em-34987a446e54","dst":"shellypro3em-34987a446e54/events","method":"NotifyStatus","params":
{"ts":1738256737.21,"em1:1":{"id":1,"act_power":30.5,"aprt_power":58.8,"current":0.251,"freq":50.0,"pf":0.51,"voltage":233.8}}}'

shellypro3em-34987a446e54/events/rpc b'{"src":"shellypro3em-34987a446e54","dst":"shellypro3em-34987a446e54/events","method":"NotifyStatus","params":
{"ts":1738256716.22,"em1:2":{"id":2,"act_power":28.7,"aprt_power":54.7,"current":0.233,"freq":50.0,"pf":0.52,"voltage":234.6}}}'

List of values have messages like below, these will not be used:
shellypro3em-34987a446e54/events/rpc b'{"src":"shellypro3em-34987a446e54","dst":"shellypro3em-34987a446e54/events","method":"NotifyEvent","params":
{"ts":1738256760.23,"events":[{"component":"em1data:0","id":0,"event":"data","ts":1738256700.00,"data":{"ts": 1738256700,"period": 60,"values":
[[0.0209,0.0000,0.0000,0.0000,1.6,1.0,19.0,17.3,235.502,234.857,235.167,0.081,0.073,0.079 ]]}}]}}'

shellypro3em-34987a446e54/events/rpc b'{"src":"shellypro3em-34987a446e54","dst":"shellypro3em-34987a446e54/events","method":"NotifyEvent","params":
{"ts":1738256760.29,"events":[{"component":"em1data:1","id":1,"event":"data","ts":1738256700.00,"data":{"ts": 1738256700,"period": 60,"values":
[[1.0923,0.0000,0.0000,0.0000,694.5,30.2,887.9,58.6,234.042,232.746,233.830,3.798,0.250,0.369 ]]}}]}}'

shellypro3em-34987a446e54/events/rpc b'{"src":"shellypro3em-34987a446e54","dst":"shellypro3em-34987a446e54/events","method":"NotifyEvent","params":
{"ts":1738256760.36,"events":[{"component":"em1data:2","id":2,"event":"data","ts":1738256700.00,"data":{"ts": 1738256700,"period": 60,"values":
[[0.4760,0.0000,0.0000,0.0000,28.9,28.0,55.0,54.3,234.895,234.403,234.584,0.234,0.231,0.232 ]]}}]}}'

"""
