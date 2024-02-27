import logging
import os
import time
import schedule
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
file_handler = logging.FileHandler(os.path.join("logs", "daily_timed_schedule.log"))
file_handler.setFormatter(log_formatter)
file_handler.setLevel(logging.DEBUG)
logger.addHandler(file_handler)


def test():
    sch = DailyTimedSchedule(name="Test schedule",
                             hour_on=17,
                             minute_on=30,
                             on_time_min=1)
    sch.enable_schedule()
    try:
        while True:
            sch.loop()
            time.sleep(1.0)
    except KeyboardInterrupt:
        print("Keyboard interrupt received. Exiting...")


class DailyTimedSchedule(Subject, StateSaver):
    """
    Class for controlling devices by setting time of turning on and how long to be on
    """

    event_name_schedule_change = "schedule_status_changed"
    event_name_new_device_associated = "new_device_associated"

    def __init__(self, name: str = "Test DailyTimedSchedule",
                 hour_on: int = 6,
                 minute_on: int = 45,
                 on_time_min: int = 15,
                 state_file_loc: str = "C:\\py_related\\home_el_cntrl\\state"):
        """
        :param name: name of schedule
        :param hour_on: at what hour to turn on
        :param minute_on: at what minute to turn on
        :param on_time_min: how long to be on in minutes
        """
        # Devices linked to this schedule - used to execute schedule
        super().__init__()
        self.name = name
        self.state_file_loc = state_file_loc
        # if false, will be executed once
        self.repeat_daily = True
        self._hour_on = 6
        self._minute_on = 45
        self._on_time_min = 15
        # Will the schedule activate at the set time
        self._schedule_enabled = False
        # should device be on or off
        self._command = False
        self.load_state()
        # Base schedule
        self.schedule_base = schedule.Scheduler()
        self.set_settings(hour_on, minute_on, on_time_min)
        # Devices that are controlled by this schedule
        self.device_list: Optional[List[Device]] = []
        self.time_when_dev_was_turned_on_s = 0


    def save_state(self):
        state_dict = {
            "_hour_on": self._hour_on,
            "_minute_on": self._minute_on,
            "_on_time_min": self._on_time_min,
            "_schedule_enabled": self._schedule_enabled,
            "_command": self._command,
            "repeat_daily": self.repeat_daily
        }
        self.save_state_to_file(base_path=self.state_file_loc, name=self.name, data=state_dict)

    def load_state(self):
        loaded_state = StateSaver.load_state_from_file(base_path=self.state_file_loc, name=self.name)
        if loaded_state is None:
            logger.info(f"No state file for this object {self.name} in {self.state_file_loc}")
            return
        try:
            self._hour_on = loaded_state["_hour_on"]
            self._minute_on = loaded_state["_minute_on"]
            self._on_time_min = loaded_state["_on_time_min"]
            self._schedule_enabled = loaded_state["_schedule_enabled"]
            self._command = loaded_state["_command"]
            self.repeat_daily = loaded_state["repeat_daily"]
        except KeyError as e:
            logger.error(f"KeyError while loading state object {self.name}: {e}")
        except Exception as e:
            logger.error(f"Failed to load state object {self.name}. Error: {e}")

    def loop(self):
        """
        Has to be called regulary for schedule to work
        Will set device auto_on commands
        Turn on off the device at set times
        """
        # Has to be called for base scheduling to work
        self.schedule_base.run_pending()
        # Check if time to turn off and do so
        if self.check_if_time_to_turn_off():
            self.turn_devices_off()
        else:
            # Write the current command to the devices
            self.write_cmd_to_devices()

    def enable_schedule(self):
        """
        Start the schedule
        """
        logger.debug(f"Enabling schedule {self._hour_on:02}:{self._minute_on:02}")
        self.schedule_base.clear()
        self.schedule_base.every().day.at(f"{self._hour_on:02}:{self._minute_on:02}").do(self.turn_devices_on)
        self._schedule_enabled = True
        self.notify_observers(self.event_name_schedule_change)

    def disable_schedule(self):
        logger.debug("Disabling schedule")
        self._schedule_enabled = False
        self.schedule_base.clear()
        self.notify_observers(self.event_name_schedule_change)

    def set_settings(self, hour_on, minute_on, on_time_min):
        # Check if setting in range before applying
        if 0 <= hour_on <= 23:
            self._hour_on = hour_on
        if 0 <= minute_on <= 59:
            self._minute_on = minute_on
        if 0 < on_time_min < 1440:
            self._on_time_min = on_time_min
        if self._schedule_enabled:
            # Set new settings if schedule enabled
            self.enable_schedule()

    def get_settings(self, ):
        return self._hour_on, self._minute_on, self._on_time_min

    def turn_devices_on(self):
        # Turn on devices from schedule
        logger.debug("Turning on")
        self.time_when_dev_was_turned_on_s = time.perf_counter()
        self._command = True
        self.write_cmd_to_devices()
        self.notify_observers(self.event_name_schedule_change)
        if not self.repeat_daily:
            logger.debug("Daily repeat is off, disabling schedule")
            self.disable_schedule()

    def check_if_time_to_turn_off(self):
        """
        Turn off after set time
        :return: True if should be turned off
        """
        if not self._command:
            # There is no on command so no need to turn off
            return False
        time_passed_s = time.perf_counter() - self.time_when_dev_was_turned_on_s
        # Full  minutes passed
        time_passed_minutes = time_passed_s // 60
        if time_passed_minutes >= self._on_time_min:
            return True
        else:
            return False

    def write_cmd_to_devices(self):
        for dev in self.device_list:
            dev.set_auto_run(self._command)

    def turn_devices_off(self):
        logger.debug("Turning off")
        self._command = False
        self.write_cmd_to_devices()
        self.notify_observers(self.event_name_schedule_change)

    def add_device(self, device: Device):
        # Add a device to be controlled from this schedule
        self.device_list.append(device)
        self.notify_observers(self.event_name_new_device_associated)

    @property
    def schedule_enabled(self):
        return self._schedule_enabled

    @property
    def command(self):
        return self._command


if __name__ == '__main__':
    test()
