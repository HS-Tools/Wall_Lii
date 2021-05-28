import requests
import os
from dotenv import load_dotenv

PREDICTIONS_URL = 'https://api.twitch.tv/helix/predictions'
STREAMS_URL = 'https://api.twitch.tv/helix/streams'
LII_TWITCH_ID = '73626243'

class Predictions:
  def __init__(self, client_id, access_token):
    self.client_id = client_id
    self.access_token = access_token

    self.headers = {
      'Authorization': 'Bearer {}'.format(self.access_token),
      'Client-Id': self.client_id
    }

    self.create_body = {
      'broadcaster_id': LII_TWITCH_ID,
      'title': 'Will lii Gain MMR?',
      'outcomes': [
        { 'title': 'YEP.' },
        { 'title': 'NOP.' }
      ],
      'prediction_window': 120
    }
  
  def create_prediction(self, body="default"):

    if body == "default":
      body = self.create_body

    r = requests.post(url=PREDICTIONS_URL, json=body, headers=self.headers)

    obj = r.json()
    print(obj)

    if (r.status_code == 200):
      return {
        'id': obj['data'][0]['id'],
        'outcome_ids': [obj['data'][0]['outcomes'][0]['id'], obj['data'][0]['outcomes'][1]['id']]
      }
    else:
      return -1

  def end_prediction(self, prediction_id, status, result_id):
    body = {
      'broadcaster_id': LII_TWITCH_ID,
      'id': prediction_id,
      'status': status,
      'winning_outcome_id': result_id
    }
    r = requests.patch(url=PREDICTIONS_URL, json=body, headers=self.headers)

    print(r.text)

  def check_if_live(self, channel_name='liihs'):
    url = f"{STREAMS_URL}?user_login={channel_name}" 
    r = requests.get(url=url, headers=self.headers)

    if len(r.json()['data']) > 0:
      return True
    else:
      return False
  
  def get_current_prediction(self):
    r = requests.get(f"{PREDICTIONS_URL}?broadcaster_id={LII_TWITCH_ID}", headers=self.headers)
    last_prediction = r.json()['data'][0]
    status = last_prediction['status']

    print(last_prediction)

    if status == 'ACTIVE' or 'LOCKED':
      return last_prediction
    else:
      return -1

  def run(self, isGain):
    current_prediction = self.get_current_prediction()

    # Resolve current prediction if there is one
    if current_prediction != -1:
      prediction_id = current_prediction['id']
      gain_id = current_prediction['outcomes'][0]['id']
      lose_id = current_prediction['outcomes'][1]['id']

      if isGain:
        self.end_prediction(prediction_id, 'RESOLVED', gain_id)
        print('Ended prediction with gain')
      else:
        self.end_prediction(prediction_id, 'RESOLVED', lose_id)
        print('Ended prediction with loss')
    else:
      print('No current prediction')

    # Start a new prediction
    self.create_prediction()
    
# delete_body = {
#   'broadcaster_id': '73626243',
#   'id': id,
#   'status': 'RESOLVED',
#   'winning_outcome_id': id
# }

#requests.post(f"https://id.twitch.tv/oauth2/revoke?client_id={CLIENT_ID}&token={ACCESS_TOKEN}")
load_dotenv()

client_id = os.environ['CLIENT_ID']
access_token = os.environ['ACCESS_TOKEN']

predictions = Predictions(client_id, access_token)

predictions.run(True)

# prediction_obj = create_prediction(create_body, headers)
# prediction_id = prediction_obj['id']
# outcome_ids = prediction_obj['outcome_ids']
# time.sleep(150)

# end_prediction(prediction_id, 'RESOLVED', outcome_ids[0], headers)