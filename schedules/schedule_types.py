from enum import Enum


class ScheduleType(Enum):
    FAKE = 0
    HOURLY_SCHEDULE_2_DAYS = 1
    AUTO_SCHEDULE_CREATOR = 2
    DAILY_TIMED_SCHEDULE = 3