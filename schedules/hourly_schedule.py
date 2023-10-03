import datetime
import logging
import os
import time
from devices.device import Device
from typing import List, Optional

# Setup logging
log_formatter = logging.Formatter('%(asctime)s:%(name)s:%(levelname)s:%(message)s')
logger = logging.getLogger(__name__)
logger.setLevel(logging.DEBUG)
# Console debug
stream_handler = logging.StreamHandler()
stream_handler.setFormatter(log_formatter)
logger.addHandler(stream_handler)

# File logger
file_handler = logging.FileHandler(os.path.join("logs", "hourly_schedule.log"))
file_handler.setFormatter(log_formatter)
file_handler.setLevel(logging.DEBUG)
logger.addHandler(file_handler)


def test():
    cntr = 0
    try:
        sch = HourlySchedule2days()
        sch.add_to_device_list(cb1)
        sch.set_schedule_hour_off_on(today_tomorrow=True, hour=12, cmd=True)
        sch.set_schedule_hour_off_on(today_tomorrow=True, hour=1, cmd=True)
        while (True):
            sch.loop()
            cntr += 1
            time.sleep(1)
    except KeyboardInterrupt:
        print("Test stopped")


def cb1(cmd: bool):
    print(f"Callback 1 {cmd}")


class HourlySchedule2days:
    """
    Class for controlling devices in an hourly schedule for today and tomorrow
    """


    def __init__(self, name: str):
        """
        :param name: Name of schedule
        """
        self.name = name
        # Dictionarries holding keys from 0 to 23 representing hours in each day
        # If the value of a hour key is true device should be on for that hour
        self.schedule_today = {key: False for key in range(24)}
        self.schedule_tomorrow = {key: False for key in range(24)}
        self.datetime_now = datetime.date.today()
        # Devices linked to this schedule - used to execute schedule
        self.device_list: Optional[List[Device]] = []

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

    def set_schedule_hour_off_on(self, today_tomorrow: bool, hour: int, cmd: bool):
        """
        :param today_tomorrow: false if value for today, true if for tomorrow
        :param hour: hour to set
        :param cmd: if a device should be on or off for that hour
        :return:
        """
        if 0 <= hour <= 23:
            if not today_tomorrow:
                self.schedule_today[hour] = cmd
            else:
                self.schedule_tomorrow[hour] = cmd
        else:
            logger.error("Invalid hour set")
        logger.debug(f"Schedule today: {self.schedule_today}")
        logger.debug(f"Schedule tomorrow: {self.schedule_tomorrow}")

    def set_schedule_full_day(self, today_tomorrow: bool, schedule: dict):
        """
        :param today_tomorrow: false - schedule for today, true - schedule for tomorrow
        :param schedule: dictionary holding keys from 0 to 23 and values holding true or false representing if device
        should be on for that hour
        :return:
        """
        if len(schedule) == 24:
            if not today_tomorrow:
                self.schedule_today.update(schedule)
            else:
                self.schedule_tomorrow.update(schedule)
        else:
            logger.error("Invalid schedule set")

    def get_current_expected_state(self):
        """
        :return: true if device should be on
        """
        current_hour = datetime.datetime.now().hour
        return self.schedule_today[current_hour]

    def check_if_new_day(self):
        """
        On new day move tomorrows schedule to today, and clear it
        """
        actual_today = datetime.date.today()
        if actual_today == self.datetime_now:
            # date has not changed
            return
        self.datetime_now = actual_today
        # next dat, move tomorrows schedule in today
        self.schedule_today.update(self.schedule_tomorrow)
        # set tomorrows schedule allto false
        self.schedule_tomorrow = {key: False for key in self.schedule_tomorrow}


if __name__ == '__main__':
    test()
