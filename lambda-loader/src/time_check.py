import api
import time
from datetime import date, datetime

while True:
  # print('Current Time: ' + datetime.now().strftime('%H:%M:%S'))
  api_time_with_microseconds_removed = api.getLeaderboardSnapshot(verbose=False)[1]['US'].split('.')[0]
  api_time = datetime.strptime(api_time_with_microseconds_removed, '%Y-%m-%d %H:%M:%S')
  print('API Time: ' + api_time.strftime('%H:%M:%S'))
  time.sleep(60)