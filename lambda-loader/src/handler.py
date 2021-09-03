import api
import data
from predictions import Predictions
from dotenv import load_dotenv
import os

def add_leaderboards_to_db(database):
    tup = api.getLeaderboardSnapshot(verbose=False)
    snapshot = tup[0]
    lastUpdated = tup[1]

    for region in snapshot.keys():
        timeLast = database.get_time(region)
        timeCurrent = database.parse_time(lastUpdated[region])
        if timeCurrent >= timeLast: ## allow equal time for easy testing
            client_id = os.environ['CLIENT_ID']
            access_token = os.environ['ACCESS_TOKEN']
            twitch_id = os.environ['LII_TWITCH_ID']

            victor_client_id = os.environ['VICTOR_CLIENT_ID']
            victor_access_token = os.environ['VICTOR_ACCESS_TOKEN']
            victor_channel_id = os.environ['VICTOR_TWITCH_ID']

            handlePredictions(database, snapshot, 'liihs', 'lii', region, client_id, access_token, twitch_id, 60)
            handlePredictions(database, snapshot, 'sunbaconrelaxer', 'diyingli', region, victor_client_id, victor_access_token, victor_channel_id, 120)
            handlePredictions(database, snapshot, 'sunbaconrelaxer', 'twlevewinshs', region, victor_client_id, victor_access_token, victor_channel_id, 120)

            database.put_time(region, timeCurrent)
            database.put_items(region, snapshot[region])

def handlePredictions(database, snapshot, channel_name, name, region, client_id, access_token, twitch_id, ad_time):
    predicter = Predictions(channel_name, twitch_id, client_id, access_token, ad_time)

    try:
        # Automatic prediction module
        rating = database.get_item(region, name)['Ratings'][-1]
        
        # Rating gain
        if int(snapshot[region][name]['rating'] > rating):
            predicter.run(True)
        # Rating loss
        if int(snapshot[region][name]['rating'] < rating):
            predicter.run(False)
    except:
        pass
        #print(f"Failed to get {name}'s data from snapshot or database from {region}, probably because they are not on leaderboard")

def handler(event, context):
    load_dotenv()
    
    database = data.RankingDatabaseClient()
    add_leaderboards_to_db(database)

