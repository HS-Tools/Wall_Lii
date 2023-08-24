import json
from concurrent.futures import as_completed
from datetime import datetime

from requests_futures.sessions import FuturesSession


def parseSnapshot(text, verbose=False, region="Unknown"):
    output = {}

    JSON = json.loads(text)
    season = JSON["seasonId"]
    accounts = JSON["leaderboard"]["rows"]
    updatedTime = datetime.now().strftime("%Y-%m-%d %H:%M:%S.%f")

    if verbose:
        print(f"{region} fetched at {updatedTime} for season {season}")

    for account in accounts:
        if verbose:
            print(f"\t{account}")

        if account != None and account["accountid"] != None:
            name = account["accountid"].encode("utf-8").lower().decode("utf-8")
            output[name] = {"rank": account["rank"], "rating": account["rating"]}

    return output, updatedTime, season


def getLeaderboardSnapshot(
    regions=["US", "EU", "AP"],
    gameMode="BG",
    season=10,
    verbose=False,
    total_count=1000,
):
    PLAYERS_PER_PAGE = 25
    ratingsDict = {region: {} for region in regions}
    updatedDict = {region: None for region in regions}  # replace None with current time

    # game mode key changed from BG to battlegrounds
    if gameMode == "BG":
        gameMode = "battlegrounds"

    for region in regions:
        username_set = {""}

        ## not supplying season always gets latest
        apiUrl = f"https://hearthstone.blizzard.com/en-us/api/community/leaderboardsData?region={region}&leaderboardId={gameMode}"
        if season != None:  ## used for test code to pull a known season results
            apiUrl = f"{apiUrl}&seasonId={season}"

        pageUrls = []
        for page in range(1, (total_count // PLAYERS_PER_PAGE) + 1):
            pageUrls.append(f"{apiUrl}&page={page}")

        with FuturesSession() as session:
            futures = [session.get(url) for url in pageUrls]
            for future in as_completed(futures):
                r = future.result()
                rDict, updatedDict[region], season = parseSnapshot(
                    r.text, verbose, region
                )
                for key in rDict:
                    if key not in username_set:
                        username_set.add(key)
                        ratingsDict[region][key] = rDict[key]

    return ratingsDict, updatedDict, season


if __name__ == "__main__":  ## run the function if this program is called
    ratingsDict, lastUpdated, season = getLeaderboardSnapshot()
    # for region in ["US", "EU", "AP"]:
    #     for account in ratingsDict[region].keys():
    #         print("\t", ratingsDict[region][account])
