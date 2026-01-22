#!/usr/bin/env python3
"""
Recalculate day_avg and weekly_avg in daily_leaderboard_stats table
using the updated estimate_placement function (with 10000 threshold) and data from leaderboard_snapshots.

This script processes all rows in daily_leaderboard_stats and recalculates:
- day_avg: Average placement for rating changes within each day (PT timezone)
- weekly_avg: Average placement for rating changes within each week (Monday-Sunday, PT timezone)
"""

import sys
from psycopg2.extras import DictCursor
from dotenv import load_dotenv

from db_utils import get_db_connection

load_dotenv()

# Configuration
DRY_RUN = True  # Set to False to enable writes

# Test configuration - set to None to process all players
TEST_PLAYER_NAME = None  # Set to None to process all players
TEST_REGION = None  # Set to None to process all regions
TEST_GAME_MODE = None  # Set to None to process all game modes (0 = solo, 1 = duo)

# Table names
DAILY_LEADERBOARD_STATS = "daily_leaderboard_stats"
LEADERBOARD_SNAPSHOTS = "leaderboard_snapshots"
PLAYERS_TABLE = "players"


def get_player_id(cursor, player_name):
    """Fetch player_id for a given player_name."""
    cursor.execute(
        f"""
        SELECT player_id, player_name
        FROM {PLAYERS_TABLE}
        WHERE player_name = %s
        """,
        (player_name.lower(),),
    )
    result = cursor.fetchone()
    if result:
        return result["player_id"]
    return None


def ensure_estimate_placement_function(cursor):
    """Create or replace the estimate_placement PostgreSQL function with 10000 threshold."""
    cursor.execute(
        """
        CREATE OR REPLACE FUNCTION estimate_placement(start_rating NUMERIC, end_rating NUMERIC)
        RETURNS NUMERIC
        LANGUAGE plpgsql
        IMMUTABLE
        AS $$
        DECLARE
            gain NUMERIC;
            dex_avg NUMERIC;
            placements NUMERIC[] := ARRAY[1, 2, 3, 3.5, 4, 4.5, 5, 5.5, 6, 6.5, 7, 7.5, 8];
            p NUMERIC;
            avg_opp NUMERIC;
            delta NUMERIC;
            best_placement NUMERIC := 1;
            best_delta NUMERIC := 'Infinity'::NUMERIC;
        BEGIN
            gain := end_rating - start_rating;
            
            -- Calculate dexAvg
            IF start_rating < 8200 THEN
                dex_avg := start_rating;
            ELSE
                dex_avg := start_rating - 0.85 * (start_rating - 8500);
            END IF;
            
            -- Find placement with smallest delta
            FOREACH p IN ARRAY placements
            LOOP
                -- avgOpp-formula
                avg_opp := start_rating - 148.1181435 * (100 - ((p - 1) * (200.0 / 7.0) + gain));
                
                -- Skip placements where avg_opp > 10000
                IF avg_opp > 10000 THEN
                    CONTINUE;
                END IF;
                
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
    print("✓ estimate_placement function created/updated with 10000 threshold")


def recalculate_averages_batch(
    conn, cursor, dry_run=False, player_id=None, region=None, game_mode=None
):
    """
    Recalculate day_avg and weekly_avg for a specific batch (region/game_mode combination).

    Args:
        conn: Database connection
        cursor: Database cursor
        dry_run: If True, only show what would be updated
        player_id: Optional player_id to filter by (for testing)
        region: Optional region to filter by
        game_mode: Optional game_mode to filter by
    """
    # Build filter conditions
    filter_conditions = []
    filter_params = []

    if player_id is not None:
        filter_conditions.append("player_id = %s")
        filter_params.append(player_id)
    if region is not None:
        filter_conditions.append("region = %s")
        filter_params.append(region)
    if game_mode is not None:
        filter_conditions.append("game_mode = %s::game_mode_enum")
        filter_params.append(str(game_mode))

    filter_clause = ""
    if filter_conditions:
        filter_clause = "WHERE " + " AND ".join(filter_conditions)

    # Build filter conditions for snapshots CTE
    snapshot_filter_conditions = []
    snapshot_filter_params = []

    if player_id is not None:
        snapshot_filter_conditions.append("ls.player_id = %s")
        snapshot_filter_params.append(player_id)
    if region is not None:
        snapshot_filter_conditions.append("ls.region = %s")
        snapshot_filter_params.append(region)
    if game_mode is not None:
        snapshot_filter_conditions.append("ls.game_mode = %s::game_mode_enum")
        snapshot_filter_params.append(str(game_mode))

    snapshot_filter_clause = ""
    if snapshot_filter_conditions:
        snapshot_filter_clause = "WHERE " + " AND ".join(snapshot_filter_conditions)

    # Optimized query: Pre-calculate all placements, then use efficient aggregation for weekly_avg
    update_query = f"""
        WITH all_snapshots AS (
            -- Get all snapshots with previous rating to identify changes
            SELECT 
                ls.player_id,
                ls.game_mode,
                ls.region,
                ls.snapshot_time,
                ls.rating,
                LAG(ls.rating) OVER (
                    PARTITION BY ls.player_id, ls.game_mode, ls.region 
                    ORDER BY ls.snapshot_time
                ) AS prev_rating,
                -- Convert to PT timezone for day calculations
                (ls.snapshot_time AT TIME ZONE 'America/Los_Angeles')::date AS day_start_pt
            FROM {LEADERBOARD_SNAPSHOTS} ls
            {snapshot_filter_clause}
        ),
        rating_changes AS (
            -- Filter to only rating changes and calculate placements (do this once)
            SELECT 
                player_id,
                game_mode,
                region,
                day_start_pt,
                prev_rating,
                rating,
                estimate_placement(prev_rating, rating) AS placement,
                -- Calculate week_start for each rating change
                day_start_pt - EXTRACT(DOW FROM day_start_pt)::integer 
                    + CASE WHEN EXTRACT(DOW FROM day_start_pt) = 0 THEN -6 ELSE 1 END AS week_start
            FROM all_snapshots
            WHERE prev_rating IS NOT NULL 
              AND prev_rating IS DISTINCT FROM rating
        ),
        daily_stats AS (
            -- Calculate day_avg for each day
            SELECT 
                player_id,
                game_mode,
                region,
                day_start_pt AS day_start,
                AVG(placement) AS day_avg
            FROM rating_changes
            GROUP BY player_id, game_mode, region, day_start_pt
        ),
        all_daily_rows AS (
            -- Get all rows from daily_leaderboard_stats
            SELECT 
                player_id,
                game_mode,
                region,
                day_start,
                day_start - EXTRACT(DOW FROM day_start)::integer 
                    + CASE WHEN EXTRACT(DOW FROM day_start) = 0 THEN -6 ELSE 1 END AS week_start
            FROM {DAILY_LEADERBOARD_STATS}
            {filter_clause}
        ),
        weekly_stats AS (
            -- Calculate weekly_avg efficiently using join and aggregation (no correlated subquery)
            SELECT 
                adr.player_id,
                adr.game_mode,
                adr.region,
                adr.day_start,
                AVG(rc.placement) AS weekly_avg
            FROM all_daily_rows adr
            INNER JOIN rating_changes rc ON
                rc.player_id = adr.player_id
                AND rc.game_mode = adr.game_mode
                AND rc.region = adr.region
                AND rc.week_start = adr.week_start
                AND rc.day_start_pt <= adr.day_start
            GROUP BY adr.player_id, adr.game_mode, adr.region, adr.day_start
        ),
        final_stats AS (
            -- Combine daily and weekly stats
            SELECT 
                COALESCE(ds.player_id, ws.player_id) AS player_id,
                COALESCE(ds.game_mode, ws.game_mode) AS game_mode,
                COALESCE(ds.region, ws.region) AS region,
                COALESCE(ds.day_start, ws.day_start) AS day_start,
                ds.day_avg,
                ws.weekly_avg
            FROM daily_stats ds
            FULL OUTER JOIN weekly_stats ws ON
                ds.player_id = ws.player_id
                AND ds.game_mode = ws.game_mode
                AND ds.region = ws.region
                AND ds.day_start = ws.day_start
        )
        UPDATE {DAILY_LEADERBOARD_STATS} dls
        SET 
            day_avg = fs.day_avg,
            weekly_avg = fs.weekly_avg,
            updated_at = now()
        FROM final_stats fs
        WHERE dls.player_id = fs.player_id
          AND dls.game_mode = fs.game_mode
          AND dls.region = fs.region
          AND dls.day_start = fs.day_start
          AND (
              dls.day_avg IS DISTINCT FROM fs.day_avg 
              OR dls.weekly_avg IS DISTINCT FROM fs.weekly_avg
          )
        """

    # Combine parameters for the query
    query_params = tuple(snapshot_filter_params + filter_params)

    if dry_run:
        # For dry run, use the same optimized query structure
        cursor.execute(
            f"""
            WITH all_snapshots AS (
                SELECT 
                    ls.player_id,
                    ls.game_mode,
                    ls.region,
                    ls.snapshot_time,
                    ls.rating,
                    LAG(ls.rating) OVER (
                        PARTITION BY ls.player_id, ls.game_mode, ls.region 
                        ORDER BY ls.snapshot_time
                    ) AS prev_rating,
                    (ls.snapshot_time AT TIME ZONE 'America/Los_Angeles')::date AS day_start_pt
                FROM {LEADERBOARD_SNAPSHOTS} ls
                {snapshot_filter_clause}
            ),
            rating_changes AS (
                SELECT 
                    player_id,
                    game_mode,
                    region,
                    day_start_pt,
                    prev_rating,
                    rating,
                    estimate_placement(prev_rating, rating) AS placement,
                    day_start_pt - EXTRACT(DOW FROM day_start_pt)::integer 
                        + CASE WHEN EXTRACT(DOW FROM day_start_pt) = 0 THEN -6 ELSE 1 END AS week_start
                FROM all_snapshots
                WHERE prev_rating IS NOT NULL 
                  AND prev_rating IS DISTINCT FROM rating
            ),
            daily_stats AS (
                SELECT 
                    player_id,
                    game_mode,
                    region,
                    day_start_pt AS day_start,
                    AVG(placement) AS day_avg
                FROM rating_changes
                GROUP BY player_id, game_mode, region, day_start_pt
            ),
            all_daily_rows AS (
                SELECT 
                    player_id,
                    game_mode,
                    region,
                    day_start,
                    day_start - EXTRACT(DOW FROM day_start)::integer 
                        + CASE WHEN EXTRACT(DOW FROM day_start) = 0 THEN -6 ELSE 1 END AS week_start
                FROM {DAILY_LEADERBOARD_STATS}
                {filter_clause}
            ),
            weekly_stats AS (
                SELECT 
                    adr.player_id,
                    adr.game_mode,
                    adr.region,
                    adr.day_start,
                    AVG(rc.placement) AS weekly_avg
                FROM all_daily_rows adr
                INNER JOIN rating_changes rc ON
                    rc.player_id = adr.player_id
                    AND rc.game_mode = adr.game_mode
                    AND rc.region = adr.region
                    AND rc.week_start = adr.week_start
                    AND rc.day_start_pt <= adr.day_start
                GROUP BY adr.player_id, adr.game_mode, adr.region, adr.day_start
            ),
            final_stats AS (
                SELECT 
                    COALESCE(ds.player_id, ws.player_id) AS player_id,
                    COALESCE(ds.game_mode, ws.game_mode) AS game_mode,
                    COALESCE(ds.region, ws.region) AS region,
                    COALESCE(ds.day_start, ws.day_start) AS day_start,
                    ds.day_avg,
                    ws.weekly_avg
                FROM daily_stats ds
                FULL OUTER JOIN weekly_stats ws ON
                    ds.player_id = ws.player_id
                    AND ds.game_mode = ws.game_mode
                    AND ds.region = ws.region
                    AND ds.day_start = ws.day_start
            )
            SELECT COUNT(*) as rows_to_update
            FROM {DAILY_LEADERBOARD_STATS} dls
            INNER JOIN final_stats fs ON
                dls.player_id = fs.player_id
                AND dls.game_mode = fs.game_mode
                AND dls.region = fs.region
                AND dls.day_start = fs.day_start
                AND (
                    dls.day_avg IS DISTINCT FROM fs.day_avg 
                    OR dls.weekly_avg IS DISTINCT FROM fs.weekly_avg
                )
            """,
            query_params,
        )
        result = cursor.fetchone()
        rows_to_update = result["rows_to_update"] if result else 0
        return rows_to_update
    else:
        # Execute update query
        cursor.execute(update_query, query_params)
        rows_updated = cursor.rowcount
        conn.commit()
        return rows_updated


def recalculate_averages(
    conn, dry_run=False, player_id=None, region=None, game_mode=None
):
    """
    Recalculate day_avg and weekly_avg for all rows in daily_leaderboard_stats.
    Processes in batches by region/game_mode to avoid timeouts.

    Args:
        conn: Database connection
        dry_run: If True, only show what would be updated
        player_id: Optional player_id to filter by (for testing)
        region: Optional region to filter by (for testing)
        game_mode: Optional game_mode to filter by (for testing)
    """
    cursor = conn.cursor(cursor_factory=DictCursor)

    try:
        # If specific filters are provided, process just that batch
        if player_id is not None or region is not None or game_mode is not None:
            print(
                f"Processing: player_id={player_id}, region={region}, game_mode={game_mode}"
            )
            if dry_run:
                rows = recalculate_averages_batch(
                    conn,
                    cursor,
                    dry_run=True,
                    player_id=player_id,
                    region=region,
                    game_mode=game_mode,
                )
                print(f"Would update {rows} rows")
            else:
                rows = recalculate_averages_batch(
                    conn,
                    cursor,
                    dry_run=False,
                    player_id=player_id,
                    region=region,
                    game_mode=game_mode,
                )
                print(f"✓ Updated {rows} rows")
            return

        # Process all players in batches by region/game_mode
        print("Processing all players/regions/game modes in batches...")
        regions = ["NA", "EU", "AP", "CN"]
        game_modes = [0, 1]  # 0 = solo, 1 = duo
        total_updated = 0

        for region_batch in regions:
            for game_mode_batch in game_modes:
                print(
                    f"\nProcessing batch: region={region_batch}, game_mode={game_mode_batch}"
                )

                if dry_run:
                    rows = recalculate_averages_batch(
                        conn,
                        cursor,
                        dry_run=True,
                        region=region_batch,
                        game_mode=game_mode_batch,
                    )
                    print(
                        f"Would update {rows} rows for {region_batch}/{game_mode_batch}"
                    )
                else:
                    rows = recalculate_averages_batch(
                        conn,
                        cursor,
                        dry_run=False,
                        region=region_batch,
                        game_mode=game_mode_batch,
                    )
                    print(f"✓ Updated {rows} rows for {region_batch}/{game_mode_batch}")
                    total_updated += rows

        if not dry_run:
            print(f"\nTotal rows updated: {total_updated}")

    except Exception as e:
        conn.rollback()
        print(f"Error: {e}")
        raise
    finally:
        cursor.close()


def main():
    """Main entry point."""
    print("=" * 60)
    print("Recalculate daily_leaderboard_stats day_avg and weekly_avg")
    print("=" * 60)
    print(f"Mode: {'DRY RUN' if DRY_RUN else 'LIVE UPDATE'}")
    print()

    conn = None
    try:
        conn = get_db_connection()
        # Increase statement timeout for large bulk updates (30 minutes)
        with conn.cursor() as timeout_cursor:
            timeout_cursor.execute("SET statement_timeout = '30min'")
        cursor = conn.cursor(cursor_factory=DictCursor)

        # Ensure estimate_placement function exists with 10000 threshold
        ensure_estimate_placement_function(cursor)
        conn.commit()

        # Handle test configuration
        player_id = None
        region = None
        game_mode = None

        if TEST_PLAYER_NAME:
            player_id = get_player_id(cursor, TEST_PLAYER_NAME)
            if not player_id:
                print(f"Error: Player '{TEST_PLAYER_NAME}' not found in database")
                return 1
            print(f"Found player_id={player_id} for player_name='{TEST_PLAYER_NAME}'")

        if TEST_REGION:
            region = TEST_REGION
            print(f"Filtering by region: {region}")

        if TEST_GAME_MODE is not None:
            game_mode = TEST_GAME_MODE
            print(f"Filtering by game_mode: {game_mode}")

        # Recalculate averages
        recalculate_averages(
            conn,
            dry_run=DRY_RUN,
            player_id=player_id,
            region=region,
            game_mode=game_mode,
        )

        print("\n" + "=" * 60)
        if DRY_RUN:
            print("DRY RUN completed. Set DRY_RUN = False to apply changes.")
        else:
            print("Recalculation completed successfully!")
        print("=" * 60)

    except Exception as e:
        print(f"\nError: {e}")
        import traceback

        traceback.print_exc()
        return 1
    finally:
        if conn:
            conn.close()

    return 0


if __name__ == "__main__":
    sys.exit(main())
