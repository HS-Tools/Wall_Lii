import api
import data
from predictions import Predictions
from dotenv import load_dotenv
import os

def add_leaderboards_to_db(database, *args):
    tup = api.getLeaderboardSnapshot(*args)
    snapshot = tup[0]

    handlePredictions(database, snapshot, 'dog', 'US')

    for region in snapshot.keys():
        database.put_items(region, snapshot[region])

def handlePredictions(database, snapshot, name, region):
    client_id = os.environ['CLIENT_ID']
    access_token = os.environ['ACCESS_TOKEN']

    predictions = Predictions(client_id, access_token)

    # Automatic prediction module
    lii_rating = database.get_item(region, name)['Ratings'][-1]
    
    # Rating gain
    if int(lii_rating) > int(snapshot[region][name]['rating']):
        predictions.run(True)
    # Rating loss
    if int(lii_rating) < int(snapshot[region][name]['rating']):
        predictions.run(False)

def handler(event, context):
    load_dotenv()
    
    database = data.RankingDatabaseClient()
    add_leaderboards_to_db(database)


