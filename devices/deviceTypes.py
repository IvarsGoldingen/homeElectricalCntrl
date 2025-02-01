from enum import Enum


class DeviceType(Enum):
    FAKE = 0 # testing purposes
    SHELLY_PLUG = 1 # Shelly smart plug MQTT
    SHELLY_PLUS = 2 # Shelly relay basic MQTT
    SHELLY_PLUS_PM = 3 # Shelly relay with power consumption MQTT
    URL_CONTROLLED_SHELLY_PLUG = 4 # Shelly smart plug but programmed to be controlled from URL
    SHELLY_PRO_3EM = 3 # Shelly energy meter MQTT
