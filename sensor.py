from dataclasses import dataclass
@dataclass
class Sensor:
    NO_DATA_VALUE = -99.99
    # sensor name, example: temperature, outside_t etc
    name: str
    # sensor value
    value: float
    # if sensor comes from certain group use this. Example ahu device with several sensors
    group_name: str = ""
