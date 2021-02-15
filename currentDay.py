from datetime import datetime
from pytz import timezone

def getCurrentDay():
    fmt = '%Y-%m-%d'
    tz = timezone('EST')

    return datetime.now(tz).strftime(fmt)