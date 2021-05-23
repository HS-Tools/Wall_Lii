import api
import data
import os

def add_leaderboards_to_db(database, *args):
    tup = api.getLeaderboardSnapshot(*args)
    snapshot = tup[0]
    lastUpdated = tup[1]

    for region in snapshot.keys():
        database.put_items(region, snapshot[region])

def handler(event, context):
    database = data.RankingDatabaseClient()
    add_leaderboards_to_db(database)


