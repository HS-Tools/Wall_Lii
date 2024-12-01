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
    accounts = JSON["leaderboard"]["rows"]

    for account in accounts:
        if account != None and account["accountid"] != None:
            name = account["accountid"].encode("utf-8").lower().decode("utf-8")
            output[name] = {
                "rank": account["rank"],
                "rating": account["rating"],
            }

    return output


def getLeaderboardSnapshot(
    region: str = None, game_type: str = "battlegrounds", page_size: int = 25
) -> Dict:
    """Get leaderboard data with rate limiting and pagination."""
    base_url = "https://hearthstone.blizzard.com/en-us/api/community/leaderboardsData"
    regions = ["US", "EU", "AP"] if region is None else [region]
    max_players = 100  # Fetch top 100 players

    all_data = {}
    for r in regions:
        try:
            all_players = {}
            name_counts = defaultdict(int)  # Track count of each name
            page = 1

            while True:  # We'll break when we see ranks > 1000
                url = f"{base_url}?region={r}&leaderboardId={game_type}&page={page}"
                response = requests.get(url)

                if response.status_code == 429:  # Too Many Requests
                    retry_after = int(response.headers.get("Retry-After", 60))
                    print(f"Rate limited. Waiting {retry_after} seconds...", flush=True)
                    time.sleep(retry_after)
                    response = requests.get(url)  # Retry once

                response.raise_for_status()
                json_data = response.json()

                players = json_data.get("leaderboard", {}).get("rows", [])

                if not players:  # No more players
                    break

                # Check first player's rank on this page
                if players[0]["rank"] > max_players:
                    break

                # Add players from this page
                for account in players:
                    if account and account["accountid"]:
                        rank = account["rank"]
                        if rank > max_players:  # Stop if we've gone past 1000
                            break

                        base_name = (
                            account["accountid"].encode("utf-8").lower().decode("utf-8")
                        )
                        name_counts[base_name] += 1

                        # If this name has been seen before, append the count
                        if name_counts[base_name] > 1:
                            name = f"{base_name}{name_counts[base_name]}"
                        else:
                            name = base_name

                        all_players[name] = {
                            "rank": rank,
                            "rating": account["rating"],
                        }

                page += 1

            print(f"Debug - Total players for {r}: {len(all_players)}", flush=True)
            all_data[r] = {game_type: all_players}

        except requests.exceptions.RequestException as e:
            print(f"Error fetching {r} leaderboard: {e}")
            continue

    return all_data


if __name__ == "__main__":  ## run the function if this program is called
    ratingsDict = getLeaderboardSnapshot()
    print(ratingsDict)
