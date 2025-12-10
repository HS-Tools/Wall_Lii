import os
import json
import asyncio
import aiohttp
from datetime import datetime, timezone, timedelta
from psycopg2.extras import execute_values
from logger import setup_logger
from db_utils import get_db_connection
import pytz
from dotenv import load_dotenv

# Load environment variables from .env file
load_dotenv()

# Set up logger
logger = setup_logger("leaderboard_snapshots")

# Table names
LEADERBOARD_SNAPSHOTS = "leaderboard_snapshots"
MILESTONE_TRACKING = "milestone_tracking"
DAILY_LEADERBOARD_STATS = "daily_leaderboard_stats"
PLAYERS_TABLE = "players"

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


def get_max_pages(region: str, game_mode: int) -> int:
    """
    Get the maximum number of pages to fetch based on region and game mode.
    Each page contains 25 players.
    Returns:
        - Non-China solo: 40 pages (1000 players)
        - Non-China duos: 4 pages (100 players)
        - China solo: 20 pages (500 players)
        - China duos: 4 pages (100 players)
    """
    if region == "CN":
        return 20 if game_mode == 0 else 4  # 500 for solo, 100 for duos
    else:
        return 40 if game_mode == 0 else 4  # 1000 for solo, 100 for duos


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
                # Calculate max_pages based on region and game mode
                mapped_region = REGION_MAPPING[api_region]
                region_max_pages = get_max_pages(mapped_region, mode_short)
                # Fetch pages for this region/mode until we get an empty page
                tasks.append(
                    fetch_region_mode_pages(
                        session, api_region, mode_api, mode_short, sem, region_max_pages
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
            # Calculate max_pages based on region and game mode
            cn_max_pages = get_max_pages("CN", mode_short)
            cn_tasks.append(
                fetch_cn_region_mode_pages(
                    session, mode_short, mode_name, sem, cn_max_pages
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
            # logger.warning(f"No data returned for CN {mode_name} page {page}")
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
                # Create or replace the estimate_placement PostgreSQL function
                # This replicates the Python estimate_placement logic (season ramp +
                # high-MMR dampening).
                cur.execute(
                    """
                    CREATE OR REPLACE FUNCTION estimate_placement(start_rating NUMERIC, end_rating NUMERIC)
                    RETURNS NUMERIC
                    LANGUAGE plpgsql
                    IMMUTABLE
                    AS $$
                    DECLARE
                        gain NUMERIC;
                        dex_avg NUMERIC;
                        lobby_cap NUMERIC;
                        dex_threshold NUMERIC;
                        offset NUMERIC;
                        damping NUMERIC;
                        days_since_season_start INT;
                        season_start DATE := DATE '2025-12-01';
                        ramp_days INT := 30;
                        season_lobby_cap NUMERIC := 8500.0;
                        season_min_lobby_cap NUMERIC := 6800.0;
                        season_dex_threshold_max NUMERIC := 8200.0;
                        season_dex_threshold_min NUMERIC := 6800.0;
                        placements NUMERIC[] := ARRAY[1, 2, 3, 3.5, 4, 4.5, 5, 5.5, 6, 6.5, 7, 7.5, 8];
                        p NUMERIC;
                        avg_opp NUMERIC;
                        delta NUMERIC;
                        best_placement NUMERIC := 1;
                        best_delta NUMERIC := 'Infinity'::NUMERIC;
                    BEGIN
                        gain := end_rating - start_rating;

                        -- Days since season start (clamped to >= 0)
                        days_since_season_start := GREATEST((CURRENT_DATE - season_start), 0);

                        -- Season-adjusted lobby cap (linear ramp over ramp_days)
                        IF days_since_season_start >= ramp_days THEN
                            lobby_cap := season_lobby_cap;
                        ELSE
                            lobby_cap := season_min_lobby_cap
                                + (days_since_season_start::NUMERIC / ramp_days::NUMERIC)
                                  * (season_lobby_cap - season_min_lobby_cap);
                        END IF;

                        -- Season-adjusted threshold
                        IF days_since_season_start >= ramp_days THEN
                            dex_threshold := season_dex_threshold_max;
                        ELSE
                            dex_threshold := season_dex_threshold_min
                                + (days_since_season_start::NUMERIC / ramp_days::NUMERIC)
                                  * (season_dex_threshold_max - season_dex_threshold_min);
                        END IF;

                        -- Calculate dexAvg with high-MMR dampening above threshold
                        IF start_rating <= dex_threshold THEN
                            dex_avg := start_rating;
                        ELSE
                            offset := start_rating - dex_threshold;
                            damping := 1 / (1 + POWER(offset / 500.0, 1.3));
                            dex_avg := lobby_cap + (start_rating - lobby_cap) * damping;
                        END IF;
                        
                        -- Find placement with smallest delta
                        FOREACH p IN ARRAY placements
                        LOOP
                            -- avgOpp-formula
                            avg_opp := start_rating - 148.1181435 * (100 - ((p - 1) * (200.0 / 7.0) + gain));
                            delta := ABS(dex_avg - avg_opp);
                            
                            IF delta < best_delta THEN
                                best_delta := delta;
                                best_placement := p;
                            END IF;
                        END LOOP;
                        
                        RETURN best_placement;
                    END;
                    $$;
                """
                )

                # Map player_name -> player_id (upsert players, then fetch ids)
                unique_names = sorted({p["player_name"] for p in players})
                id_by_name = {}
                if unique_names:
                    # Helper to chunk large arrays
                    def _chunks(lst, n):
                        for i in range(0, len(lst), n):
                            yield lst[i : i + n]

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

                    # Sanity log
                    if len(id_by_name) != len(unique_names):
                        missing = [n for n in unique_names if n not in id_by_name]
                        logger.warning(
                            f"Player id lookup mismatch: expected {len(unique_names)}, got {len(id_by_name)}. Missing sample: {missing[:10]}"
                        )
                    logger.info(f"Prepared id map for {len(id_by_name)} players.")
                else:
                    logger.info("No player names to upsert into players table.")

                # Process milestones after inserting player data
                process_milestones(cur, players)

                pacific = pytz.timezone("America/Los_Angeles")
                now_utc = datetime.now(timezone.utc)
                today_pt = now_utc.astimezone(pacific).date()
                yesterday_pt = today_pt - timedelta(days=1)
                is_monday = today_pt.weekday() == 0  # Monday is 0

                # Stage today's polled rows in a temp table, then do a single server-side upsert
                cur.execute(
                    """
                    CREATE TEMP TABLE tmp_daily (
                      player_id int,
                      game_mode game_mode_enum,
                      region    region_enum,
                      rating    int,
                      rank      int,
                      day_start date,
                      updated_at timestamptz
                    ) ON COMMIT DROP
                    """
                )

                # Build temp rows from fetched players
                tmp_rows = []
                for p in players:
                    pid = id_by_name.get(p["player_name"])
                    if pid is None:
                        continue
                    tmp_rows.append(
                        (
                            pid,
                            str(p["game_mode"]),  # label auto-casts to enum
                            p["region"],  # label auto-casts to enum
                            p["rating"],
                            p["rank"],
                            today_pt,
                            now_utc,
                        )
                    )

                if tmp_rows:
                    execute_values(
                        cur,
                        """
                        INSERT INTO tmp_daily (player_id, game_mode, region, rating, rank, day_start, updated_at)
                        VALUES %s
                        """,
                        tmp_rows,
                        page_size=BATCH_WRITE_SIZE,
                    )

                    # Single statement: insert new rows with correct initial counters,
                    # and update existing rows by incrementing when rating changes.
                    # For inserts, we carry yesterday's weekly unless Monday.
                    cur.execute(
                        f"""
                        WITH prev AS (
                          SELECT d.player_id, d.game_mode, d.region,
                                 d.rating AS prev_rating,
                                 d.weekly_games_played AS prev_weekly,
                                 d.day_avg AS prev_day_avg,
                                 d.weekly_avg AS prev_weekly_avg,
                                 d.games_played AS prev_games_played
                          FROM {DAILY_LEADERBOARD_STATS} d
                          WHERE d.day_start = %s
                        )
                        INSERT INTO {DAILY_LEADERBOARD_STATS}
                          (player_id, game_mode, region, day_start, rating, rank, games_played, weekly_games_played, day_avg, weekly_avg, updated_at)
                        SELECT t.player_id, t.game_mode, t.region, t.day_start, t.rating, t.rank,
                               CASE WHEN p.prev_rating IS NOT NULL AND p.prev_rating IS DISTINCT FROM t.rating THEN 1 ELSE 0 END AS games_played,
                               (CASE WHEN %s THEN 0 ELSE COALESCE(p.prev_weekly, 0) END)
                                 + CASE WHEN p.prev_rating IS NOT NULL AND p.prev_rating IS DISTINCT FROM t.rating THEN 1 ELSE 0 END AS weekly_games_played,
                               CASE 
                                 WHEN p.prev_rating IS NOT NULL AND p.prev_rating IS DISTINCT FROM t.rating THEN
                                   estimate_placement(p.prev_rating, t.rating)
                                 ELSE NULL
                               END AS day_avg,
                               CASE 
                                 WHEN p.prev_rating IS NOT NULL AND p.prev_rating IS DISTINCT FROM t.rating THEN
                                   estimate_placement(p.prev_rating, t.rating)
                                 ELSE NULL
                               END AS weekly_avg,
                               t.updated_at
                        FROM tmp_daily t
                        LEFT JOIN prev p
                          ON p.player_id = t.player_id
                         AND p.game_mode = t.game_mode
                         AND p.region    = t.region
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
                          day_avg = CASE
                            WHEN EXCLUDED.rating <> {DAILY_LEADERBOARD_STATS}.rating THEN
                              CASE
                                WHEN {DAILY_LEADERBOARD_STATS}.games_played = 0 OR {DAILY_LEADERBOARD_STATS}.day_avg IS NULL THEN
                                  estimate_placement({DAILY_LEADERBOARD_STATS}.rating, EXCLUDED.rating)
                                ELSE
                                  ({DAILY_LEADERBOARD_STATS}.day_avg * {DAILY_LEADERBOARD_STATS}.games_played 
                                   + estimate_placement({DAILY_LEADERBOARD_STATS}.rating, EXCLUDED.rating))
                                  / ({DAILY_LEADERBOARD_STATS}.games_played + 1.0)
                              END
                            ELSE {DAILY_LEADERBOARD_STATS}.day_avg
                          END,
                          weekly_avg = CASE
                            WHEN EXCLUDED.rating <> {DAILY_LEADERBOARD_STATS}.rating THEN
                              CASE
                                WHEN {DAILY_LEADERBOARD_STATS}.weekly_games_played = 0 OR {DAILY_LEADERBOARD_STATS}.weekly_avg IS NULL THEN
                                  estimate_placement({DAILY_LEADERBOARD_STATS}.rating, EXCLUDED.rating)
                                ELSE
                                  ({DAILY_LEADERBOARD_STATS}.weekly_avg * {DAILY_LEADERBOARD_STATS}.weekly_games_played 
                                   + estimate_placement({DAILY_LEADERBOARD_STATS}.rating, EXCLUDED.rating))
                                  / ({DAILY_LEADERBOARD_STATS}.weekly_games_played + 1.0)
                              END
                            ELSE {DAILY_LEADERBOARD_STATS}.weekly_avg
                          END,
                          updated_at = now()
                        """,
                        (yesterday_pt, is_monday),
                    )
                    logger.info(
                        f"Daily upsert (server-side): affected_rows={cur.rowcount}"
                    )
                else:
                    logger.info("No tmp_daily rows to upsert.")
                # =============================
                # Change-point insert into snapshots
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
                          player_id int,
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
    print(lambda_handler({}, None))
