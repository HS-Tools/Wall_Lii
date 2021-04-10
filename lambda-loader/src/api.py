import requests
import json

currentSeason = 2
pages = range(1, 9)
gameMode = 'BG'
regions = ['US', 'EU', 'AP']

def getLeaderboardSnapshot():
    ratingsDict = {region : {} for region in regions}

    for region in regions:
        apiUrl = 'https://playhearthstone.com/en-us/api/community/leaderboardsData?region={}&leaderboardId={}&seasionId={}'.format(region, gameMode, currentSeason)
        r = requests.get(apiUrl)

        accounts = json.loads(r.text)['leaderboard']['rows']
        lastUpdated = json.loads(r.text)['leaderboard']['metadata']['last_updated_time']
        # To get UTC Time

        print(f'{region} fetched at {lastUpdated}')
        lastUpdated = lastUpdated.split(' ')[1].split('.')[0]

        for account in accounts:
            name = account['accountid'].encode('utf-8').lower() # Why is this converted to bytes?
            ratingsDict[region][name] = {'rank': account['rank'], 'rating': account['rating']}

    return (ratingsDict, lastUpdated)
