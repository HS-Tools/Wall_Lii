import os
import json
import asyncio
import aiohttp
from datetime import datetime, timezone
from psycopg2.extras import execute_values
from logger import setup_logger
from db_utils import get_db_connection
import pytz

# Set up logger
logger = setup_logger("leaderboard_snapshots")

# Table names
LEADERBOARD_SNAPSHOTS = "leaderboard_snapshots"
MILESTONE_TRACKING = "milestone_tracking"

# Configs
REGIONS = ["US", "EU", "AP"]
MODES = [("battlegrounds", 0), ("battlegroundsduo", 1)]
REGION_MAPPING = {"US": "NA", "EU": "EU", "AP": "AP"}
BASE_URL = "https://hearthstone.blizzard.com/en-us/api/community/leaderboardsData"
CURRENT_SEASON = int(os.environ.get("CURRENT_SEASON", "16"))
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
        cn_pages = 20  # Only need 20 pages for CN region (500 players total)

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
        INSERT INTO {LEADERBOARD_SNAPSHOTS} (player_name, game_mode, region, rank, rating, snapshot_time)
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

                # Fully rewrite logic for handling the daily_leaderboard_stats table
                from datetime import timedelta

                pacific = pytz.timezone("America/Los_Angeles")
                today_pt = datetime.now(timezone.utc).astimezone(pacific).date()
                yesterday_pt = today_pt - timedelta(days=1)
                is_monday = today_pt.weekday() == 0  # Monday is 0

                # Group players by (player_name, game_mode, region)
                # key_fn and current_keys are not used, so removed.

                # Fetch existing entries for today
                cur.execute(
                    """
                    SELECT player_name, game_mode, region, rating, rank, games_played, weekly_games_played
                    FROM daily_leaderboard_stats
                    WHERE day_start = %s
                """,
                    (today_pt,),
                )
                existing_today = cur.fetchall()
                # Map for today's stats
                today_stats = {
                    f"{r[0]}#{r[1]}#{r[2]}": {
                        "rating": r[3],
                        "rank": r[4],
                        "games_played": r[5],
                        "weekly_games_played": r[6],
                    }
                    for r in existing_today
                }

                # Fetch yesterday’s entries to compute games_played and weekly_games_played
                cur.execute(
                    """
                    SELECT player_name, game_mode, region, rating, weekly_games_played
                    FROM daily_leaderboard_stats
                    WHERE day_start = %s
                """,
                    (yesterday_pt,),
                )
                prev_rows = cur.fetchall()
                prev_stats = {
                    f"{r[0]}#{r[1]}#{r[2]}": {"rating": r[3], "weekly": r[4]}
                    for r in prev_rows
                }

                daily_values = []
                for p in players:
                    key = f"{p['player_name']}#{p['game_mode']}#{p['region']}"
                    today = today_stats.get(key)
                    prev = prev_stats.get(key)

                    if today:
                        # If player already has a row today, increment only if rating changed
                        rating_changed = today["rating"] != p["rating"]
                        games_played = (
                            today["games_played"] + 1
                            if rating_changed
                            else today["games_played"]
                        )
                        weekly_games_played = (
                            today["weekly_games_played"] + 1
                            if rating_changed
                            else today["weekly_games_played"]
                        )
                    else:
                        # First entry for today, compare to yesterday
                        rating_changed = prev and prev["rating"] != p["rating"]
                        games_played = 1 if rating_changed else 0
                        if not prev:
                            games_played = 0  # New player, treat as 0
                        weekly_games_played = (
                            games_played
                            if is_monday
                            else (prev["weekly"] if prev else 0) + games_played
                        )

                    daily_values.append(
                        (
                            p["player_name"],
                            p["game_mode"],
                            p["region"],
                            today_pt,
                            p["rating"],
                            p["rank"],
                            games_played,
                            weekly_games_played,
                            datetime.now(timezone.utc),
                        )
                    )

                # Clear and reinsert only affected rows (delete all for today, then reinsert)
                if existing_today:
                    cur.execute(
                        """
                        DELETE FROM daily_leaderboard_stats
                        WHERE day_start = %s
                    """,
                        (today_pt,),
                    )

                insert_daily_query = """
                    INSERT INTO daily_leaderboard_stats
                      (player_name, game_mode, region, day_start, rating, rank, games_played, weekly_games_played, updated_at)
                    VALUES %s
                """
                execute_values(cur, insert_daily_query, daily_values)
                logger.info(f"Inserted daily stats for {len(daily_values)} players.")
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
            FROM {MILESTONE_TRACKING} 
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
                INSERT INTO {MILESTONE_TRACKING}
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
    if not players:
        logger.warning("No player data fetched — skipping DB write to avoid data loss.")
        return 0
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
