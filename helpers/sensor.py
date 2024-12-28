from dataclasses import dataclass
from global_var import NO_DATA_VALUE

@dataclass
class Sensor:
    NO_DATA_VALUE = NO_DATA_VALUE
    # sensor name, example: temperature, outside_t etc
    name: str
    # sensor value
    value: float
    # if sensor comes from certain group use this. Example ahu device with several sensors
    group_name: str = ""
