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
            database.put_item(region, player.decode('utf-8'), rating)
            print(player.decode('utf-8'),region,rating)
            database.put_item(region=region,player=player,rating=rating)

