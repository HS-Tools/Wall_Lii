#!/usr/bin/env python3
"""
One-off script to recalculate day_avg and weekly_avg in daily_leaderboard_stats table
using the updated estimate_placement function and data from leaderboard_snapshots.

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
DRY_RUN = False  # Set to False to enable writes

# Test configuration - set to None to process all players
TEST_PLAYER_NAME = "gaiabot"  # Set to None to process all players
TEST_REGION = "AP"  # Set to None to process all regions
TEST_GAME_MODE = 0  # Set to None to process all game modes (0 = solo, 1 = duo)

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
    """Create or replace the estimate_placement PostgreSQL function."""
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
                
                -- Skip placements where avg_opp > 8500
                IF avg_opp > 8500 THEN
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
    print("✓ estimate_placement function created/updated")


def recalculate_averages(
    conn, dry_run=False, player_id=None, region=None, game_mode=None
):
    """
    Recalculate day_avg and weekly_avg for all rows in daily_leaderboard_stats.

    Strategy:
    1. For each row in daily_leaderboard_stats, we need to:
       - Get all snapshots for that player/region/game_mode
       - Identify rating changes (when rating differs from previous snapshot)
       - Calculate placements for each change
       - Group by day_start (PT) for day_avg
       - Group by week_start (Monday PT) for weekly_avg
       - Calculate weighted averages

    2. We'll use a SQL query that:
       - Gets all snapshots with LAG to identify changes
       - Calculates placements for each change
       - Groups by day_start and week_start
       - Joins back to daily_leaderboard_stats to update

    Args:
        conn: Database connection
        dry_run: If True, only show what would be updated
        player_id: Optional player_id to filter by (for testing)
        region: Optional region to filter by (for testing)
        game_mode: Optional game_mode to filter by (for testing)
    """
    cursor = conn.cursor(cursor_factory=DictCursor)

    try:
        # Build filter conditions for testing
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
            print(
                f"Filtering by: player_id={player_id}, region={region}, game_mode={game_mode}"
            )

        # Step 1: Create a CTE that identifies all rating changes with their placements
        # We'll process this in batches by date range to avoid memory issues
        print("Fetching all daily_leaderboard_stats rows...")
        cursor.execute(
            f"""
            SELECT DISTINCT day_start
            FROM {DAILY_LEADERBOARD_STATS}
            {filter_clause}
            ORDER BY day_start
            """,
            tuple(filter_params),
        )
        all_dates = [row["day_start"] for row in cursor.fetchall()]
        print(f"Found {len(all_dates)} unique dates to process")

        if not all_dates:
            print("No data to process")
            return

        # Process in batches - we'll recalculate for all rows at once using a comprehensive SQL query
        print("\nCalculating averages from leaderboard_snapshots...")

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

        # Main query: Calculate day_avg and weekly_avg for all rows
        # Strategy:
        # 1. For each row in daily_leaderboard_stats, we need:
        #    - day_avg: average of placements for rating changes on that specific day (PT)
        #    - weekly_avg: average of placements for rating changes from week_start (Monday PT) through that day
        # 2. We'll use a CTE to identify all rating changes, then join back to daily_leaderboard_stats
        #    to calculate cumulative weekly averages

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
            -- Filter to only rating changes and calculate placements
            SELECT 
                player_id,
                game_mode,
                region,
                day_start_pt,
                prev_rating,
                rating,
                estimate_placement(prev_rating, rating) AS placement
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
            -- Get all rows from daily_leaderboard_stats to ensure we update all rows
            SELECT 
                player_id,
                game_mode,
                region,
                day_start,
                -- Calculate week_start for each day
                day_start - EXTRACT(DOW FROM day_start)::integer 
                    + CASE WHEN EXTRACT(DOW FROM day_start) = 0 THEN -6 ELSE 1 END AS week_start
            FROM {DAILY_LEADERBOARD_STATS}
            {filter_clause}
        ),
        final_stats AS (
            -- Join all daily rows with calculated averages
            SELECT 
                adr.player_id,
                adr.game_mode,
                adr.region,
                adr.day_start,
                ds.day_avg,
                -- Calculate weekly_avg for each day from week_start through day_start
                (SELECT AVG(rc2.placement)
                 FROM rating_changes rc2
                 WHERE rc2.player_id = adr.player_id
                   AND rc2.game_mode = adr.game_mode
                   AND rc2.region = adr.region
                   AND rc2.day_start_pt >= adr.week_start
                   AND rc2.day_start_pt <= adr.day_start) AS weekly_avg
            FROM all_daily_rows adr
            LEFT JOIN daily_stats ds ON
                ds.player_id = adr.player_id
                AND ds.game_mode = adr.game_mode
                AND ds.region = adr.region
                AND ds.day_start = adr.day_start
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

        # Combine parameters for the query (snapshot params first, then daily stats params)
        # Since both use the same filters, we can reuse the same parameter list
        query_params = tuple(snapshot_filter_params + filter_params)

        if dry_run:
            print("\n[DRY RUN] Would execute update query...")
            print("To actually update, set DRY_RUN = False")

            # For dry run, let's show what would be updated
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
                        estimate_placement(prev_rating, rating) AS placement
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
                daily_with_week AS (
                    SELECT 
                        d.player_id,
                        d.game_mode,
                        d.region,
                        d.day_start,
                        d.day_avg,
                        d.day_start - EXTRACT(DOW FROM d.day_start)::integer 
                            + CASE WHEN EXTRACT(DOW FROM d.day_start) = 0 THEN -6 ELSE 1 END AS week_start
                    FROM daily_stats d
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
                final_stats AS (
                    SELECT 
                        adr.player_id,
                        adr.game_mode,
                        adr.region,
                        adr.day_start,
                        ds.day_avg,
                        (SELECT AVG(rc2.placement)
                         FROM rating_changes rc2
                         WHERE rc2.player_id = adr.player_id
                           AND rc2.game_mode = adr.game_mode
                           AND rc2.region = adr.region
                           AND rc2.day_start_pt >= adr.week_start
                           AND rc2.day_start_pt <= adr.day_start) AS weekly_avg
                    FROM all_daily_rows adr
                    LEFT JOIN daily_stats ds ON
                        ds.player_id = adr.player_id
                        AND ds.game_mode = adr.game_mode
                        AND ds.region = adr.region
                        AND ds.day_start = adr.day_start
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
            print(f"Would update {rows_to_update} rows")

            # Show a sample of what would change
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
                        estimate_placement(prev_rating, rating) AS placement
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
                daily_with_week AS (
                    SELECT 
                        d.player_id,
                        d.game_mode,
                        d.region,
                        d.day_start,
                        d.day_avg,
                        d.day_start - EXTRACT(DOW FROM d.day_start)::integer 
                            + CASE WHEN EXTRACT(DOW FROM d.day_start) = 0 THEN -6 ELSE 1 END AS week_start
                    FROM daily_stats d
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
                final_stats AS (
                    SELECT 
                        adr.player_id,
                        adr.game_mode,
                        adr.region,
                        adr.day_start,
                        ds.day_avg,
                        (SELECT AVG(rc2.placement)
                         FROM rating_changes rc2
                         WHERE rc2.player_id = adr.player_id
                           AND rc2.game_mode = adr.game_mode
                           AND rc2.region = adr.region
                           AND rc2.day_start_pt >= adr.week_start
                           AND rc2.day_start_pt <= adr.day_start) AS weekly_avg
                    FROM all_daily_rows adr
                    LEFT JOIN daily_stats ds ON
                        ds.player_id = adr.player_id
                        AND ds.game_mode = adr.game_mode
                        AND ds.region = adr.region
                        AND ds.day_start = adr.day_start
                )
                SELECT 
                    dls.player_id,
                    dls.game_mode,
                    dls.region,
                    dls.day_start,
                    dls.day_avg AS old_day_avg,
                    fs.day_avg AS new_day_avg,
                    dls.weekly_avg AS old_weekly_avg,
                    fs.weekly_avg AS new_weekly_avg,
                    dls.games_played,
                    dls.weekly_games_played
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
                    AND dls.day_start IN ('2025-12-08'::date, '2025-12-09'::date, '2025-12-10'::date)
                ORDER BY dls.day_start
                """,
                query_params,
            )
            samples = cursor.fetchall()
            if samples:
                print(
                    "\nChanges for day_start in (2025-12-08, 2025-12-09, 2025-12-10):"
                )
                for sample in samples:
                    print(
                        f"\n  player_id={sample['player_id']}, game_mode={sample['game_mode']}, "
                        f"region={sample['region']}, day_start={sample['day_start']}"
                    )
                    print(
                        f"    day_avg: {sample['old_day_avg']} -> {sample['new_day_avg']}"
                    )
                    print(
                        f"    weekly_avg: {sample['old_weekly_avg']} -> {sample['new_weekly_avg']}"
                    )
                    if sample["day_start"] == "2025-12-10":
                        print(f"    games_played: {sample['games_played']}")
                        print(
                            f"    weekly_games_played: {sample['weekly_games_played']}"
                        )

                    # Get individual placements for this day
                    # Combine snapshot filter params with WHERE clause params
                    placement_query_params = list(snapshot_filter_params) + [
                        sample["player_id"],
                        str(sample["game_mode"]),
                        sample["region"],
                        sample["day_start"],
                    ]
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
                                snapshot_time,
                                prev_rating,
                                rating,
                                estimate_placement(prev_rating, rating) AS placement
                            FROM all_snapshots
                            WHERE prev_rating IS NOT NULL 
                              AND prev_rating IS DISTINCT FROM rating
                        )
                        SELECT placement
                        FROM rating_changes
                        WHERE player_id = %s
                          AND game_mode = %s::game_mode_enum
                          AND region = %s
                          AND day_start_pt = %s
                        ORDER BY snapshot_time
                        """,
                        tuple(placement_query_params),
                    )
                    placements = cursor.fetchall()
                    if placements:
                        placement_values = [str(p["placement"]) for p in placements]
                        print(f"    placements: {', '.join(placement_values)}")
                    else:
                        print("    placements: (no rating changes)")
        else:
            print("\nExecuting update query...")
            cursor.execute(update_query, query_params)
            rows_updated = cursor.rowcount
            conn.commit()
            print(f"✓ Updated {rows_updated} rows")

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
        cursor = conn.cursor(cursor_factory=DictCursor)

        # Ensure estimate_placement function exists
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
