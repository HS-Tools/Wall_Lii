import api
import data
from predictions import Predictions
from dotenv import load_dotenv
import os

REGIONS = ['US', 'EU', 'AP']

def add_leaderboards_to_db(database, *args):
    tup = api.getLeaderboardSnapshot(*args)
    snapshot = tup[0]
    timeSnapshot = tup[1]
    timeDB = {}

    for region in snapshot:
        timeDB[region] = database.get_time(region)
        timeSnapshot[region] = database.parse_time(timeSnapshot[region])
        if timeSnapshot[region] >= timeDB[region]: ## allow equal time for easy testing
            database.put_time(region, timeSnapshot[region])
            database.put_items(region, snapshot[region])

    return snapshot, timeSnapshot, timeDB

def handlePredictions(previous_rating, new_rating, channel_name, client_id, access_token, twitch_id):
    predicter = Predictions(channel_name, twitch_id, client_id, access_token)
    # Rating gain
    if new_rating > previous_rating:
        predicter.run(True)
    # Rating loss
    elif new_rating < previous_rating:
        predicter.run(False)
    # No Rating Change
    else:
        pass # no way to determine if a 0 mmr game occured

def handler(event, context):
    load_dotenv()

    prediction_channels = { ## idealy this would be stored in the channel table
        'lii':{
            'channel_name':'liihs',
            'client_id':os.environ['CLIENT_ID'],
            'access_token':os.environ['ACCESS_TOKEN'],
            'twitch_id':os.environ['LII_TWITCH_ID']
            },
        'diyingli':{
            'channel_name':'sunbaconrelaxer',
            'client_id':os.environ['VICTOR_CLIENT_ID'],
            'access_token':os.environ['VICTOR_ACCESS_TOKEN'],
            'twitch_id':os.environ['VICTOR_TWITCH_ID']
            },
        'twlevewinshs':{
            'channel_name':'sunbaconrelaxer',
            'client_id':os.environ['VICTOR_CLIENT_ID'],
            'access_token':os.environ['VICTOR_ACCESS_TOKEN'],
            'twitch_id':os.environ['VICTOR_TWITCH_ID']
            },
    }
    
    database = data.RankingDatabaseClient()

    ## check for previous reading
    for name in prediction_channels:
        for region in REGIONS:
            item = database.get_item(region, name)
            if item is None:
                prediction_channels[region] = 0
            else:
                prediction_channels[region] = item['Ratings'][-1] ## last item


    snapshot, timeSnapshot, timeDB = add_leaderboards_to_db(database, verbose=False)

    for name in prediction_channels:
        for region in snapshot:
            if timeSnapshot[region] >= timeDB[region] and name in snapshot[region]: ## wierd edge case if you fall off the leaderboard
                handlePredictions(prediction_channels[name][region], snapshot[region][name],
                    prediction_channels['channel_name'], prediction_channels['client_id'],
                    prediction_channels['access_token'], prediction_channels['twitch_id'])


