from datetime import datetime, date, time
from pytz import timezone

def getMidnightTTL():
    tz = timezone('US/Pacific')
    currentDate = date.today()
    midnight_without_tzinfo = datetime.combine(currentDate, time())
    midnight_with_tzinfo = tz.localize(midnight_without_tzinfo)
    midnight_as_epoch = int(midnight_with_tzinfo.timestamp())

    return midnight_as_epoch