import datetime
import logging
import os
import time
from devices.device import Device
from typing import List, Optional
from helpers.observer_pattern import Subject
from helpers.state_saver import StateSaver

# Setup logging
log_formatter = logging.Formatter('%(asctime)s:%(name)s:%(levelname)s:%(message)s')
logger = logging.getLogger(__name__)
logger.setLevel(logging.DEBUG)
# Console debug
stream_handler = logging.StreamHandler()
stream_handler.setFormatter(log_formatter)
logger.addHandler(stream_handler)

# File logger
file_handler = logging.FileHandler(os.path.join("/logs", "hourly_schedule.log"))
file_handler.setFormatter(log_formatter)
file_handler.setLevel(logging.DEBUG)
logger.addHandler(file_handler)


def test():
    cntr = 0
    try:
        sch = HourlySchedule2days("Test schedule")
        sch.set_schedule_hour_off_on(today_tomorrow=True, hour=12, cmd=True)
        sch.set_schedule_hour_off_on(today_tomorrow=True, hour=1, cmd=True)
        while (True):
            sch.loop()
            cntr += 1
            time.sleep(1)
    except KeyboardInterrupt:
        print("Test stopped")


class HourlySchedule2days(Subject, StateSaver):
    """
    Class for controlling devices in an hourly schedule for today and tomorrow
    """

    event_name_schedule_change = "schedule_changed"
    event_name_new_device_associated = "new_device_associated"

    def __init__(self, name: str,state_file_loc: str ="C:\\py_related\\home_el_cntrl\\state"):
        """
        :param name: Name of schedule
        """
        super().__init__()
        self.name = name
        self.state_file_loc = state_file_loc
        # Dictionarries holding keys from 0 to 23 representing hours in each day
        # If the value of a hour key is true device should be on for that hour
        self.schedule_today = {key: False for key in range(24)}
        self.schedule_tomorrow = {key: False for key in range(24)}
        self.datetime_now = datetime.date.today()
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
            logger.debug(f"State retrieved successfully for {self.name}")
            logger.debug(f"Schedule today {self.schedule_today}")
            logger.debug(f"Schedule today {self.schedule_tomorrow}")
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
        expected_state = self.get_current_expected_state()
        self.set_device_cmds(expected_state)

    def set_device_cmds(self, cmd: bool):
        """
        :param cmd: turn on or off
        :return:
        """
        if self.device_list is None:
            logger.debug("Device list is empty")
            return
        for dev in self.device_list:
            # set all device auto cmds to true
            dev.set_auto_run(cmd)

    def add_to_device_list(self, dev: Device):
        """
        :param dev: Device that will be turned on or off
        :return:
        """
        self.device_list.append(dev)
        self.notify_observers(self.event_name_new_device_associated)

    def set_schedule_hour_off_on(self, today_tomorrow: bool, hour: int, cmd: bool):
        """
        :param today_tomorrow: false if value for today, true if for tomorrow
        :param hour: hour to set
        :param cmd: if a device should be on or off for that hour
        :return:
        """
        logger.debug(f"Schedule single hour change")
        if hour > 23 or hour < 0:
            logger.error("Invalid hour set")
            return
        if not today_tomorrow:
            self.schedule_today[hour] = cmd
        else:
            self.schedule_tomorrow[hour] = cmd
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
        if len(schedule) != 24:
            logger.error("Invalid schedule set")
            return
        if not today_tomorrow:
            self.schedule_today.update(schedule)
        else:
            self.schedule_tomorrow.update(schedule)
        self.save_state()
        self.notify_observers(self.event_name_schedule_change)

    def get_current_expected_state(self):
        """
        :return: true if device should be on
        """
        current_hour = datetime.datetime.now().hour
        return self.schedule_today[current_hour]

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


if __name__ == '__main__':
    test()
