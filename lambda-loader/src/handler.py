import api
import data
import os

def add_leaderboards_to_db(database, *args):
    tup = api.getLeaderboardSnapshot(*args)
    snapshot = tup[0]
    lastUpdated = tup[1]

    for region in snapshot.keys():
        timeLast = database.get_time(region)
        timeCurrent = database.parse_time(lastUpdated[region])
        if timeCurrent >= timeLast: ## allow equal time for easy testing
            database.put_time(region, timeCurrent)
            database.put_items(region, snapshot[region])

def handler(event, context):
    database = data.RankingDatabaseClient()
    add_leaderboards_to_db(database)

