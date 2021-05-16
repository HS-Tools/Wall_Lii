import requests
import json

def getLeaderboardSnapshot(regions = ['US', 'EU', 'AP'], gameMode = 'BG'):
    ratingsDict = {region : {} for region in regions}

    for region in regions:
        apiUrl = f'https://playhearthstone.com/en-us/api/community/leaderboardsData?region={region}&leaderboardId={gameMode}'
        r = requests.get(apiUrl)

        jsonStr = json.loads(r.text)
        season = jsonStr['seasonId']
        accounts = jsonStr['leaderboard']['rows']
        lastUpdated = " ".join(jsonStr['leaderboard']['metadata']['last_updated_time'].split(' ')[0:2])

        print(f'{region} fetched at {lastUpdated}')

        for account in accounts:
            print(f'\t{account}')
            name = account['accountid'].encode('utf-8').lower() # Why is this converted to bytes?
            ratingsDict[region][name] = {'rank': account['rank'], 'rating': account['rating']}

    return (ratingsDict, lastUpdated)

if __name__ == '__main__':
    getLeaderboardSnapshot(['US'])
    getLeaderboardSnapshot(['AP', 'EU'])
    getLeaderboardSnapshot()
