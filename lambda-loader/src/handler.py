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
            handlePredictions(database, snapshot, 'liihs', 'lii', region)

            database.put_time(region, timeCurrent)
            database.put_items(region, snapshot[region])

def handlePredictions(database, snapshot, channel_name, name, region):
    client_id = os.environ['CLIENT_ID']
    access_token = os.environ['ACCESS_TOKEN']
    lii_twitch_id = os.environ['LII_TWITCH_ID']

    predicter = Predictions(channel_name, lii_twitch_id, client_id, access_token)

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

