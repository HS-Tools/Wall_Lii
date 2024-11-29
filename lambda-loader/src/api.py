import json
from collections import defaultdict
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
            output[name] = {
                "rank": account["rank"],
                "rating": account["rating"],
                # "lastUpdated": updatedTime,
            }

    return output


def getLeaderboardSnapshot(
    regions=["US", "EU", "AP"],
    gameModes=["battlegrounds", "battlegroundsduo"],
    season=13,
    verbose=False,
    total_count=25,
):
    PLAYERS_PER_PAGE = 25
    ratingsDict = {region: {mode: {} for mode in gameModes} for region in regions}
    # updatedDict = {region: {mode: None for mode in gameModes} for region in regions}  # replace None with current time
    name_count = {
        region: defaultdict(int) for region in regions
    }  # Track name counts per region

    for region in regions:
        for gameMode in gameModes:
            apiUrl = f"https://hearthstone.blizzard.com/en-us/api/community/leaderboardsData?region={region}&leaderboardId={gameMode}"
            if season is not None:  # Used for test code to pull known season results
                apiUrl = f"{apiUrl}&seasonId={season}"

            # Generate page URLs for each mode
            pageUrls = [
                f"{apiUrl}&page={page}"
                for page in range(1, (total_count // PLAYERS_PER_PAGE) + 1)
            ]

            with FuturesSession() as session:
                futures = [session.get(url) for url in pageUrls]
                for future in as_completed(futures):
                    r = future.result()

                    # Parse snapshot and validate response
                    if r.status_code == 200 and r.text:
                        rDict = parseSnapshot(r.text, verbose, region)

                        # Process leaderboard data for the current mode
                        for key, player_data in rDict.items():
                            # Apply identifier suffixing
                            base_name = key
                            if base_name in name_count[region]:
                                name_count[region][base_name] += 1
                                key = f"{base_name}{name_count[region][base_name]}"
                            else:
                                name_count[region][base_name] = 1

                            # Add game mode to player data
                            player_data["gameMode"] = gameMode

                            # Store player data if not already added
                            if key not in ratingsDict[region][gameMode]:
                                ratingsDict[region][gameMode][key] = player_data

    return ratingsDict


if __name__ == "__main__":  ## run the function if this program is called
    ratingsDict = getLeaderboardSnapshot()
    print(ratingsDict)
    # for region in ["US", "EU", "AP"]:
    #     for account in ratingsDict[region].keys():
    #         print("\t", ratingsDict[region][account])
    #         # print("\t", lastUpdated[region][account])
