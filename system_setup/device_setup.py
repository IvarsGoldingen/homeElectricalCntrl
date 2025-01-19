import datetime
import os
import logging
from collections.abc import Callable
from uu import decode

from devices.deviceTypes import DeviceType
from devices.shellyPlugMqtt import ShellyPlug
from devices.shellyPlus import ShellyPlus
from devices.shellyPlusPM import ShellyPlusPM
from devices.shellyPlugUrlControlled import URLControlledShellyPlug
from devices.device import Device
import settings
import json

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

"""
Methods for getting list of devices used in the particular system
Configuration file expected like below:
[
    {"type": "SHELLY_PLUG", "name": "Plug 1", "plug_id": "shellyplug-s-80646F840029"},
    {"type": "SHELLY_PLUG", "name": "Plug 2", "plug_id": "shellyplug-s-C8C9A3B8E92E"}
]
type must be from devices.deviceTypes Enum
"""

def test_fc() -> None:
    file_path = os.path.join(settings.DEV_CONFIG_FILE_LOCATION, settings.DEV_CONFIG_FILE_NAME)
    dev_list = get_device_list_from_file(fake_mqtt_publish, file_path)
    for dev in dev_list:
        print(dev)

def fake_mqtt_publish(str1: str, str2: str):
    # For testing
    pass

def get_device_list_from_file(mqtt_publish_method: Callable[[str, str], None],
                              file_path: str) -> list[Device]:
    """
    :param mqtt_publish_method: Needed for MQTT device initialisation
    :param file_path: Path of device file
    :return: List of Device objects defined in the device file
    """
    dev_dic_list = get_device_json_from_file(file_path)
    dev_list = get_dev_list_from_dic_list(dev_dic_list, mqtt_publish_method)
    return dev_list

def get_dev_list_from_dic_list(dev_dic_list: list[dict], mqtt_publish_method:  Callable[[str,str], None]) -> list[Device]:
    """
    :param dev_dic_list: list of dictionaries that describe the devices in the system
    :param mqtt_publish_method: Needed for MQTT device initialisation
    :return: List of Device objects defined in the device dictionary list
    """
    dev_list: list[Device] = []
    for dev_dic in dev_dic_list:
        if dev_dic["type"] == DeviceType.SHELLY_PLUG.name:
            dev_list.append(ShellyPlug(name=dev_dic["name"],
                                mqtt_publish=mqtt_publish_method,
                                plug_id=dev_dic["plug_id"]))
        elif dev_dic["type"] == DeviceType.SHELLY_PLUS.name:
            dev_list.append(ShellyPlus(name=dev_dic["name"],
                                       mqtt_publish=mqtt_publish_method,
                                       plug_id=dev_dic["plug_id"]))
        elif dev_dic["type"] == DeviceType.SHELLY_PLUS_PM.name:
            dev_list.append(ShellyPlusPM(name=dev_dic["name"],
                                       mqtt_publish=mqtt_publish_method,
                                       plug_id=dev_dic["plug_id"]))
        elif dev_dic["type"] == DeviceType.URL_CONTROLLED_SHELLY_PLUG.name:
            dev_list.append(URLControlledShellyPlug(name=dev_dic["name"],
                                       url_on=dev_dic["url_on"],
                                       url_off=dev_dic["url_off"]))
        else:
            raise Exception("Device file contains unknown device type")
    return dev_list

def get_device_json_from_file(file_path: str) -> list[dict]:
    """
    :param file_path: path where to look for the file
    :return: list of dictionaries that describe the devices in the system
    """
    if not os.path.exists(file_path):
        # State file does not exist, create one with default parameters
        logger.error(f"Device creator file dos not exist {file_path}.")
        raise FileNotFoundError(f"The file at '{file_path}' was not found")
    try:
        with open(file_path, 'r') as file:
            return json.load(file)
    except json.decoder.JSONDecodeError:
        logger.error(f"Unable to parse device data from {file_path}.")
    except Exception as e:
        logger.error(f"Unable to load devices {file_path}. Error {e}")
    raise Exception("Failed to open device file")

if __name__ == "__main__":
    test_fc()