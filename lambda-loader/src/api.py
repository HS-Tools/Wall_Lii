import json
import time
from collections import defaultdict
from datetime import datetime
from typing import Dict, Optional

import requests

from logger import setup_logger

logger = setup_logger("api")


def parseSnapshot(text, verbose=False, region="Unknown"):
    output = {}
    JSON = json.loads(text)
    accounts = JSON["leaderboard"]["rows"]

    for account in accounts:
        if account != None and account["accountid"] != None:
            name = account["accountid"].encode("utf-8").lower().decode("utf-8")
            output[name] = {
                "rank": account["rank"],
                "rating": account["rating"],
            }

    return output


def getLeaderboardSnapshot(game_type="battlegrounds", max_pages=20):
    """
    Fetch leaderboard data from Blizzard API
    """
    # Standardize region names
    region_mapping = {
        "US": "NA",  # Map US to NA
        "EU": "EU",  # Keep EU as is
        "AP": "AP",  # Keep AP as is
    }

    result = {}

    for api_region in ["US", "EU", "AP"]:
        normalized_region = region_mapping[api_region]  # Convert US to NA
        result[normalized_region] = {game_type: {}}
        players = {}
        name_counts = {}  # Track duplicate names

        for page in range(1, max_pages + 1):
            try:
                url = f"https://hearthstone.blizzard.com/en-us/api/community/leaderboardsData"
                params = {
                    "region": api_region,  # Use original region for API
                    "leaderboardId": game_type,
                    "seasonId": "14",  # Current season
                    "page": page,
                }

                response = requests.get(url, params=params)
                if response.status_code == 200:
                    data = response.json()
                    rows = data.get("leaderboard", {}).get("rows", [])

                    for row in rows:
                        if row and row.get("accountid"):
                            player_name = row["accountid"].lower()

                            # Handle duplicate names
                            if player_name in name_counts:
                                name_counts[player_name] += 1
                                player_name = f"{player_name}{name_counts[player_name]}"
                            else:
                                name_counts[player_name] = 1

                            players[player_name] = {
                                "rank": row["rank"],
                                "rating": row["rating"],
                            }

                else:
                    logger.error(
                        f"Error fetching {normalized_region} page {page}: {response.status_code}"
                    )

            except Exception as e:
                logger.error(
                    f"Error in API call for {normalized_region} page {page}: {str(e)}"
                )

        result[normalized_region][game_type] = players

    return result


if __name__ == "__main__":  ## run the function if this program is called
    ratingsDict = getLeaderboardSnapshot()
    print(ratingsDict)
