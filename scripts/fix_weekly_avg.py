#!/usr/bin/env python3
"""
Fix weekly_avg in daily_leaderboard_stats by recalculating it from existing day_avg and games_played.

This script recalculates weekly_avg as a weighted average:
    weekly_avg = Σ(day_avg * games_played) / weekly_games_played

Where the sum is over all days in the week (Monday through day_start, inclusive).
This uses only data already in daily_leaderboard_stats (day_avg, games_played, weekly_games_played)
which are already correct, so we don't need to access leaderboard_snapshots.
"""

import argparse
import os
import sys
from typing import Optional, Tuple

from dotenv import load_dotenv, find_dotenv
from psycopg2.extras import DictCursor
import psycopg2

from db_utils import get_db_connection


DAILY_LEADERBOARD_STATS = "daily_leaderboard_stats"
PLAYERS_TABLE = "players"


def load_env(env_name: Optional[str] = None) -> None:
    """
    Load environment variables, preferring a per-env file if present (e.g., .env.prod).
    If env_name is None, just loads the default .env file.
    """
    if env_name:
        candidate = f".env.{env_name}"
        if os.path.exists(candidate):
            load_dotenv(candidate)
            return
    load_dotenv(find_dotenv())


def get_player_id(cursor, player_name: str) -> Optional[int]:
    """Get player_id for a given player_name."""
    cursor.execute(
        f"""
        SELECT player_id
        FROM {PLAYERS_TABLE}
        WHERE player_name = %s
        """,
        (player_name.lower(),),
    )
    result = cursor.fetchone()
    return result["player_id"] if result else None


def build_filter_clauses(
    player_id: Optional[int],
    region: Optional[str],
    game_mode: Optional[int],
    alias: str,
) -> Tuple[str, list]:
    """Build WHERE clause and parameters for filtering."""
    conditions = []
    params = []

    if player_id is not None:
        conditions.append(f"{alias}.player_id = %s")
        params.append(player_id)
    if region is not None:
        conditions.append(f"{alias}.region = %s::region_enum")
        params.append(region)
    if game_mode is not None:
        conditions.append(f"{alias}.game_mode = %s::game_mode_enum")
        params.append(str(game_mode))

    clause = ""
    if conditions:
        clause = "WHERE " + " AND ".join(conditions)
    return clause, params


def build_computed_cte(target_clause: str) -> str:
    """
    Build the CTE that computes weekly_avg from day_avg and games_played.

    Formula: weekly_avg = Σ(day_avg * games_played) / weekly_games_played
    Where the sum is over all days from week_start (Monday) through day_start.
    """
    return f"""
WITH target_rows AS (
    SELECT 
        dls.player_id,
        dls.game_mode,
        dls.region,
        dls.day_start,
        dls.day_start - EXTRACT(DOW FROM dls.day_start)::integer
            + CASE WHEN EXTRACT(DOW FROM dls.day_start) = 0 THEN -6 ELSE 1 END AS week_start,
        dls.weekly_games_played
    FROM {DAILY_LEADERBOARD_STATS} dls
    {target_clause}
),
computed AS (
    SELECT 
        tr.player_id,
        tr.game_mode,
        tr.region,
        tr.day_start,
        CASE 
            WHEN tr.weekly_games_played = 0 THEN NULL
            ELSE SUM(d.day_avg * d.games_played) / NULLIF(tr.weekly_games_played, 0)
        END AS weekly_avg
    FROM target_rows tr
    JOIN {DAILY_LEADERBOARD_STATS} d ON
        d.player_id = tr.player_id
        AND d.game_mode = tr.game_mode
        AND d.region = tr.region
        AND d.day_start >= tr.week_start
        AND d.day_start <= tr.day_start
    WHERE d.day_avg IS NOT NULL AND d.games_played > 0
    GROUP BY tr.player_id, tr.game_mode, tr.region, tr.day_start, tr.weekly_games_played
)
"""


def run_dry_run(
    cursor, computed_cte: str, params: list, sample_limit: int = 20
) -> None:
    """Run a dry-run query to show what would be updated."""
    cursor.execute(
        f"""{computed_cte}
SELECT COUNT(*) AS target_rows FROM computed;
""",
        params,
    )
    target_rows = cursor.fetchone()["target_rows"]

    cursor.execute(
        f"""{computed_cte}
SELECT COUNT(*) AS rows_to_update
FROM {DAILY_LEADERBOARD_STATS} d
INNER JOIN computed c
  ON d.player_id = c.player_id
 AND d.game_mode = c.game_mode
 AND d.region = c.region
 AND d.day_start = c.day_start
WHERE d.weekly_avg IS DISTINCT FROM c.weekly_avg;
""",
        params,
    )
    rows_to_update = cursor.fetchone()["rows_to_update"]

    cursor.execute(
        f"""{computed_cte}
SELECT
  d.player_id,
  d.game_mode,
  d.region,
  d.day_start,
  d.weekly_avg AS current_weekly_avg,
  c.weekly_avg AS recomputed_weekly_avg,
  d.weekly_games_played
FROM {DAILY_LEADERBOARD_STATS} d
INNER JOIN computed c
  ON d.player_id = c.player_id
 AND d.game_mode = c.game_mode
 AND d.region = c.region
 AND d.day_start = c.day_start
WHERE d.weekly_avg IS DISTINCT FROM c.weekly_avg
ORDER BY d.day_start DESC
LIMIT %s;
""",
        params + [sample_limit],
    )
    sample = cursor.fetchall()

    print("\n[DRY RUN] Summary")
    print(f"Target rows considered: {target_rows}")
    print(f"Rows that would update: {rows_to_update}")
    if sample:
        print(f"\nSample differences (up to {sample_limit}):")
        for row in sample:
            print(
                f"- player_id={row['player_id']}, game_mode={row['game_mode']}, "
                f"region={row['region']}, day_start={row['day_start']}: "
                f"weekly_avg {row['current_weekly_avg']} -> {row['recomputed_weekly_avg']}, "
                f"weekly_games_played={row['weekly_games_played']}"
            )
    else:
        print("No differences detected.")


def apply_updates(cursor, connection, computed_cte: str, params: list) -> int:
    """Apply updates to weekly_avg."""
    cursor.execute(
        f"""{computed_cte}
UPDATE {DAILY_LEADERBOARD_STATS} d
SET
  weekly_avg = c.weekly_avg,
  updated_at = now()
FROM computed c
WHERE d.player_id = c.player_id
  AND d.game_mode = c.game_mode
  AND d.region = c.region
  AND d.day_start = c.day_start
  AND (d.weekly_avg IS DISTINCT FROM c.weekly_avg);
""",
        params,
    )
    return cursor.rowcount


def parse_args() -> argparse.Namespace:
    """Parse command-line arguments."""
    parser = argparse.ArgumentParser(
        description="Fix weekly_avg in daily_leaderboard_stats by recalculating from day_avg and games_played."
    )
    parser.add_argument(
        "--env",
        choices=["prod", "staging"],
        help="Environment to target; loads .env.<env> if present. If not specified, loads default .env.",
    )
    parser.add_argument(
        "--apply",
        action="store_true",
        help="Apply updates (default is dry-run log only).",
    )
    parser.add_argument(
        "--all-players",
        action="store_true",
        help="Process all players/regions/game modes (default behavior).",
    )
    parser.add_argument(
        "--player-name",
        help="Player name filter (ignored if --all-players).",
    )
    parser.add_argument(
        "--region",
        help="Region filter (ignored if --all-players).",
    )
    parser.add_argument(
        "--game-mode",
        type=int,
        choices=[0, 1],
        help="Game mode filter: 0=solo, 1=duo (ignored if --all-players).",
    )
    parser.add_argument(
        "--sample-limit",
        type=int,
        default=20,
        help="Max sample rows to print during dry-run.",
    )
    return parser.parse_args()


def main() -> int:
    """Main entry point."""
    args = parse_args()
    load_env(args.env)

    conn = None
    try:
        conn = get_db_connection()
        # Increase statement timeout for large bulk updates (30 minutes)
        with conn.cursor() as timeout_cursor:
            timeout_cursor.execute("SET statement_timeout = '30min'")
        cursor = conn.cursor(cursor_factory=DictCursor)

        player_id: Optional[int] = None
        region: Optional[str] = None
        game_mode: Optional[int] = None

        # Default is to process all players unless --player-name is specified
        if not args.all_players and args.player_name:
            player_id = get_player_id(cursor, args.player_name)
            if player_id is None:
                print(f"Player '{args.player_name}' not found; aborting.")
                return 1
            region = args.region
            game_mode = args.game_mode
            print(
                f"Processing scope -> player_id={player_id}, region={region}, game_mode={game_mode} "
                "(use --all-players to process everything)."
            )
        else:
            print("Processing all players/regions/game modes in batches.")
            # Process in batches by region/game_mode to avoid timeout
            regions = ["NA", "EU", "AP", "CN"]
            game_modes = [0, 1]  # 0 = solo, 1 = duo
            total_updated = 0

            for region_batch in regions:
                for game_mode_batch in game_modes:
                    print(
                        f"\nProcessing batch: region={region_batch}, game_mode={game_mode_batch}"
                    )

                    target_clause, target_params = build_filter_clauses(
                        None, region_batch, game_mode_batch, "dls"
                    )
                    computed_cte = build_computed_cte(target_clause)

                    if not args.apply:
                        run_dry_run(
                            cursor,
                            computed_cte,
                            target_params,
                            sample_limit=args.sample_limit,
                        )
                        continue

                    print(f"Applying updates for {region_batch}/{game_mode_batch}...")
                    updated = apply_updates(cursor, conn, computed_cte, target_params)
                    conn.commit()
                    print(
                        f"Updated {updated} rows for {region_batch}/{game_mode_batch}"
                    )
                    total_updated += updated

            if args.apply:
                print(f"\nTotal rows updated: {total_updated}")
            return 0

        # Single player/region/game_mode processing
        target_clause, target_params = build_filter_clauses(
            player_id, region, game_mode, "dls"
        )
        computed_cte = build_computed_cte(target_clause)

        if not args.apply:
            run_dry_run(
                cursor, computed_cte, target_params, sample_limit=args.sample_limit
            )
            return 0

        print("Applying updates...")
        updated = apply_updates(cursor, conn, computed_cte, target_params)
        conn.commit()
        print(f"Updated rows: {updated}")
        return 0

    except Exception as exc:
        print(f"Error: {exc}")
        import traceback

        traceback.print_exc()
        if conn:
            conn.rollback()
        return 1
    finally:
        if conn:
            conn.close()


if __name__ == "__main__":
    sys.exit(main())
