import json
import time
from collections import defaultdict
from concurrent.futures import as_completed
from datetime import datetime
from typing import Dict, Optional

import requests
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
    region: str = None, game_type: str = "battlegrounds"
) -> Dict:
    """
    Get leaderboard data with rate limiting.
    If region is None, fetches all regions.
    """
    base_url = "https://hearthstone.blizzard.com/en-us/api/community/leaderboardsData"
    regions = ["US", "EU", "AP"] if region is None else [region]

    all_data = {}
    for r in regions:
        try:
            url = f"{base_url}?region={r}&leaderboardId={game_type}"
            response = requests.get(url)

            if response.status_code == 429:  # Too Many Requests
                retry_after = int(response.headers.get("Retry-After", 60))
                print(f"Rate limited. Waiting {retry_after} seconds...")
                time.sleep(retry_after)
                response = requests.get(url)  # Retry once

            response.raise_for_status()
            data = parseSnapshot(response.text, region=r)  # Parse the response

            # Add to our results
            all_data[r] = {game_type: data}

            # Voluntary rate limiting - sleep between regions
            if len(regions) > 1:
                print(f"Sleeping 2 seconds between regions...")
                time.sleep(2)

        except requests.exceptions.RequestException as e:
            print(f"Error fetching {r} leaderboard: {e}")
            continue

    return all_data


if __name__ == "__main__":  ## run the function if this program is called
    ratingsDict = getLeaderboardSnapshot()
    print(ratingsDict)
    # for region in ["US", "EU", "AP"]:
    #     for account in ratingsDict[region].keys():
    #         print("\t", ratingsDict[region][account])
    #         # print("\t", lastUpdated[region][account])
