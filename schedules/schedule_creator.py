import datetime
import heapq
import logging
import os
import time

# Setup logging
log_formatter = logging.Formatter('%(asctime)s:%(name)s:%(levelname)s:%(message)s')
logger = logging.getLogger(__name__)
logger.setLevel(logging.DEBUG)
# Console debug
stream_handler = logging.StreamHandler()
stream_handler.setFormatter(log_formatter)
logger.addHandler(stream_handler)

# File logger
file_handler = logging.FileHandler(os.path.join("logs", "schedule_creator.log"))
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
    start_time = time.perf_counter()
    schedule_today, schedule_tomorrow = ScheduleCreator.get_schedule_from_prices_v2(prices_today=fake_prices_today,
                                                                                    prices_tomorrow=fake_prices_tomorrow,
                                                                                    max_total_cost=50.0,
                                                                                    hours_ahead_to_calculate=24,
                                                                                    period_h=8,
                                                                                    max_hours_to_run=15,
                                                                                    min_hours_to_run=4)
    logger.debug(schedule_today)
    logger.debug(schedule_tomorrow)
    end_time = time.perf_counter()
    time_taken = end_time - start_time
    logger.debug(f"Calculations took {time_taken}s")


class ScheduleCreator:
    """
    Class for creating on off schedules for devices according to electricity prices.
    """

    @staticmethod
    def get_schedule_from_prices(prices_today: dict,
                                 prices_tomorrow: dict,
                                 max_total_cost: float = 50.0,
                                 hours_ahead_to_calculate: int = 20,
                                 max_hours_to_run: int = 10,
                                 min_hours_to_run: int = 6) -> [dict, dict]:
        """
        Calculate best times to turn on an appliance in set time
        :param prices_today: dictionary with keys 0...23 holding electricity prices for each hour today
        :param prices_tomorrow: dictionary with keys 0...23 holding electricity prices for each hour tomorrow
        :param max_total_cost: maximum total cost the device is allowed to use
        :param hours_ahead_to_calculate: for how many hours to create the schedule
        :param max_hours_to_run: what is the maximum number of on hours for the device to be on
        :param min_hours_to_run: what is the minimum number of hours for the device to be on, This has higher priority
        than max_total_cost.
        :return: 2 dictionaries, one holding todays schedule, the other tomorrows. Each key in dict represents the hour
        in the day, each value True or False wether the device should be on or not
        """
        if hours_ahead_to_calculate > 24:
            logger.warning("Calculation period set larger than 24 hours")
            hours_ahead_to_calculate = 24
        # get start hour now because calculation might take time, and when finished it might be the next hour
        if not prices_today or not prices_tomorrow:
            logger.warning("Price list does not exist")
            return {i: False for i in range(24)}, {i: False for i in range(24)}
        start_hour, future_prices_list = ScheduleCreator.get_list_of_upcoming_prices(prices_today, prices_tomorrow,
                                                                                     hours_ahead_to_calculate)
        run_list = ScheduleCreator.find_cheapest_hours_to_run_in(max_total_cost, max_hours_to_run, min_hours_to_run,
                                                                 future_prices_list)
        schedule_today, schedule_tomorrow = ScheduleCreator.create_schedule_dicts_from_run_list(run_list, start_hour)
        return schedule_today, schedule_tomorrow

    @staticmethod
    def get_schedule_from_prices_v2(prices_today: dict,
                                    prices_tomorrow: dict,
                                    max_total_cost: float = 600.0,
                                    hours_ahead_to_calculate=24,
                                    period_h: int = 8,
                                    max_hours_to_run: int = 7,
                                    min_hours_to_run: int = 6) -> [dict, dict]:
        """
        Calculate best times to turn on an appliance in set time, full period split in smaller periods
        :param prices_today: dictionary with keys 0...23 holding electricity prices for each hour today
        :param prices_tomorrow: dictionary with keys 0...23 holding electricity prices for each hour tomorrow
        :param max_total_cost: maximum total cost the device is allowed to use
        :param hours_ahead_to_calculate: for how many hours to create the schedule
        :param period_h: in what periods to split hours_ahead_to_calculate
        :param max_hours_to_run: what is the maximum number of on hours for the device to be on
        :param min_hours_to_run: what is the minimum number of hours for the device to be on, This has higher priority
        than max_total_cost.
        :return: 2 dictionaries, one holding todays schedule, the other tomorrows. Each key in dict represents the hour
        in the day, each value True or False wether the device should be on or not
        """
        if period_h > 24:
            logger.warning("Calculation period set larger than 24 hours")
            period_h = 24
        # get start hour now because calculation might take time, and when finished it might be the next hour
        if not prices_today or not prices_tomorrow:
            logger.warning("Price list does not exist")
            return {i: False for i in range(24)}, {i: False for i in range(24)}
        start_hour, future_prices_list = ScheduleCreator.get_list_of_upcoming_prices(prices_today, prices_tomorrow,
                                                                                     hours_ahead_to_calculate)
        # Split hours ahead in periods and calculate best hours to run for each period
        nr_of_periods = hours_ahead_to_calculate // period_h
        run_list = []
        for x in range(nr_of_periods):
            future_prices_to_use = future_prices_list[(period_h * x):(period_h * x + period_h)]
            temp_list = ScheduleCreator.find_cheapest_hours_to_run_in(max_total_cost, max_hours_to_run,
                                                                      min_hours_to_run,
                                                                      future_prices_to_use)
            run_list.extend(temp_list)
        schedule_today, schedule_tomorrow = ScheduleCreator.create_schedule_dicts_from_run_list(run_list, start_hour)
        return schedule_today, schedule_tomorrow

    @staticmethod
    def create_schedule_dicts_from_run_list(run_list, run_list_start_hour):
        """
        Create schedule dictionaries from a future hour run list and start hour
        :param run_list: list of True or False representing wether a device should be on or off for upcomming hours
        :param run_list_start_hour: the hour to which the first item in the run list coresponds
        :return: 2 dictionaries, one holding todays schedule, the other tomorrows. Each key in dict represents the hour
        in the day, each value True or False wether the device should be on or not
        """
        # Create schedule dictionaries with all false values
        schedule_today = {key: False for key in range(24)}
        schedule_tomorrow = {key: False for key in range(24)}
        # How many hours from the run_list will be meant for today and how many for tomorrow
        hours_for_today, hours_for_tomorrow = 0, 0
        run_list_length = len(run_list)
        if run_list_start_hour == 0:
            # If the hour is 0 that means that we are starting with tomorrow and all hours are meant for it
            # Do not allow for more than 24
            hours_for_tomorrow = min(run_list_length, 24)
        else:
            # If any other values is the first one, some hours for today, some for tomorrow
            hours_for_today = min((24 - run_list_start_hour), run_list_length)
            hours_for_tomorrow = max(run_list_length - hours_for_today, 0)
        # variable for keeping track of which item in the run list is currently being put into dictionarries
        run_list_item = 0
        # Put values in today's dictionary
        for hour_ofset in range(hours_for_today):
            schedule_today[run_list_start_hour + hour_ofset] = run_list[run_list_item]
            run_list_item += 1
        # Put values in tomorrow's dictionary
        for hour_ofset in range(hours_for_tomorrow):
            schedule_tomorrow[hour_ofset] = run_list[run_list_item]
            run_list_item += 1
        return schedule_today, schedule_tomorrow

    @staticmethod
    def find_cheapest_hours_to_run_in(max_total_cost: float,
                                      max_hours_to_run: int,
                                      min_hours_to_run: int,
                                      upcoming_prices: list) -> [list]:
        """
        :param max_total_cost: maximum total cost the device is allowed to use
        :param max_hours_to_run: what is the maximum number of on hours for the device to be on
        :param min_hours_to_run: what is the minimum number of hours for the device to be on, This has higher priority
        than max_total_cost.
        :param upcoming_prices: list of upcomming electricity prices, each value meaning one hour
        :return: list of bools representing wether a device should be on or off for upcomming prices list
        """
        # Get the length of future price list because it can be shorter than the setting
        hours_ahead_to_calculate = len(upcoming_prices)
        # How many on hours to consider
        nr_of_on_hours = min(max_hours_to_run, hours_ahead_to_calculate)
        logger.debug(f"Finding lowes price combo for prices: {upcoming_prices}")
        # Get the indicies and values for the cheapest prices in the list
        indices, values = ScheduleCreator.find_n_smallest_items_in_list(upcoming_prices, nr_of_on_hours)
        while nr_of_on_hours > 0:
            # Get the total cost of running the lowest hours
            total_cost = sum(values)
            logger.debug(f"Lowest cost of running {nr_of_on_hours} hours is {total_cost}")
            if total_cost <= max_total_cost or nr_of_on_hours == min_hours_to_run:
                # Found best combination of hours to run in
                # Total price is below limit or it is not possible to reduce hours to run for because of
                # min_hours_to_run
                # Return a list representing future hours, where each bool represents whether a device should be on or
                # off
                return [True if x in indices else False for x in range(hours_ahead_to_calculate)]
            # The cost was too high, run for one hour less.
            # remove the largest value of the list and try again
            index_of_largest = values.index(max(values))
            values.pop(index_of_largest)
            indices.pop(index_of_largest)
            nr_of_on_hours -= 1
        logger.debug("No valid combinations")
        # Was not possible to find cheap enough combination
        false_list = [False] * hours_ahead_to_calculate
        return false_list

    @staticmethod
    def find_n_smallest_items_in_list(items: list, n: int) -> [list, list]:
        """
        Find n number of smallest values in a list
        :param items: list of items to look in
        :param n: number of smallest values to find
        :return: 2 lists, on containing indices, the other the values of the smallest items from the original list
        """
        if n <= 0:
            return
        smallest_items = heapq.nsmallest(n, enumerate(items), key=lambda item: item[1])
        # smallest_items is a list of tupples, each tupples first value containning the item number from the original
        # list, the second one the value
        # Get 2 tuples one containing the indeces the other the values
        indices, values = zip(*smallest_items)
        return list(indices), list(values)

    @staticmethod
    def get_list_of_upcoming_prices(prices_today: dict,
                                    prices_tomorrow: dict,
                                    hours_ahead_to_calculate: int) -> [int, list]:
        """
        Get a list of the upcoming prices from today's and tomorrow's price dictionarries
        :param prices_today: dictionary with keys 0...23 holding electricity prices for each hour today
        :param prices_tomorrow: dictionary with keys 0...23 holding electricity prices for each hour tomorrow
        :param hours_ahead_to_calculate: for how many hours ahead to get the prices
        :return:
        """
        # get the number of the next hour, will be needed when returning schedule dictionaries
        next_hour = datetime.datetime.now().hour + 1
        logger.debug(f"Schedule start hour is {next_hour}")
        # How many prices for each hour from today's dictionary
        hours_from_today = min(hours_ahead_to_calculate, 24 - next_hour)
        # How many prices for each hour from tomorrow's dictionary
        hours_from_tomorrow = min(hours_ahead_to_calculate - hours_from_today, 24)
        # list of future prices from today
        today_hours = [prices_today[next_hour + i] for i in range(hours_from_today)]
        # list of future prices from tomorrow
        tomorrow_hours = [prices_tomorrow[i] for i in range(hours_from_tomorrow)]
        # combine todays and tomorrows list
        future_hours = today_hours + tomorrow_hours
        return next_hour, future_hours


if __name__ == '__main__':
    test()
