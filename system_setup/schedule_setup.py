import os
import logging
from collections.abc import Callable
from schedules.hourly_schedule import HourlySchedule2days
from schedules.auto_schedule_creator import AutoScheduleCreator
from schedules.daily_timed_schedule import DailyTimedSchedule
from devices.device import Device
from devices.shellyPlugUrlControlled import URLControlledShellyPlug
from devices.deviceTypes import DeviceType
from schedules.schedule_types import ScheduleType
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
file_handler = logging.FileHandler(os.path.join("../logs", "schedule_setup.log"))
file_handler.setFormatter(log_formatter)
file_handler.setLevel(settings.FILE_LOG_LEVEL)
logger.addHandler(file_handler)

"""
Methods for getting list of schedules used in the particular system
Make sure to have correct order, do not assign a schedule creator to a schedule that has not yet been created
Configuration file expected like below:
[
    {"type": "HOURLY_SCHEDULE_2_DAYS", "name": "2 DAY SCHEDULE", "assigned_device": "Plug 1"},
    {"type": "AUTO_SCHEDULE_CREATOR", "name": "Auto schedule creator", "assigned_schedule": "2 DAY SCHEDULE"},
    {"type": "DAILY_TIMED_SCHEDULE", "name": "Alarm clock", "assigned_device": ""},
    {"type": "DAILY_TIMED_SCHEDULE", "name": "Christmas lights", "assigned_device": "Plug 2"}
]
type must be from schedules.schedule_types Enum
"""

def test_fc() -> None:
    file_path = os.path.join(settings.SCH_CONFIG_FILE_LOCATION, settings.SCH_CONFIG_FILE_NAME)
    fake_dev_list = [URLControlledShellyPlug(name="Plug 2", url_off="fake", url_on="fake")]
    sch_list = get_schedule_list_from_file(fake_get_prices, fake_dev_list,file_path)
    for sch in sch_list:
        print(sch)

def fake_get_prices() -> tuple[dict,dict]:
    # For testing
    pass

def get_schedule_list_from_file(get_prices_method: Callable[[], tuple[dict, dict]],
                                dev_list: list[Device],
                              file_path: str) -> list:
    """
    :param get_prices_method: method needed for objects that rely on creating schedules for devices according to electricity
    prices
    :param dev_list: list of system devices. To be assinged to schedules created here.
    :param file_path: Path of schedule file
    :return: List of Schedule objects defined in the device file
    """
    sch_dic_list = get_schedule_json_from_file(file_path)
    sch_list = get_sch_list_from_dic_list(sch_dic_list, get_prices_method, dev_list)
    return sch_list

def get_sch_list_from_dic_list(sch_dic_list: list[dict],
                               get_prices_method:  Callable[[], tuple[dict, dict]],
                               dev_list: list[Device]) -> list:
    """
    :param sch_dic_list: List of Schedule objects defined in the device file
    :param get_prices_method: method needed for objects that rely on creating schedules for devices according to electricity
    prices
    :param dev_list: list of system devices. To be assinged to schedules created here.
    :return: List of Schedule objects defined in the device file
    """
    sch_list: list = []
    for sch_dic in sch_dic_list:
        if sch_dic["type"] == ScheduleType.HOURLY_SCHEDULE_2_DAYS.name:
            sch_list.append(HourlySchedule2days(name=sch_dic["name"]))
        elif sch_dic["type"] == ScheduleType.AUTO_SCHEDULE_CREATOR.name:
            assigned_schedule_name = sch_dic["assigned_schedule"]
            assigned_sch = None
            if assigned_schedule_name:
                assigned_sch = next((sch for sch in sch_list if sch.name == assigned_schedule_name), None)
                if not assigned_sch:
                    raise Exception(f"The assigned schedule for AUTO_SCHEDULE_CREATOR does not exist: {assigned_schedule_name}")
            sch_list.append(AutoScheduleCreator(name=sch_dic["name"],
                                       get_prices_method=get_prices_method,
                                       hourly_schedule=assigned_sch))
        elif sch_dic["type"] == ScheduleType.DAILY_TIMED_SCHEDULE.name:
            logger.debug("DAILY_TIMED_SCHEDULE")
            daily_schedule = DailyTimedSchedule(name=sch_dic["name"])
            assigned_dev_name = sch_dic["assigned_device"]
            if assigned_dev_name:
                assigned_dev = next((dev for dev in dev_list if dev.name == assigned_dev_name),None)
                if not assigned_dev:
                    raise Exception(
                        f"The assigned device for DAILY_TIMED_SCHEDULE does not exist: {assigned_dev_name}")
                daily_schedule.add_device(assigned_dev)
            sch_list.append(daily_schedule)
        else:
            raise Exception("Schedule file contains unknown device type")
    return sch_list

def get_schedule_json_from_file(file_path: str) -> list[dict]:
    """
    :param file_path: path where to look for the file
    :return: list of dictionaries that describe the schedules in the system
    """
    if not os.path.exists(file_path):
        # State file does not exist, create one with default parameters
        logger.error(f"Schedule creator file dos not exist {file_path}.")
        raise FileNotFoundError(f"The file at '{file_path}' was not found")
    try:
        with open(file_path, 'r') as file:
            return json.load(file)
    except json.decoder.JSONDecodeError:
        logger.error(f"Unable to parse schedule data from {file_path}.")
    except Exception as e:
        logger.error(f"Unable to load schedules {file_path}. Error {e}")
    raise Exception("Failed to open schedule file")

if __name__ == "__main__":
    test_fc()