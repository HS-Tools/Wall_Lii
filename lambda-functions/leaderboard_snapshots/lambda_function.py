import os
import json
import asyncio
import aiohttp
from datetime import datetime, timezone
from psycopg2.extras import execute_values
from logger import setup_logger
from db_utils import get_db_connection
from config import TABLES

# Set up logger
logger = setup_logger("leaderboard_snapshots")

# Configs
REGIONS = ["US", "EU", "AP"]
MODES = [("battlegrounds", 0), ("battlegroundsduo", 1)]
REGION_MAPPING = {"US": "NA", "EU": "EU", "AP": "AP"}
BASE_URL = "https://hearthstone.blizzard.com/en-us/api/community/leaderboardsData"
CURRENT_SEASON = int(os.environ.get("CURRENT_SEASON", "15"))
MILESTONE_START = int(os.environ.get("MILESTONE_START", "8000"))
MILESTONE_INCREMENT = int(os.environ.get("MILESTONE_INCREMENT", "1000"))
MAX_PAGES = int(os.environ.get("MAX_PAGES", "40"))


async def fetch_page(session, params, sem, retries=3):
    """Fetch a single page of leaderboard data with retries"""
    backoff = 1
    async with sem:
        for attempt in range(retries):
            try:
                async with session.get(BASE_URL, params=params) as response:
                    if response.status == 200:
                        return await response.json()
                    logger.warning(f"Failed {params}: Status {response.status}")
            except Exception as e:
                logger.error(f"Error {params}: {str(e)}")
            if attempt < retries - 1:
                await asyncio.sleep(backoff)
                backoff *= 2
        return None


async def fetch_leaderboards(max_pages=MAX_PAGES):
    """Fetch leaderboard data from all regions and modes"""
    players = []
    sem = asyncio.Semaphore(10)

    # Fetch data from global regions (US, EU, AP)
    async with aiohttp.ClientSession() as session:
        tasks = []
        for mode_api, mode_short in MODES:
            for api_region in REGIONS:
                for page in range(1, max_pages + 1):
                    params = {
                        "region": api_region,
                        "leaderboardId": mode_api,
                        "seasonId": str(CURRENT_SEASON),
                        "page": page,
                    }
                    tasks.append(
                        (
                            REGION_MAPPING[api_region],
                            mode_short,
                            fetch_page(session, params, sem),
                        )
                    )

        results = await asyncio.gather(*[t[2] for t in tasks])
        for (region, mode, _), result in zip(tasks, results):
            if result and "leaderboard" in result:
                for row in result["leaderboard"].get("rows", []):
                    if row and row.get("accountid"):
                        players.append(
                            {
                                "player_name": row["accountid"].lower(),
                                "game_mode": mode,
                                "region": region,
                                "rank": row["rank"],
                                "rating": row["rating"],
                                "snapshot_time": datetime.now(timezone.utc).isoformat(),
                            }
                        )

    # Fetch data from China region
    async with aiohttp.ClientSession() as session:
        cn_tasks = []
        cn_pages = 20  # Only need 4 pages for CN region (500 players total)

        for mode_short, mode_name in [(0, "battlegrounds"), (1, "battlegroundsduo")]:
            for page in range(1, cn_pages + 1):
                url = f"https://webapi.blizzard.cn/hs-rank-api-server/api/game/ranks"
                params = {
                    "page": page,
                    "page_size": 25,
                    "mode_name": mode_name,
                    "season_id": str(CURRENT_SEASON),
                }
                cn_tasks.append((mode_short, fetch_cn_page(session, url, params, sem)))

        cn_results = await asyncio.gather(*[t[1] for t in cn_tasks])

        for (mode, _), result in zip(cn_tasks, cn_results):
            if (
                result
                and result.get("code") == 0
                and "data" in result
                and "list" in result["data"]
            ):
                for row in result["data"]["list"]:
                    players.append(
                        {
                            "player_name": row["battle_tag"].lower(),
                            "game_mode": mode,
                            "region": "CN",
                            "rank": row["position"],
                            "rating": row["score"],
                            "snapshot_time": datetime.now(timezone.utc).isoformat(),
                        }
                    )

    logger.info(f"Fetched {len(players)} players from all regions including CN")
    return _make_names_unique(players)


async def fetch_cn_page(session, url, params, sem, retries=3):
    """Fetch a single page of leaderboard data from CN API with retries"""
    backoff = 1
    async with sem:
        for attempt in range(retries):
            try:
                async with session.get(url, params=params) as response:
                    if response.status == 200:
                        return await response.json()
                    logger.warning(f"Failed CN {params}: Status {response.status}")
            except Exception as e:
                logger.error(f"Error CN {params}: {str(e)}")
            if attempt < retries - 1:
                await asyncio.sleep(backoff)
                backoff *= 2
        return None


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


def write_to_postgres(players):
    """Write player data to the database and process milestones"""
    insert_query = f"""
        INSERT INTO {TABLES['leaderboard_snapshots']} (player_name, game_mode, region, rank, rating, snapshot_time)
        VALUES %s
    """
    values = [
        (
            p["player_name"],
            p["game_mode"],
            p["region"],
            p["rank"],
            p["rating"],
            p["snapshot_time"],
        )
        for p in players
    ]

    conn = None
    try:
        conn = get_db_connection()
        with conn:
            with conn.cursor() as cur:
                execute_values(cur, insert_query, values, page_size=100)
                logger.info(f"Inserted {len(players)} players.")

                # Process milestones after inserting player data
                process_milestones(cur, players)
    except Exception as e:
        logger.error(f"Error inserting into DB: {str(e)}")
        raise
    finally:
        if conn:
            conn.close()


def process_milestones(cursor, players):
    """Process rating milestones and insert into milestone_tracking table"""
    try:
        # Get existing milestones
        cursor.execute(
            f"""
            SELECT region, game_mode, milestone 
            FROM {TABLES['milestone_tracking']} 
            WHERE season = %s
        """,
            (CURRENT_SEASON,),
        )

        existing_milestones = set()
        for row in cursor.fetchall():
            existing_milestones.add(f"{row[0]}#{row[1]}#{row[2]}")

        # Group players by region and game_mode
        region_mode_players = {}
        for player in players:
            key = f"{player['region']}#{player['game_mode']}"
            if key not in region_mode_players:
                region_mode_players[key] = []
            region_mode_players[key].append(player)

        # Find highest rated player for each region/mode
        milestones_to_insert = []
        now = datetime.now(timezone.utc)

        for key, players_list in region_mode_players.items():
            region, game_mode = key.split("#")
            # Sort by rating (highest first)
            sorted_players = sorted(
                players_list, key=lambda p: p["rating"], reverse=True
            )

            if not sorted_players:
                continue

            # Get highest rated player
            top_player = sorted_players[0]
            top_rating = top_player["rating"]

            # Calculate all milestones this player has achieved
            milestone = MILESTONE_START
            while milestone <= top_rating:
                milestone_key = f"{region}#{game_mode}#{milestone}"

                # Check if this milestone already exists
                if milestone_key not in existing_milestones:
                    milestones_to_insert.append(
                        {
                            "season": CURRENT_SEASON,
                            "game_mode": game_mode,
                            "region": region,
                            "milestone": milestone,
                            "player_name": top_player["player_name"],
                            "timestamp": now,
                            "rating": top_rating,
                        }
                    )

                milestone += MILESTONE_INCREMENT

        # Insert new milestones
        if milestones_to_insert:
            # Use ON CONFLICT DO NOTHING to handle duplicates gracefully
            milestone_insert_query = f"""
                INSERT INTO {TABLES['milestone_tracking']}
                (season, game_mode, region, milestone, player_name, timestamp, rating)
                VALUES %s
                ON CONFLICT (season, game_mode, region, milestone) DO NOTHING
            """
            milestone_values = [
                (
                    m["season"],
                    m["game_mode"],
                    m["region"],
                    m["milestone"],
                    m["player_name"],
                    m["timestamp"],
                    m["rating"],
                )
                for m in milestones_to_insert
            ]

            execute_values(cursor, milestone_insert_query, milestone_values)
            logger.info(f"Processed {len(milestones_to_insert)} milestones.")

    except Exception as e:
        logger.error(f"Error processing milestones: {e}")
        raise


async def process_leaderboards():
    """Main function to fetch and process leaderboard data"""
    logger.info("Fetching leaderboard data...")
    players = await fetch_leaderboards()
    logger.info(f"Fetched {len(players)} players.")
    write_to_postgres(players)
    return len(players)


def lambda_handler(event, context):
    """AWS Lambda entry point"""
    try:
        players_count = asyncio.run(process_leaderboards())
        return {
            "statusCode": 200,
            "body": json.dumps(
                {
                    "message": "Leaderboard snapshots processed successfully",
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
