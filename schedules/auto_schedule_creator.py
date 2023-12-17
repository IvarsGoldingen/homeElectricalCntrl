import schedule
import logging
import os
from schedules.hourly_schedule import HourlySchedule2days
from schedules.schedule_creator import ScheduleCreator
from typing import Callable, Dict, Tuple

# Setup logging
log_formatter = logging.Formatter('%(asctime)s:%(name)s:%(levelname)s:%(message)s')
logger = logging.getLogger(__name__)
logger.setLevel(logging.DEBUG)
# Console debug
stream_handler = logging.StreamHandler()
stream_handler.setFormatter(log_formatter)
logger.addHandler(stream_handler)

# File logger
file_handler = logging.FileHandler(os.path.join("logs", "auto_schedule_creator.log"))
file_handler.setFormatter(log_formatter)
file_handler.setLevel(logging.DEBUG)
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
    test = AutoScheduleCreator(auto_create_period=8,
                               get_prices_method=lambda: (fake_prices_today, fake_prices_tomorrow))


class AutoScheduleCreator:
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
                 auto_create_period: int = 6,
                 max_total_cost: float = 300.0,
                 max_hours_to_run: int = 5,
                 min_hours_to_run: int = 2):
        self._get_prices_method = get_prices_method
        self._auto_create_enabled = True
        self._auto_create_period = auto_create_period
        self._hourly_schedule = hourly_schedule
        # settings for schedule
        self._max_total_cost = max_total_cost
        self._max_hours_to_run = max_hours_to_run
        self._min_hours_to_run = min_hours_to_run

    def loop(self):
        # Call periodically to execute auto schedule creation
        if self._auto_create_enabled:
            schedule.run_pending()

    def set_parameters(self,
                       auto_create_period: int = 8,
                       max_total_cost: float = 50.0,
                       max_hours_to_run: int = 4,
                       min_hours_to_run: int = 0):
        self._auto_create_period = auto_create_period
        self._max_total_cost = max_total_cost
        self._max_hours_to_run = max_hours_to_run
        self._min_hours_to_run = min_hours_to_run

    def get_schedule_name(self):
        return self._hourly_schedule.name

    def get_parameters(self):
        return self._auto_create_period, self._max_total_cost, self._max_hours_to_run, self._min_hours_to_run

    def set_auto_create_enabled(self, off_on: bool):
        self._auto_create_enabled = off_on
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
        # Always start before midnight
        start_hour = 23
        # Set other execution times depending on schedule period
        while start_hour > 0:
            schedule.every().day.at(f"{start_hour:02}:{self.MINUTE_START_AT:02}").do(self.execute_schedule_generation)
            start_hour -= self._auto_create_period

    def execute_schedule_generation(self):
        # get prices using the available method
        prices_today, prices_tomorrow = self._get_prices_method()
        schedule_today, schedule_tomorrow = ScheduleCreator.get_schedule_from_prices(
            prices_today=prices_today,
            prices_tomorrow=prices_tomorrow,
            max_total_cost=self._max_total_cost,
            hours_ahead_to_calculate=self._auto_create_period,
            max_hours_to_run=self._max_hours_to_run,
            min_hours_to_run=self._min_hours_to_run)
        if self._hourly_schedule:
            self._hourly_schedule.set_schedule_full_day(today_tomorrow=False, schedule=schedule_today)
            self._hourly_schedule.set_schedule_full_day(today_tomorrow=True, schedule=schedule_tomorrow)
        else:
            logger.warning("No schedule assigned to auto creator, printing results")
            logger.warning(f"{schedule_today}\n{schedule_tomorrow}")

    def check_period(self):
        if self._auto_create_period in self.ALLOWED_PERIODS:
            return
        # Get the closest allowed period length
        self._auto_create_period = min(self.ALLOWED_PERIODS, key=lambda x: abs(x - self._auto_create_period))
        logger.debug(f"Changed period to {self._auto_create_period}")


if __name__ == '__main__':
    test()
