import requests
import json


def parseSnapshot(text, verbose=True, region='Unknown'):
    output = {}

    JSON = json.loads(text)
    season = JSON['seasonId']
    accounts = JSON['leaderboard']['rows']
    updatedTime = " ".join(JSON['leaderboard']['metadata']['last_updated_time'].split(' ')[0:2])

    if verbose: print(f'{region} fetched at {updatedTime}')

    for account in accounts:
        if verbose: print(f'\t{account}')
        name = account['accountid'].encode('utf-8').lower().decode('utf-8')
        output[name] = {'rank': account['rank'], 'rating': account['rating']}

    return output, updatedTime, season

def getLeaderboardSnapshot(regions = ['US', 'EU', 'AP'], gameMode = 'BG', season = None, verbose = True):
    ratingsDict = {region : {} for region in regions}
    updatedDict = {region : None for region in regions}

    for region in regions:
        ## not supplying season always gets latest
        apiUrl = f'https://playhearthstone.com/en-us/api/community/leaderboardsData?region={region}&leaderboardId={gameMode}'
        if season != None: ## used for test code to pull a known season results
            apiUrl = f'{apiUrl}&seasonId={season}'
        r = requests.get(apiUrl)
        ratingsDict[region], updatedDict[region], season = parseSnapshot(r.text, verbose, region)

    return (ratingsDict, updatedDict, season)

if __name__ == '__main__': ## run the function if this program is called
    ratingsDict, lastUpdated, season = getLeaderboardSnapshot()
    for region in ['US', 'EU', 'AP']:
        print(f'{region} fetched at {updatedDict[region]}')
        for account in ratingsDict[region].keys():
            print('\t',ratingsDict[region][account])