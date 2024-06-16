from enum import Enum


class DeviceType(Enum):
    FAKE = 0
    SHELLY_PLUG = 1
    SHELLY_PLUS = 2
    SHELLY_PLUS_PM = 3
    URL_CONTROLLED_SHELLY_PLUG = 4
