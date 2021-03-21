import api 
import data
import os

TABLE_NAME = os.environ.get('TABLE_NAME')
REGIONS = ['US','EU','AP']
database = data.RankingDatabaseClient(TABLE_NAME)

def handler(event, context):
    snapshot = api.getLeaderboardSnapshot()
    for region in REGIONS:
        for player in snapshot[region].keys(): # ???
            rating = snapshot[region][player]['rating']
            rank = snapshot[region][player]['rank']
            database.put_item(region, player.decode('utf-8'), rating)
            player = player.decode('utf-8')
            database.put_item(region=region,player=player,rating=rating,rank=rank)

