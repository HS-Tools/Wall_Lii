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
    """Get leaderboard data with parallel fetching and pagination."""
    base_url = "https://hearthstone.blizzard.com/en-us/api/community/leaderboardsData"
    regions = ["US", "EU", "AP"] if region is None else [region]
    max_players = 100  # Fetch top 1000 players
    season_id = 13

    all_data = {}
    session = FuturesSession(max_workers=3)  # One worker per region
    region_futures = {}

    # Start all region fetches in parallel
    for r in regions:
        region_futures[r] = {
            'players': {},
            'name_counts': defaultdict(int),
            'page': 1,
            'futures': [],
            'processed_pages': set()  # Track which pages we've processed
        }
        # Queue first page for each region
        url = f"{base_url}?region={r}&leaderboardId={game_type}&seasonId={season_id}&page=1"
        region_futures[r]['futures'].append((1, session.get(url)))  # Store page number with future

    # Process responses as they complete
    while region_futures:
        completed_regions = []
        for r in list(region_futures.keys()):
            if r in completed_regions:  # Skip if region already completed
                continue
                
            region_data = region_futures[r]
            
            # Process any completed futures
            completed_futures = []
            for page_num, future in region_data['futures']:
                if future.done():
                    completed_futures.append((page_num, future))
                    try:
                        # Skip if we've already processed this page
                        if page_num in region_data['processed_pages']:
                            continue
                        region_data['processed_pages'].add(page_num)

                        response = future.result()
                        if response.status_code == 429:  # Rate limited
                            retry_after = int(response.headers.get("Retry-After", 60))
                            logger.warning(f"Rate limited on {r}, waiting {retry_after}s")
                            time.sleep(retry_after)
                            # Requeue the request
                            url = response.request.url
                            region_data['futures'].append((page_num, session.get(url)))
                            continue

                        response.raise_for_status()
                        players = response.json().get("leaderboard", {}).get("rows", [])
                        
                        if not players:  # No more players on this page
                            completed_regions.append(r)
                            all_data[r] = {game_type: region_data['players']}
                            logger.info(f"Completed {r} - Total Players: {len(region_data['players'])}")
                            break

                        # Process players from this page (only once)
                        processed_players = set()  # Track players we've seen
                        for account in players:
                            if account and account["accountid"]:
                                player_id = account["accountid"].lower()
                                if player_id in processed_players:
                                    continue  # Skip if we've seen this player
                                processed_players.add(player_id)
                                rank = account["rank"]
                                if rank > max_players:  # Only break if we've exceeded max_players
                                    completed_regions.append(r)
                                    all_data[r] = {game_type: region_data['players']}
                                    logger.info(f"Completed {r} - Total Players: {len(region_data['players'])}")
                                    break

                                base_name = account["accountid"].encode("utf-8").lower().decode("utf-8")
                                region_data['name_counts'][base_name] += 1
                                name = (f"{base_name}{region_data['name_counts'][base_name]}" 
                                       if region_data['name_counts'][base_name] > 1 else base_name)

                                region_data['players'][name] = {
                                    "rank": rank,
                                    "rating": account["rating"],
                                }

                                # Only log if it's lii
                                if account["accountid"].lower() == "lii":
                                    logger.info(f"Found lii in {r}: MMR={account['rating']}, Rank={account['rank']}")

                        # Queue next page if needed
                        if len(region_data['players']) < max_players:  # Remove rank check here
                            region_data['page'] += 1
                            url = f"{base_url}?region={r}&leaderboardId={game_type}&seasonId={season_id}&page={region_data['page']}"
                            region_data['futures'].append((region_data['page'], session.get(url)))

                    except requests.exceptions.RequestException as e:
                        logger.error(f"Error fetching {r} leaderboard: {e}")
                        completed_regions.append(r)
                        break

            # If region is complete, log final count
            if r in completed_regions:
                logger.info(f"Completed {r} - Total Players: {len(region_data['players'])}")

    logger.info(f"All regions completed for {game_type}")
    return all_data


if __name__ == "__main__":  ## run the function if this program is called
    ratingsDict = getLeaderboardSnapshot()
    print(ratingsDict)
