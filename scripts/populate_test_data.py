import os
from pathlib import Path
from time import sleep
from dotenv import load_dotenv
from db_utils import get_db_connection
import requests

# Load environment variables from .env file
env_path = Path(__file__).parent.parent / ".env"
load_dotenv(env_path)

# 1. Establish db connection
# 2. Fetch top 100 of each leaderboard ideally in parallel
# 3. I need to get the player id to player name mappings
# 4. Add new entries to the player id table if there's new players
# 5.

BASE_URL = "https://hearthstone.blizzard.com/en-us/api/community/leaderboardsData"
REGIONS = ["US", "EU", "AP"]
REGION_MAPPING = {"US": "NA", "EU": "EU", "AP": "AP"}
MODES = [("battlegrounds", 0), ("battlegroundsduo", 1)]
CURRENT_SEASON = 16


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
DAILY_LEADERBOARD_STATS = "daily_leaderboard_stats"
LEADERBOARD_SNAPSHOTS = "leaderboard_snapshots"
MILESTONE_TRACKING = "milestone_tracking"  # unchanged; optional

# Configs
REGIONS = ["US", "EU", "AP"]
MODES = [("battlegrounds", 0), ("battlegroundsduo", 1)]
REGION_MAPPING = {"US": "NA", "EU": "EU", "AP": "AP"}
BASE_URL = "https://hearthstone.blizzard.com/en-us/api/community/leaderboardsData"
CURRENT_SEASON = int(os.environ.get("CURRENT_SEASON", "17"))
MILESTONE_START = int(os.environ.get("MILESTONE_START", "8000"))
MILESTONE_INCREMENT = int(os.environ.get("MILESTONE_INCREMENT", "1000"))

# Concurrency & batching
FETCH_CONCURRENCY = int(
    os.environ.get("FETCH_CONCURRENCY", "16")
)  # parallel API fetches
AIOHTTP_CONNECTOR_LIMIT = int(os.environ.get("AIOHTTP_CONNECTOR_LIMIT", "64"))
AIOHTTP_PER_HOST_LIMIT = int(os.environ.get("AIOHTTP_PER_HOST_LIMIT", "16"))
BATCH_WRITE_SIZE = int(
    os.environ.get("BATCH_WRITE_SIZE", "200")
)  # execute_values page_size

MAX_PAGES = int(os.environ.get("MAX_PAGES", "40"))


async def fetch_page(session, params, sem, retries=3):
    """Fetch a single page of leaderboard data with retries and timeout"""
    backoff = 1
    timeout = aiohttp.ClientTimeout(total=30)  # 30 second timeout per request

    async with sem:
        for attempt in range(retries):
            try:
                async with session.get(
                    BASE_URL, params=params, timeout=timeout
                ) as response:
                    if response.status == 200:
                        return await response.json()
                    elif response.status == 429:  # Rate limited
                        logger.warning(
                            f"Rate limited {params}: Status {response.status}"
                        )
                        await asyncio.sleep(
                            backoff * 2
                        )  # Longer backoff for rate limits
                    else:
                        logger.warning(f"Failed {params}: Status {response.status}")
            except asyncio.TimeoutError:
                logger.error(f"Timeout {params}: Attempt {attempt + 1}")
            except Exception as e:
                logger.error(f"Error {params}: {str(e)}")

            if attempt < retries - 1:
                await asyncio.sleep(backoff)
                backoff *= 2
        return None


async def fetch_region_mode_pages(
    session, api_region, mode_api, mode_short, sem, max_pages
):
    """Fetch all pages for a specific region and mode until empty page is found"""
    players = []
    page = 1

    while page <= max_pages:
        params = {
            "region": api_region,
            "leaderboardId": mode_api,
            "seasonId": str(CURRENT_SEASON),
            "page": page,
        }

        result = await fetch_page(session, params, sem)
        if not result or "leaderboard" not in result:
            logger.warning(f"No data returned for {api_region}/{mode_api} page {page}")
            break

        rows = result["leaderboard"].get("rows", [])
        if not rows:
            break

        # Process players from this page
        for row in rows:
            if row and row.get("accountid"):
                players.append(
                    {
                        "player_name": row["accountid"].lower(),
                        "game_mode": mode_short,
                        "region": REGION_MAPPING[api_region],
                        "rank": row["rank"],
                        "rating": row["rating"],
                        "snapshot_time": datetime.now(timezone.utc).isoformat(),
                    }
                )

        page += 1

    return players


async def fetch_leaderboards(max_pages=MAX_PAGES):
    """Fetch leaderboard data from all regions and modes with smart pagination"""
    players = []
    sem = asyncio.Semaphore(FETCH_CONCURRENCY)

    # Configure session with timeouts and connection limits
    timeout = aiohttp.ClientTimeout(total=60)  # 60 second timeout for entire session

    # Fetch data from global regions (US, EU, AP)
    async with aiohttp.ClientSession(
        timeout=timeout,
        connector=aiohttp.TCPConnector(
            limit=AIOHTTP_CONNECTOR_LIMIT, limit_per_host=AIOHTTP_PER_HOST_LIMIT
        ),
    ) as session:
        tasks = []
        for mode_api, mode_short in MODES:
            for api_region in REGIONS:
                # Fetch pages for this region/mode until we get an empty page
                tasks.append(
                    fetch_region_mode_pages(
                        session, api_region, mode_api, mode_short, sem, max_pages
                    )
                )

        results = await asyncio.gather(*tasks)
        for result in results:
            if result:
                players.extend(result)

    # Fetch data from China region with smart pagination
    async with aiohttp.ClientSession(
        timeout=timeout,
        connector=aiohttp.TCPConnector(
            limit=AIOHTTP_CONNECTOR_LIMIT, limit_per_host=AIOHTTP_PER_HOST_LIMIT
        ),
    ) as session:
        cn_tasks = []
        for mode_short, mode_name in [(0, "battlegrounds"), (1, "battlegroundsduo")]:
            cn_tasks.append(
                fetch_cn_region_mode_pages(
                    session, mode_short, mode_name, sem, max_pages
                )
            )

        cn_results = await asyncio.gather(*cn_tasks)
        for result in cn_results:
            if result:
                players.extend(result)

    logger.info(f"Fetched {len(players)} players from all regions including CN")
    return _make_names_unique(players)


async def fetch_cn_page(session, url, params, sem, retries=3):
    """Fetch a single page of leaderboard data from CN API with retries and timeout"""
    backoff = 1
    timeout = aiohttp.ClientTimeout(total=30)  # 30 second timeout per request

    async with sem:
        for attempt in range(retries):
            try:
                async with session.get(url, params=params, timeout=timeout) as response:
                    if response.status == 200:
                        return await response.json()
                    elif response.status == 429:  # Rate limited
                        logger.warning(
                            f"Rate limited CN {params}: Status {response.status}"
                        )
                        await asyncio.sleep(
                            backoff * 2
                        )  # Longer backoff for rate limits
                    else:
                        logger.warning(f"Failed CN {params}: Status {response.status}")
            except asyncio.TimeoutError:
                logger.error(f"Timeout CN {params}: Attempt {attempt + 1}")
            except Exception as e:
                logger.error(f"Error CN {params}: {str(e)}")

            if attempt < retries - 1:
                await asyncio.sleep(backoff)
                backoff *= 2
        return None


async def fetch_cn_region_mode_pages(session, mode_short, mode_name, sem, max_pages):
    """Fetch all pages for a specific CN region and mode until empty page is found"""
    players = []
    page = 1
    url = "https://webapi.blizzard.cn/hs-rank-api-server/api/game/ranks"

    while page <= max_pages:
        params = {
            "page": page,
            "page_size": 25,
            "mode_name": mode_name,
            "season_id": str(CURRENT_SEASON),
        }

        result = await fetch_cn_page(session, url, params, sem)
        if not result or result.get("code") != 0:
            logger.warning(f"No data returned for CN {mode_name} page {page}")
            break

        data_list = result.get("data", {}).get("list", [])
        if not data_list:
            break

        # Process players from this page
        for row in data_list:
            players.append(
                {
                    "player_name": row["battle_tag"].lower(),
                    "game_mode": mode_short,
                    "region": "CN",
                    "rank": row["position"],
                    "rating": row["score"],
                    "snapshot_time": datetime.now(timezone.utc).isoformat(),
                }
            )

        page += 1

    return players


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

    conn = None
    try:
        conn = get_db_connection()
        with conn:
            with conn.cursor() as cur:

                # Map player_name -> player_id (upsert players, then fetch ids)
                unique_names = sorted({p["player_name"] for p in players})
                id_by_name = {}
                if unique_names:
                    # Helper to chunk large arrays
                    def _chunks(lst, n):
                        for i in range(0, len(lst), n):
                            yield lst[i : i + n]

                    # Pre-check: how many of these names already exist?
                    _existing_rows = []
                    for chunk in _chunks(unique_names, 1000):
                        cur.execute(
                            """
                            SELECT player_id, player_name
                            FROM players
                            WHERE player_name = ANY(%s)
                            """,
                            (chunk,),
                        )
                        _existing_rows.extend(cur.fetchall())
                    _existing_names = {name for (_pid, name) in _existing_rows}
                    _existing_count = len(_existing_names)

                    # 1) Upsert without RETURNING (safe across execute_values batching)
                    player_upsert_query = """
                        INSERT INTO players (player_name)
                        VALUES %s
                        ON CONFLICT (player_name)
                        DO UPDATE SET player_name = EXCLUDED.player_name
                        """
                    execute_values(
                        cur,
                        player_upsert_query,
                        [(n,) for n in unique_names],
                        page_size=BATCH_WRITE_SIZE,
                    )

                    # 2) Fetch ids for all names in chunks to avoid overly-large arrays
                    id_rows = []
                    for chunk in _chunks(unique_names, 1000):
                        cur.execute(
                            """
                            SELECT player_id, player_name
                            FROM players
                            WHERE player_name = ANY(%s)
                            """,
                            (chunk,),
                        )
                        id_rows.extend(cur.fetchall())
                    id_by_name = {name: pid for (pid, name) in id_rows}

                    _created_count = len(unique_names) - _existing_count
                    logger.info(
                        f"Players: existing={_existing_count}, created={_created_count}, total={len(unique_names)}"
                    )
                    # Sanity log
                    if len(id_by_name) != len(unique_names):
                        missing = [n for n in unique_names if n not in id_by_name]
                        logger.warning(
                            f"Player id lookup mismatch: expected {len(unique_names)}, got {len(id_by_name)}. Missing sample: {missing[:10]}"
                        )
                    logger.info(f"Prepared id map for {len(id_by_name)} players.")
                else:
                    logger.info("No player names to upsert into players table.")

                # Fully rewrite logic for handling the daily_leaderboard_stats table via UPSERT
                from datetime import timedelta

                pacific = pytz.timezone("America/Los_Angeles")
                now_utc = datetime.now(timezone.utc)
                today_pt = now_utc.astimezone(pacific).date()
                yesterday_pt = today_pt - timedelta(days=1)
                is_monday = today_pt.weekday() == 0  # Monday is 0

                # Fetch existing entries for today (cast enums to text for consistent Python keys)
                cur.execute(
                    f"""
                    SELECT player_id, game_mode::text, region::text, rating, rank, games_played, weekly_games_played
                    FROM {DAILY_LEADERBOARD_STATS}
                    WHERE day_start = %s
                    """,
                    (today_pt,),
                )
                existing_today = cur.fetchall()
                today_stats = {
                    f"{r[0]}#{r[2]}#{r[1]}": {  # player_id#region#mode
                        "rating": r[3],
                        "rank": r[4],
                        "games_played": r[5],
                        "weekly_games_played": r[6],
                    }
                    for r in existing_today
                }

                # Fetch yesterday’s entries to compute base weekly and rating delta at day rollover
                cur.execute(
                    f"""
                    SELECT player_id, game_mode::text, region::text, rating, weekly_games_played
                    FROM {DAILY_LEADERBOARD_STATS}
                    WHERE day_start = %s
                    """,
                    (yesterday_pt,),
                )
                prev_rows = cur.fetchall()
                prev_stats = {
                    f"{r[0]}#{r[2]}#{r[1]}": {"rating": r[3], "weekly": r[4]}
                    for r in prev_rows
                }

                # Build UPSERT values
                daily_values = []
                skipped_missing_ids = 0
                for p in players:
                    pid = id_by_name.get(p["player_name"])  # ensure we have an id
                    if pid is None:
                        skipped_missing_ids += 1
                        continue

                    mode_label = str(p["game_mode"])  # enum labels are '0'/'1'
                    region_label = p["region"]  # enum labels 'NA','EU','AP','CN'
                    key = f"{pid}#{region_label}#{mode_label}"
                    today = today_stats.get(key)
                    prev = prev_stats.get(key)

                    if not today:
                        base_weekly = (
                            0 if is_monday else (prev["weekly"] if prev else 0)
                        )
                        rating_changed_from_prev = bool(
                            prev and prev["rating"] != p["rating"]
                        )
                        weekly_games_played = base_weekly + (
                            1 if rating_changed_from_prev else 0
                        )
                        games_played = 1 if rating_changed_from_prev else 0
                    else:
                        # For existing rows, ON CONFLICT will increment if rating changes.
                        weekly_games_played = today["weekly_games_played"]
                        games_played = today["games_played"]

                    daily_values.append(
                        (
                            pid,  # player_id
                            mode_label,  # game_mode_enum label
                            region_label,  # region_enum label
                            today_pt,  # day_start
                            p["rating"],
                            p["rank"],
                            games_played,
                            weekly_games_played,
                            now_utc,
                        )
                    )

                insert_daily_query = f"""
                    INSERT INTO {DAILY_LEADERBOARD_STATS}
                      (player_id, game_mode, region, day_start, rating, rank, games_played, weekly_games_played, updated_at)
                    VALUES %s
                    ON CONFLICT (player_id, game_mode, region, day_start)
                    DO UPDATE SET
                      rating = EXCLUDED.rating,
                      rank = EXCLUDED.rank,
                      games_played = CASE
                        WHEN EXCLUDED.rating <> {DAILY_LEADERBOARD_STATS}.rating THEN {DAILY_LEADERBOARD_STATS}.games_played + 1
                        ELSE {DAILY_LEADERBOARD_STATS}.games_played
                      END,
                      weekly_games_played = CASE
                        WHEN EXCLUDED.rating <> {DAILY_LEADERBOARD_STATS}.rating THEN {DAILY_LEADERBOARD_STATS}.weekly_games_played + 1
                        ELSE {DAILY_LEADERBOARD_STATS}.weekly_games_played
                      END,
                      updated_at = now()
                """
                # Use RETURNING to count inserts vs updates across chunks
                insert_daily_query_returning = (
                    insert_daily_query + "\nRETURNING (xmax = 0) AS inserted"
                )
                daily_inserted = 0
                daily_updated = 0

                def _chunks_daily(lst, n):
                    for i in range(0, len(lst), n):
                        yield lst[i : i + n]

                if daily_values:
                    for chunk in _chunks_daily(daily_values, BATCH_WRITE_SIZE):
                        execute_values(
                            cur,
                            insert_daily_query_returning,
                            chunk,
                            page_size=BATCH_WRITE_SIZE,
                        )
                        flags = cur.fetchall()  # list of (inserted,)
                        ins = sum(1 for (inserted,) in flags if inserted)
                        daily_inserted += ins
                        daily_updated += len(flags) - ins
                logger.info(
                    f"Daily upsert: attempted={len(daily_values)}, inserted={daily_inserted}, updated={daily_updated}, skipped_missing_ids={skipped_missing_ids}"
                )
                # =============================
                # Change-point insert into snapshots (TEST)
                # =============================
                # Build staging rows with player_id + enums
                snapshot_stage = []
                for p in players:
                    pid = id_by_name.get(
                        p["player_name"]
                    )  # must exist from earlier upsert
                    if pid is None:
                        continue
                    snapshot_stage.append(
                        (
                            pid,  # player_id
                            str(p["game_mode"]),  # game_mode_enum label '0' | '1'
                            p["region"],  # region_enum label 'NA'|'EU'|'AP'|'CN'
                            p["rank"],
                            p["rating"],
                            p["snapshot_time"],  # ISO string; cast to timestamptz below
                        )
                    )

                if snapshot_stage:
                    # 1) Put incoming poll into a TEMP table with proper enum types
                    cur.execute(
                        f"""
                        CREATE TEMP TABLE tmp_ls (
                          player_id bigint,
                          game_mode { 'game_mode_enum' },
                          region    { 'region_enum'   },
                          rank      int,
                          rating    int,
                          snapshot_time timestamptz
                        ) ON COMMIT DROP
                        """.replace(
                            "{ 'game_mode_enum' }", "game_mode_enum"
                        ).replace(
                            "{ 'region_enum'   }", "region_enum"
                        )
                    )

                    # Insert rows, casting labels to enums/timestamptz
                    execute_values(
                        cur,
                        """
                        INSERT INTO tmp_ls (player_id, game_mode, region, rating, snapshot_time)
                        VALUES %s
                        """,
                        [
                            (
                                r[0],
                                r[1],  # label will auto-cast to game_mode_enum
                                r[2],  # label will auto-cast to region_enum
                                r[4],
                                r[5],
                            )
                            for r in snapshot_stage
                        ],
                        page_size=BATCH_WRITE_SIZE,
                    )

                    # 2) Insert only change points into snapshots using a LATERAL lookup of the last rating
                    cur.execute(
                        f"""
                        INSERT INTO {LEADERBOARD_SNAPSHOTS}
                          (player_id, game_mode, region, rating, snapshot_time)
                        SELECT t.player_id, t.game_mode, t.region, t.rating, t.snapshot_time
                        FROM tmp_ls t
                        LEFT JOIN LATERAL (
                          SELECT ls.rating
                          FROM {LEADERBOARD_SNAPSHOTS} ls
                          WHERE ls.player_id = t.player_id
                            AND ls.region    = t.region
                            AND ls.game_mode = t.game_mode
                          ORDER BY ls.snapshot_time DESC
                          LIMIT 1
                        ) prev ON TRUE
                        WHERE prev.rating IS NULL OR prev.rating <> t.rating
                        """
                    )
                    snapshot_inserted = cur.rowcount
                    logger.info(
                        f"Snapshots change-points: staged={len(snapshot_stage)}, inserted={snapshot_inserted}, skipped={len(snapshot_stage) - snapshot_inserted}"
                    )
                else:
                    logger.info("No snapshot rows to stage (empty or missing ids).")
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

            execute_values(
                cursor,
                milestone_insert_query,
                milestone_values,
                page_size=BATCH_WRITE_SIZE,
            )
            logger.info(f"Processed {len(milestones_to_insert)} milestones.")

    except Exception as e:
        logger.error(f"Error processing milestones: {e}")
        raise


async def process_leaderboards():
    """Main function to fetch and process leaderboard data with timeout protection"""
    start_time = datetime.now()
    logger.info("Fetching leaderboard data...")

    try:
        players = await fetch_leaderboards()
        if not players:
            logger.warning(
                "No player data fetched — skipping DB write to avoid data loss."
            )
            return 0

        fetch_time = (datetime.now() - start_time).total_seconds()
        logger.info(f"Fetched {len(players)} players in {fetch_time:.2f}s.")

        # Check if we're approaching timeout (leave 60 seconds buffer for DB operations)
        elapsed = (datetime.now() - start_time).total_seconds()
        if elapsed > 240:  # 300 - 60 seconds buffer
            logger.warning(
                f"Approaching timeout after {elapsed}s, skipping database write"
            )
            return len(players)

        write_to_postgres(players)
        total_time = (datetime.now() - start_time).total_seconds()
        logger.info(f"DB write completed in {total_time:.2f}s")

        return len(players)

    except Exception as e:
        logger.error(f"Error in process_leaderboards: {str(e)}")
        raise


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
    while True:
        print(lambda_handler({}, None))
        sleep(300)
