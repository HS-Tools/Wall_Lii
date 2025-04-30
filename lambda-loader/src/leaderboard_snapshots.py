import json
import os
import asyncio
import aiohttp
from datetime import datetime, timezone
import logging
import boto3
import psycopg2
from psycopg2.extras import execute_values

# Set up logging
logger = logging.getLogger()
logger.setLevel(logging.INFO)

# Constants
REGIONS = ["US", "EU", "AP"]
MODES = [("battlegrounds", "0"), ("battlegroundsduo", "1")]
REGION_MAPPING = {"US": "NA", "EU": "EU", "AP": "AP"}
BASE_URL = "https://hearthstone.blizzard.com/en-us/api/community/leaderboardsData"
CURRENT_SEASON = 14  # Current season ID
MILESTONE_START = 8000  # Starting milestone
MILESTONE_INCREMENT = 1000  # Increment for milestones


# Database connection
def get_db_connection():
    """Get PostgreSQL connection using environment variables"""
    return psycopg2.connect(
        host=os.environ.get("DB_HOST"),
        port=os.environ.get("DB_PORT", "5432"),
        dbname=os.environ.get("DB_NAME"),
        user=os.environ.get("DB_USER"),
        password=os.environ.get("DB_PASSWORD"),
        sslmode="require",
    )


async def fetch_page(session, params, sem, retries=3):
    """Fetch a single page with rate limiting and retries"""
    backoff = 1
    async with sem:
        for attempt in range(retries):
            try:
                async with session.get(BASE_URL, params=params) as response:
                    if response.status == 200:
                        return await response.json()
                    logger.error(f"Failed {params}: Status {response.status}")
            except Exception as e:
                logger.error(f"Error {params}: {str(e)}")

            if attempt < retries - 1:
                await asyncio.sleep(backoff)
                backoff *= 2
        return None


async def fetch_leaderboards(max_pages: int = 40):
    """Fetch leaderboard data from all regions and modes"""
    players = []
    sem = asyncio.Semaphore(15)  # Rate limiting

    async with aiohttp.ClientSession(
        connector=aiohttp.TCPConnector(limit=50)
    ) as session:
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

    return _make_names_unique(players)


def _make_names_unique(players):
    """Ensure unique player names within each region-mode combination"""
    seen = {}
    final = []
    for p in players:
        key = f"{p['region']}#{p['game_mode']}#{p['player_name']}"
        count = seen.get(key, 0) + 1
        seen[key] = count
        p = p.copy()
        if count > 1:
            p["player_name"] = f"{p['player_name']}#{count}"
        final.append(p)
    return final


def write_to_postgres(players):
    """Write player data to PostgreSQL and process milestones"""
    insert_query = """
        INSERT INTO leaderboard_snapshots (player_name, game_mode, region, rank, rating, snapshot_time)
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

    try:
        conn = get_db_connection()
        with conn:
            with conn.cursor() as cur:
                execute_values(cur, insert_query, values, page_size=100)
                logger.info(
                    f"Inserted {len(players)} players into leaderboard_snapshots."
                )

                # Process milestones after inserting player data
                process_milestones(cur, players)

        return {"players_inserted": len(players), "status": "success"}
    except Exception as e:
        logger.error(f"Error inserting into DB: {str(e)}")
        return {"error": str(e), "status": "error"}
    finally:
        if conn:
            conn.close()


def process_milestones(cursor, players):
    """Process rating milestones and insert into milestone_tracking table"""
    try:
        # Get existing milestones
        cursor.execute(
            """
            SELECT region, game_mode, milestone 
            FROM milestone_tracking
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
            milestone_insert_query = """
                INSERT INTO milestone_tracking 
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

        return len(milestones_to_insert)
    except Exception as e:
        logger.error(f"Error processing milestones: {e}")
        return 0


async def async_lambda_handler(event, context):
    """Async handler for Lambda function"""
    try:
        max_pages = event.get("max_pages", 40) if event else 40
        players = await fetch_leaderboards(max_pages)
        logger.info(f"Fetched {len(players)} players.")
        result = write_to_postgres(players)

        return {
            "statusCode": 200 if result["status"] == "success" else 500,
            "body": json.dumps(result),
        }
    except Exception as e:
        logger.error(f"Error in lambda handler: {str(e)}")
        return {"statusCode": 500, "body": json.dumps({"error": str(e)})}


def lambda_handler(event, context):
    """AWS Lambda handler to fetch and store leaderboard data"""
    loop = asyncio.get_event_loop()
    return loop.run_until_complete(async_lambda_handler(event, context))


if __name__ == "__main__":
    # For local testing
    result = asyncio.run(async_lambda_handler(None, None))
    print(json.dumps(result, indent=2))
