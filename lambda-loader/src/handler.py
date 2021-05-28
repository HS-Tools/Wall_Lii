import api
import data
import predictions
import os

def add_leaderboards_to_db(database, *args):
    tup = api.getLeaderboardSnapshot(*args)
    snapshot = tup[0]

    handlePredictions(database, snapshot, 'dog', 'US')

    for region in snapshot.keys():
        database.put_items(region, snapshot[region])

def handlePredictions(database, snapshot, name, region):
    # Automatic prediction module
    lii_rating = database.get_item(region, name)['Ratings'][-1]
    
    # Rating gain
    if int(lii_rating) > int(snapshot[region][name]['rating']):
        predictions.run(True)
    # Rating loss
    if int(lii_rating) > int(snapshot[region][name]['rating']):
        predictions.run(False)

def handler(event, context):
    database = data.RankingDatabaseClient()
    add_leaderboards_to_db(database)


