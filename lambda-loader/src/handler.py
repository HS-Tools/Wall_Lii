import api
import data
import os

TABLE_NAME = os.environ.get('TABLE_NAME')
database = data.RankingDatabaseClient(TABLE_NAME)

def handler(event, context):
    tup = api.getLeaderboardSnapshot(verbose=True) ## call and log the results to stdout
    snapshot = tup[0]
    lastUpdated = tup[1]

    for region in snapshot.keys():
        for player in snapshot[region].keys():
            rating = snapshot[region][player]['rating']
            rank = snapshot[region][player]['rank']
            player = player.decode('utf-8')
            database.put_item(region=region,player=player,rating=rating,rank=rank, lastUpdate=lastUpdated[region])

