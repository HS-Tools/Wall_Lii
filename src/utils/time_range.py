from datetime import datetime, timedelta
import pytz

class TimeRangeHelper:
    @staticmethod
    def now_la():
        return datetime.now(pytz.timezone("America/Los_Angeles"))

    @staticmethod
    def start_of_day_la(offset: int = 0):
        """
        Returns the start of the day `offset` days ago in UTC.
        offset = 0 => today
        offset = 1 => yesterday
        """
        now = TimeRangeHelper.now_la()
        start = now.replace(hour=0, minute=0, second=0, microsecond=0) - timedelta(days=offset)
        return start.astimezone(pytz.utc)

    @staticmethod
    def start_of_week_la(offset: int = 0):
        """
        Returns the start of the week `offset` weeks ago in UTC.
        offset = 0 => current week
        offset = 1 => last week
        """
        now = TimeRangeHelper.now_la()
        start_of_week = now - timedelta(days=now.weekday())  # Go back to Monday
        start = start_of_week.replace(hour=0, minute=0, second=0, microsecond=0) - timedelta(weeks=offset)
        return start.astimezone(pytz.utc)