import requests
import os
from dotenv import load_dotenv

PREDICTIONS_URL = 'https://api.twitch.tv/helix/predictions'
STREAMS_URL = 'https://api.twitch.tv/helix/streams'

class Predictions:
  def __init__(self, channel_name, broadcaster_id, client_id, access_token, ad_time=60):
    self.client_id = client_id
    self.access_token = access_token
    self.channel_name = channel_name
    self.broadcaster_id = broadcaster_id
    self.ad_time = ad_time

    self.headers = {
      'Authorization': 'Bearer {}'.format(self.access_token),
      'Client-Id': self.client_id
    }

    self.create_body = {
      'broadcaster_id': self.broadcaster_id,
      'title': f'Will {self.channel_name} Gain MMR?',
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
      'broadcaster_id': self.broadcaster_id,
      'id': prediction_id,
      'status': status,
      'winning_outcome_id': result_id
    }
    r = requests.patch(url=PREDICTIONS_URL, json=body, headers=self.headers)

    print(r.text)

  def check_if_live(self):
    url = f"{STREAMS_URL}?user_login={self.channel_name}" 
    r = requests.get(url=url, headers=self.headers)

    if len(r.json()['data']) > 0:
      return True
    else:
      return False
  
  def get_current_prediction(self):
    r = requests.get(f"{PREDICTIONS_URL}?broadcaster_id={self.broadcaster_id}", headers=self.headers)
    last_prediction = r.json()['data'][0]
    status = last_prediction['status']

    print(last_prediction)

    if status == 'ACTIVE' or status == 'LOCKED':
      return last_prediction
    else:
      return -1

  def start_ad(self):
    AD_URL = 'https://api.twitch.tv/helix/channels/commercial'
    data = {
      'broadcaster_id': self.broadcaster_id,
      'length': self.ad_time
    }

    r = requests.post(url=AD_URL, headers=self.headers ,json=data)

    print(r.text)

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

    # Start a new prediction and run ad
    if self.check_if_live():
      self.start_ad()
      self.create_prediction()
    else:
      print(f"Didn't start prediction cause {self.channel_name} isn't live")

# load_dotenv()

# client_id = os.environ['CLIENT_ID']
# access_token = os.environ['ACCESS_TOKEN']
# channel_id = os.environ['LII_TWITCH_ID']

# p = Predictions('liihs', channel_id, client_id, access_token)

# p.start_ad()

# p.create_prediction()

# predictions = Predictions(client_id, access_token)
# predictions.get_current_prediction()

# predictions.run(True)
