import schedule
import logging
import os
from schedules.hourly_schedule import HourlySchedule2days
from schedules.schedule_creator import ScheduleCreator
from typing import Callable, Dict, Tuple
from helpers.state_saver import StateSaver
import settings

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
file_handler = logging.FileHandler(os.path.join("../logs", "auto_schedule_creator.log"))
file_handler.setFormatter(log_formatter)
file_handler.setLevel(settings.FILE_LOG_LEVEL)
logger.addHandler(file_handler)


def test():
    fake_prices_today = {0: 1.0, 1: 2.82, 2: 2.52, 3: 39.6, 4: 75.06, 5: 92.91, 6: 104.52, 7: 150.03, 8: 190.85,
                         9: 122.88,
                         10: 104.39, 11: 88.69, 12: 81.28, 13: 90.18, 14: 88.63, 15: 90.23, 16: 93.46, 17: 101.96,
                         18: 104.0,
                         19: 140.09, 20: 200.09, 21: 93.49, 22: 7.18, 23: 1.34}
    fake_prices_tomorrow = {0: 1.0, 1: 30.0, 2: 3.0, 3: 40.0, 4: 5.0, 5: 6.0, 6: 7.0, 7: 8.0, 8: 9.0, 9: 10.0,
                            10: 104.39, 11: 88.69, 12: 81.28, 13: 90.18, 14: 88.63, 15: 90.23, 16: 93.46, 17: 101.96,
                            18: 104.0,
                            19: 0.2, 20: 200.09, 21: 93.49, 22: 7.18, 23: 1.34}
    test = AutoScheduleCreator(get_prices_method=lambda: (fake_prices_today, fake_prices_tomorrow))
    test.set_scheduled_times()


class AutoScheduleCreator(StateSaver):
    """
    Class for repeatedly creating schedules to turn devices on or off for the upcoming hours
    """

    # Auto schedule create periods allowed in hours
    ALLOWED_PERIODS = [6, 8, 12, 24]
    # At what minute is the schedule created - 23:55, 15:55 ... for 8 hour period
    MINUTE_START_AT = 55

    def __init__(self,
                 get_prices_method: Callable[[], Tuple[Dict, Dict]],
                 hourly_schedule: HourlySchedule2days = None,
                 period_split_h: int = 6,
                 max_total_cost: float = 300.0,
                 max_hours_to_run: int = 5,
                 min_hours_to_run: int = 2,
                 calculation_time_h: int = 16,
                 calculation_time_min: int = 50,
                 name: str = "Auto schedule creator",
                 state_file_loc: str = "C:\\py_related\\home_el_cntrl\\state"):
        self.state_file_loc = state_file_loc
        self.name = name
        self._get_prices_method = get_prices_method
        self._auto_create_enabled = True
        self._auto_create_period = 24
        self._hourly_schedule = hourly_schedule
        self._max_total_cost = max_total_cost
        self._max_hours_to_run = max_hours_to_run
        self._min_hours_to_run = min_hours_to_run
        self._calculation_time_h = calculation_time_h
        self._calculation_time_min = calculation_time_min
        self._period_split_h = period_split_h
        # Set default values initially, then attempt to load saved state
        self.load_state()
        # Activate auto create
        self.set_auto_create_enabled(self._auto_create_enabled)

    def loop(self):
        # Call periodically to execute auto schedule creation
        if self._auto_create_enabled:
            schedule.run_pending()
        else:
            logger.debug("Auto create disabled")

    def set_parameters(self,
                       period_split_h: int = 8,
                       max_total_cost: float = 50.0,
                       max_hours_to_run: int = 4,
                       min_hours_to_run: int = 0,
                       calculation_time_h: int = 16,
                       calculation_time_min: int = 50):
        self._period_split_h = period_split_h
        self._max_total_cost = max_total_cost
        self._max_hours_to_run = max_hours_to_run
        self._min_hours_to_run = min_hours_to_run
        self._calculation_time_h = calculation_time_h
        self._calculation_time_min = calculation_time_min
        if self._auto_create_enabled:
            self.set_up_scheduling()
        self.save_state()

    def get_schedule_name(self):
        return self._hourly_schedule.name

    def get_parameters(self):
        return self._period_split_h, self._max_total_cost, self._max_hours_to_run, self._min_hours_to_run, \
            self._calculation_time_h, self._calculation_time_min

    def set_auto_create_enabled(self, off_on: bool):
        self._auto_create_enabled = off_on
        self.save_state()
        if self._auto_create_enabled:
            self.set_up_scheduling()

    def get_auto_create_enabled(self):
        return self._auto_create_enabled

    def set_up_scheduling(self):
        # delete all schedules already setup
        schedule.clear()
        self.check_period()
        self.set_scheduled_times()

    def set_scheduled_times(self):
        logger.info("Setting schedule times")
        schedule_time_str = f"{self._calculation_time_h:02}:{self._calculation_time_min:02}"
        logger.info(f"Adding time {schedule_time_str}")
        schedule.every().day.at(f"{schedule_time_str}").do(self.execute_schedule_generation)

    def execute_schedule_generation(self):
        # get prices using the available method
        logger.info("Executing schedule creation")
        prices_today, prices_tomorrow = self._get_prices_method()
        schedule_today, schedule_tomorrow = ScheduleCreator.get_schedule_from_prices_v2(
            prices_today=prices_today,
            prices_tomorrow=prices_tomorrow,
            max_total_cost=self._max_total_cost,
            period_h=self._period_split_h,
            hours_ahead_to_calculate=self._auto_create_period,
            max_hours_to_run=self._max_hours_to_run,
            min_hours_to_run=self._min_hours_to_run)
        if self._hourly_schedule:
            self._hourly_schedule.set_schedule_full_day(today_tomorrow=False, schedule=schedule_today)
            self._hourly_schedule.set_schedule_full_day(today_tomorrow=True, schedule=schedule_tomorrow)
        else:
            logger.warning("No schedule assigned to auto creator, printing results")
            logger.warning(f"Today {schedule_today} Tomorrow {schedule_tomorrow}")

    def check_period(self):
        if self._period_split_h in self.ALLOWED_PERIODS:
            return
        # Get the closest allowed period length
        self._period_split_h = min(self.ALLOWED_PERIODS, key=lambda x: abs(x - self._period_split_h))
        logger.debug(f"Changed period to {self._period_split_h}")

    def save_state(self):
        state_to_save = {
            "period_split_h": self._period_split_h,
            "max_total_cost": self._max_total_cost,
            "max_hours_to_run": self._max_hours_to_run,
            "min_hours_to_run": self._min_hours_to_run,
            "calculation_time_h": self._calculation_time_h,
            "calculation_time_min": self._calculation_time_min,
            "_auto_create_enabled": self._auto_create_enabled,
            "_auto_create_period": self._auto_create_period,
        }
        StateSaver.save_state_to_file(base_path=self.state_file_loc, data=state_to_save, name=self.name)
        logger.info(f"State saved successfully for {self.name}")

    def load_state(self):
        loaded_state = StateSaver.load_state_from_file(base_path=self.state_file_loc, name=self.name)
        if loaded_state is None:
            logger.info(f"No state file for this object {self.name} in {self.state_file_loc}")
            return
        try:
            # Dictionary keys are read as strings from JSON, comvert them to ints
            self._period_split_h = loaded_state["period_split_h"]
            self._max_total_cost = loaded_state["max_total_cost"]
            self._max_hours_to_run = loaded_state["max_hours_to_run"]
            self._min_hours_to_run = loaded_state["min_hours_to_run"]
            self._calculation_time_h = loaded_state["calculation_time_h"]
            self._calculation_time_min = loaded_state["calculation_time_min"]
            self._auto_create_period = loaded_state["_auto_create_period"]
            self._auto_create_enabled = loaded_state["_auto_create_enabled"]
            logger.info(f"State retrieved successfully for {self.name}")
            logger.info(f"State {loaded_state}")
        except KeyError as e:
            logger.error(f"KeyError while loading state object {self.name}: {e}")
        except Exception as e:
            logger.error(f"Failed to load state object {self.name}. Error: {e}")


if __name__ == '__main__':
    test()
