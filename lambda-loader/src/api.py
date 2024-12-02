import json
import time
from collections import defaultdict
from concurrent.futures import as_completed
from datetime import datetime
from typing import Dict, Optional

import requests
from requests_futures.sessions import FuturesSession

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


def getLeaderboardSnapshot(
    region: str = None, game_type: str = "battlegrounds", page_size: int = 25
) -> Dict:
    """Get leaderboard data with rate limiting and pagination."""
    base_url = "https://hearthstone.blizzard.com/en-us/api/community/leaderboardsData"
    regions = ["US", "EU", "AP"] if region is None else [region]
    max_players = 1000  # Fetch top 1000 players

    # Get current season ID for the game type
    season_id = 13  # Current season for battlegrounds/duo

    all_data = {}
    for r in regions:
        try:
            all_players = {}
            name_counts = defaultdict(int)
            page = 1

            while True:  # We'll break when we see ranks > max_players
                url = f"{base_url}?region={r}&leaderboardId={game_type}&seasonId={season_id}&page={page}"
                response = requests.get(url)

                if response.status_code == 429:  # Rate limited
                    retry_after = int(response.headers.get("Retry-After", 60))
                    logger.warning(f"Rate limited on {r}, waiting {retry_after}s")
                    time.sleep(retry_after)
                    response = requests.get(url)  # Retry once

                response.raise_for_status()
                json_data = response.json()
                players = json_data.get("leaderboard", {}).get("rows", [])

                if not players:  # No more players on this page
                    break

                # Process players from this page
                for account in players:
                    if account and account["accountid"]:
                        rank = account["rank"]
                        if rank > max_players:  # Stop if we've hit our limit
                            break

                        base_name = (
                            account["accountid"].encode("utf-8").lower().decode("utf-8")
                        )
                        name_counts[base_name] += 1
                        name = (
                            f"{base_name}{name_counts[base_name]}"
                            if name_counts[base_name] > 1
                            else base_name
                        )

                        all_players[name] = {
                            "rank": rank,
                            "rating": account["rating"],
                        }

                if rank > max_players:  # Stop pagination if we've hit our limit
                    break

                logger.info(
                    f"Processed {r} page {page} - Players so far: {len(all_players)}"
                )
                page += 1

            logger.info(
                f"Completed {r} - Total Players: {len(all_players)}, Pages: {page}"
            )
            all_data[r] = {game_type: all_players}

        except requests.exceptions.RequestException as e:
            logger.error(f"Error fetching {r} leaderboard: {e}")
            continue

    return all_data


if __name__ == "__main__":  ## run the function if this program is called
    ratingsDict = getLeaderboardSnapshot()
    print(ratingsDict)
