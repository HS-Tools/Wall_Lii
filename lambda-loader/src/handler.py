import api 
import data
import os

TABLE_NAME = os.environ.get('TABLE_NAME')
REGIONS = ['US','EU','AP']
database = data.RankingDatabaseClient(TABLE_NAME)

def handler(event, context):
    tup = api.getLeaderboardSnapshot()
    snapshot = tup[0]
    lastUpdated = tup[1]

    for region in REGIONS:
        for player in snapshot[region].keys(): # ???
            rating = snapshot[region][player]['rating']
            rank = snapshot[region][player]['rank']
            player = player.decode('utf-8')
            database.put_item(region=region,player=player,rating=rating,rank=rank, lastUpdate=lastUpdated)

    