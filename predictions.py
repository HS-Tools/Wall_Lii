import requests
import time

CLIENT_ID = 'gp762nuuoqcoxypju8c569th9wz7q5'
ACCESS_TOKEN = '3ed3pyj7ifam7fhn3plbp9fcqr2udu'
REFRESH_TOKEN = '0ug9ct0fvlvjr1wjhtcayvtd6dq2y2scqoebi31l8lnnjq0r5o'
PREDICTIONS_URL = 'https://api.twitch.tv/helix/predictions'
STREAMS_URL = 'https://api.twitch.tv/helix/streams'
LII_TWITCH_ID = '73626243'

create_body = {
  'broadcaster_id': LII_TWITCH_ID,
  'title': 'Will lii Gain MMR?',
  'outcomes': [
    { 'title': 'YEP.' },
    { 'title': 'NOP.' }
  ],
  'prediction_window': 120
}

# delete_body = {
#   'broadcaster_id': '73626243',
#   'id': id,
#   'status': 'RESOLVED',
#   'winning_outcome_id': id
# }

headers = {
  'Authorization': 'Bearer {}'.format(ACCESS_TOKEN),
  'Client-Id': CLIENT_ID
}

def create_prediction(body, headers):
  r = requests.post(url=PREDICTIONS_URL, json=body, headers=headers)

  obj = r.json()
  print(obj)

  if (r.status_code == 200):
    return {
      'id': obj['data'][0]['id'],
      'outcome_ids': [obj['data'][0]['outcomes'][0]['id'], obj['data'][0]['outcomes'][1]['id']]
    }
  else:
    return -1


def end_prediction(prediction_id, status, result_id, headers):
  body = {
    'broadcaster_id': LII_TWITCH_ID,
    'id': prediction_id,
    'status': status,
    'winning_outcome_id': result_id
  }
  r = requests.patch(url=PREDICTIONS_URL, json=body, headers=headers)

  print(r.text)

def check_if_live(channel_name='liihs', headers=headers):
  url = f"{STREAMS_URL}?user_login={channel_name}" 
  r = requests.get(url=url, headers=headers)

  if len(r.json()['data']) > 0:
    return True
  else:
    return False

print(check_if_live())

# prediction_obj = create_prediction(create_body, headers)
# prediction_id = prediction_obj['id']
# outcome_ids = prediction_obj['outcome_ids']
# time.sleep(150)

# end_prediction(prediction_id, 'RESOLVED', outcome_ids[0], headers)