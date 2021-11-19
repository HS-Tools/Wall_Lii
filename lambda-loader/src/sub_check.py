import requests
import json
import os
from dotenv import load_dotenv

load_dotenv()

client_id = os.environ['CLIENT_ID']
access_token = os.environ['ACCESS_TOKEN']
channel_id = os.environ['LII_TWITCH_ID']

sub_url = f"https://api.twitch.tv/helix/subscriptions?broadcaster_id={channel_id}"

headers = {
  'Authorization': 'Bearer {}'.format(access_token),
  'Client-Id': client_id
}

def get_sub_page(request):
    data = request['data']
    pagination = None
    if request['pagination']:
        pagination = request['pagination']['cursor']
    usernames = []
    for user in data:
        usernames.append(user['user_name'])
    return usernames, pagination

def get_subs():
    pagination_number = ''
    pagination_param = ''
    subs = []

    while pagination_number != None:

        url = sub_url + pagination_param
        sub_request = requests.get(url=url, headers=headers)
        request_json = json.loads(sub_request.text)
        sub_page, pagination_number = get_sub_page(request_json)

        pagination_param = f"&after={pagination_number}"
        subs += sub_page
