import os
import json
import asyncio
import aiohttp
from datetime import datetime, timezone
from psycopg2.extras import execute_values
import time
from logger import setup_logger
from db_utils import get_db_connection

# Set up logger
logger = setup_logger("current_leaderboard")

# Table names
CURRENT_LEADERBOARD = "current_leaderboard"

# Configs
REGIONS = ["US", "EU", "AP"]
MODES = [("battlegrounds", 0), ("battlegroundsduo", 1)]
REGION_MAPPING = {"US": "NA", "EU": "EU", "AP": "AP"}
BASE_URL = "https://hearthstone.blizzard.com/en-us/api/community/leaderboardsData"
CURRENT_SEASON = int(os.environ.get("CURRENT_SEASON", "17"))


async def fetch_all_pages(session, region, mode_api, mode_short, sem):
    """Fetch all pages for a specific region and mode"""
    players = []
    page = 1
    while True:
        params = {
            "region": region,
            "leaderboardId": mode_api,
            "seasonId": str(CURRENT_SEASON),
            "page": page,
        }
        async with sem:
            try:
                async with session.get(BASE_URL, params=params) as response:
                    if response.status == 403 or response.status == 429:
                        logger.warning(f"Rate limited for {params}. Backing off.")
                        await asyncio.sleep(60)  # wait 1 minute
                        continue  # retry same request

                    if response.status != 200:
                        logger.error(
                            f"Error fetching {params}: Status {response.status}"
                        )
                        break

                    data = await response.json()
                    rows = data.get("leaderboard", {}).get("rows", [])
                    if not rows:
                        break

                    for row in rows:
                        if row.get("accountid"):
                            players.append(
                                {
                                    "player_name": row["accountid"].lower(),
                                    "game_mode": mode_short,
                                    "region": REGION_MAPPING[region],
                                    "rank": row["rank"],
                                    "rating": row["rating"],
                                }
                            )
                    page += 1
            except Exception as e:
                logger.error(f"Error fetching {params}: {e}")
                break
    return players


async def fetch_cn_pages(session, mode_short, sem):
    """Fetch leaderboard data from CN region"""
    players = []
    cn_pages = 20  # Only need 20 pages for CN region (500 players total)
    url = "https://webapi.blizzard.cn/hs-rank-api-server/api/game/ranks"

    for page in range(1, cn_pages + 1):
        params = {
            "page": page,
            "page_size": 25,
            "mode_name": "battlegrounds" if mode_short == 0 else "battlegroundsduo",
            "season_id": str(CURRENT_SEASON),
        }
        async with sem:
            try:
                async with session.get(url, params=params) as response:
                    if response.status == 200:
                        data = await response.json()
                        if (
                            data.get("code") == 0
                            and "data" in data
                            and "list" in data["data"]
                        ):
                            for row in data["data"]["list"]:
                                players.append(
                                    {
                                        "player_name": row["battle_tag"].lower(),
                                        "game_mode": mode_short,
                                        "region": "CN",
                                        "rank": row["position"],
                                        "rating": row["score"],
                                    }
                                )
                    else:
                        logger.warning(f"Failed CN {params}: Status {response.status}")
            except Exception as e:
                logger.error(f"Error CN {params}: {e}")
    return players


async def fetch_current_leaderboards():
    """Fetch current leaderboard data from all regions and modes"""
    sem = asyncio.Semaphore(10)
    async with aiohttp.ClientSession() as session:
        tasks = []
        for mode_api, mode_short in MODES:
            for region in REGIONS:
                tasks.append(
                    fetch_all_pages(session, region, mode_api, mode_short, sem)
                )
            # Add CN region tasks
            tasks.append(fetch_cn_pages(session, mode_short, sem))

        results = await asyncio.gather(*tasks)
        players = [p for sublist in results for p in sublist]
        return _make_names_unique(players)


def _make_names_unique(players):
    """Ensure player names are unique within region and game mode"""
    seen = {}
    final = []
    for p in players:
        key = f"{p['region']}#{p['game_mode']}#{p['player_name']}"
        count = seen.get(key, 0) + 1
        seen[key] = count
        p = p.copy()
        if count > 1:
            p["player_name"] = f"{p['player_name']}_{count}"
        final.append(p)
    return final


def update_current_leaderboard(players):
    """Update the current_leaderboard table with the latest data"""
    conn = None
    try:
        conn = get_db_connection()
        with conn:
            with conn.cursor() as cur:
                cur.execute(f"TRUNCATE TABLE {CURRENT_LEADERBOARD};")
                insert_query = f"""
                    INSERT INTO {CURRENT_LEADERBOARD} (player_name, game_mode, region, rank, rating)
                    VALUES %s
                """
                values = [
                    (
                        p["player_name"],
                        p["game_mode"],
                        p["region"],
                        p["rank"],
                        p["rating"],
                    )
                    for p in players
                ]
                execute_values(cur, insert_query, values, page_size=100)
                logger.info(
                    f"Inserted {len(players)} players into current_leaderboard."
                )
                return len(players)
    except Exception as e:
        logger.error(f"Error updating current_leaderboard: {str(e)}")
        raise
    finally:
        if conn:
            conn.close()


async def process_current_leaderboard():
    """Main function to fetch and process current leaderboard data"""
    start_time = time.time()
    logger.info("Fetching current leaderboard data...")
    players = await fetch_current_leaderboards()
    logger.info(f"Fetched {len(players)} players.")
    players_count = update_current_leaderboard(players)
    end_time = time.time()
    elapsed_time = end_time - start_time
    logger.info(f"Execution time: {elapsed_time:.2f} seconds")
    return players_count


def lambda_handler(event, context):
    """AWS Lambda entry point"""
    try:
        players_count = asyncio.run(process_current_leaderboard())
        return {
            "statusCode": 200,
            "body": json.dumps(
                {
                    "message": "Current leaderboard updated successfully",
                    "players_processed": players_count,
                }
            ),
        }
    except Exception as e:
        logger.error(f"Lambda execution failed: {str(e)}")
        return {
            "statusCode": 500,
            "body": json.dumps({"message": f"Error during execution: {str(e)}"}),
        }


# For local testing
if __name__ == "__main__":
    print(lambda_handler({}, None))
