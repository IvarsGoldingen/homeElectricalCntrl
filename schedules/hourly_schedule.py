import datetime
import logging
import os
import time
from devices.device import Device
from typing import List, Optional
from helpers.observer_pattern import Subject
from helpers.state_saver import StateSaver
import settings

# Setup logging
log_formatter = logging.Formatter('%(asctime)s:%(name)s:%(levelname)s:%(message)s')
logger = logging.getLogger(__name__)
logger.setLevel(settings.BASE_LOG_LEVEL)
# Console debug
stream_handler = logging.StreamHandler()
stream_handler.setFormatter(log_formatter)
stream_handler.setLevel(logging.DEBUG)
logger.addHandler(stream_handler)

# File logger
file_handler = logging.FileHandler(os.path.join("../logs", "hourly_schedule.log"))
file_handler.setFormatter(log_formatter)
file_handler.setLevel(settings.FILE_LOG_LEVEL)
logger.addHandler(file_handler)

class HourlySchedule2days(Subject, StateSaver):
    """
    Class for controlling devices in an hourly schedule for today and tomorrow
    """
    #Schedule changed
    event_name_schedule_change = "schedule_changed"
    event_name_new_device_associated = "new_device_associated"
    # Next 15 minutes started, move indication in UI of active period
    event_name_period_changed = "period_change"

    def __init__(self, name: str, state_file_loc: str = "C:\\py_related\\home_el_cntrl\\state"):
        """
        :param name: Name of schedule
        """
        super().__init__()
        self.name = name
        self.state_file_loc = state_file_loc
        # Dictionarries holding keys from 0 to 96 representing 15 min periods in each day
        # If the value of a period index key is true device should be on for that period
        self.schedule_today = {key: False for key in range(96)}
        self.schedule_tomorrow = {key: False for key in range(96)}
        self.datetime_now = datetime.date.today()
        # To display in UI
        self.current_hour = datetime.datetime.now().hour
        self.current_minute = datetime.datetime.now().minute
        self.current_period = (self.current_hour * 4)  +  (self.current_minute // 15)
        self.load_state()
        # Devices linked to this schedule - used to execute schedule
        self.device_list: Optional[List[Device]] = []

    def save_state(self):
        state_to_save = {
            "schedule_today": self.schedule_today,
            "schedule_tomorrow": self.schedule_tomorrow,
            "datetime_now": self.datetime_now.strftime("%Y-%m-%d")
        }
        StateSaver.save_state_to_file(base_path=self.state_file_loc, data=state_to_save, name=self.name)

    def load_state(self):
        loaded_state = StateSaver.load_state_from_file(base_path=self.state_file_loc, name=self.name)
        if loaded_state is None:
            logger.info(f"No state file for this object {self.name} in {self.state_file_loc}")
            return
        try:
            state_date_time = loaded_state["datetime_now"]
            if datetime.date.fromisoformat(state_date_time) != self.datetime_now:
                logger.info(f"State for {self.name} is from an earlier date, state is not loaded")
                return
            # Dictionary keys are read as strings from JSON, comvert them to ints
            schedule_today_temp = loaded_state["schedule_today"]
            self.schedule_today = {int(key): value for key, value in schedule_today_temp.items()}
            schedule_tomorrow_temp = loaded_state["schedule_tomorrow"]
            self.schedule_tomorrow = {int(key): value for key, value in schedule_tomorrow_temp.items()}
            logger.info(f"State retrieved successfully for {self.name}")
            logger.info(f"Schedule today {self.schedule_today}")
            logger.info(f"Schedule tomorrow {self.schedule_tomorrow}")
        except KeyError as e:
            logger.error(f"KeyError while loading state object {self.name}: {e}")
        except Exception as e:
            logger.error(f"Failed to load state object {self.name}. Error: {e}")

    def loop(self):
        """
        Call periodically to have devices turned on or off according to schedule
        :return:
        """
        self.check_if_new_day()
        hour_now = datetime.datetime.now().hour
        minute_now = datetime.datetime.now().minute
        expected_period_nr = (hour_now * 4) + (minute_now//15)
        expected_state = self.schedule_today[expected_period_nr]
        self.set_device_cmds(expected_state)
        self.check_period_change_change(hour_now, minute_now)

    def check_period_change_change(self, hour_now: int, minute_now: int):
        """
        Check if 15 minute period has changed, so UI can display current hour
        """
        current_period = (hour_now * 4) + (minute_now // 15)
        if current_period != self.current_period:
            self.current_period = current_period
            self.notify_observers(HourlySchedule2days.event_name_period_changed)

    def set_device_cmds(self, cmd: bool):
        """
        :param cmd: turn on or off
        :return:
        """
        if self.device_list is None:
            logger.debug("Device list is empty")
            return
        for dev in self.device_list:
            logger.debug(f"Setting device CMD dev{dev} cmd{cmd}")
            # set all device auto cmds to true
            dev.set_auto_run(cmd)

    def add_device(self, dev: Device):
        """
         # Add a device to be controlled from this schedule
        :param dev: Device that will be turned on or off
        :return:
        """
        self.device_list.append(dev)
        self.notify_observers(self.event_name_new_device_associated)

    def set_schedule_period_off_on(self, today_tomorrow: bool, period: int, cmd: bool):
        """
        :param today_tomorrow: false if value for today, true if for tomorrow
        :param period: period to set
        :param cmd: if a device should be on or off for that hour
        :return:
        """
        logger.debug(f"Schedule single hour change")
        if not today_tomorrow:
            self.schedule_today[period] = cmd
        else:
            self.schedule_tomorrow[period] = cmd
        self.save_state()
        logger.debug(f"Schedule today: {self.schedule_today}")
        logger.debug(f"Schedule tomorrow: {self.schedule_tomorrow}")
        self.notify_observers(self.event_name_schedule_change)

    def set_schedule_full_day(self, today_tomorrow: bool, schedule: dict):
        """
        :param today_tomorrow: false - schedule for today, true - schedule for tomorrow
        :param schedule: dictionary holding keys from 0 to 23 and values holding true or false representing if device
        should be on for that hour
        :return:
        """
        logger.debug(f"Schedule full day change")
        if len(schedule) != 96:
            logger.error("Invalid schedule set")
            return
        if not today_tomorrow:
            logger.debug(f"Current day schedule change")
            self.schedule_today.update(schedule)
        else:
            logger.debug(f"Next day schedule change")
            self.schedule_tomorrow.update(schedule)
        self.save_state()
        self.notify_observers(self.event_name_schedule_change)

    def check_if_new_day(self):
        """
        On new day move tomorrow's schedule to today, and clear it
        """
        actual_today = datetime.date.today()
        if actual_today == self.datetime_now:
            # date has not changed
            return
        # new day
        self.datetime_now = actual_today
        self.move_tomorrow_in_today()
        self.save_state()
        self.notify_observers(self.event_name_schedule_change)

    def move_tomorrow_in_today(self):
        # next day, move tomorrow's schedule in today
        self.schedule_today.update(self.schedule_tomorrow)
        # set tomorrow's schedule all to false
        self.schedule_tomorrow = {key: False for key in self.schedule_tomorrow}
