#!/usr/bin/env python3
"""
Rebuild day_avg and weekly_avg in daily_leaderboard_stats using leaderboard_snapshots.

The script recomputes placement averages per player/game_mode/region by:
- Converting snapshot_time to America/Los_Angeles (PT) dates.
- Calculating placements for rating changes (consecutive ratings differ).
- Averaging placements per day (day_avg) and cumulatively within the PT week (weekly_avg).
- Updating only day_avg and weekly_avg in daily_leaderboard_stats; all other fields remain untouched.

Defaults mirror the old recalc script's test scope (gaiabot/AP/solo) for safe dry runs.
Use --all-players to process everyone.
"""

import argparse
import os
import sys
from typing import Optional, Sequence, Tuple

from dotenv import load_dotenv, find_dotenv
from psycopg2.extras import DictCursor

from db_utils import get_db_connection


DEFAULT_TEST_PLAYER = "gaiabot"
DEFAULT_TEST_REGION = "AP"
DEFAULT_TEST_GAME_MODE = 0  # 0 = solo, 1 = duo

DAILY_LEADERBOARD_STATS = "daily_leaderboard_stats"
LEADERBOARD_SNAPSHOTS = "leaderboard_snapshots"
PLAYERS_TABLE = "players"


def load_env(env_name: str) -> None:
    """
    Load environment variables, preferring a per-env file if present (e.g., .env.prod).
    """
    candidate = f".env.{env_name}"
    if os.path.exists(candidate):
        load_dotenv(candidate)
    else:
        load_dotenv(find_dotenv())


def get_player_id(cursor, player_name: str) -> Optional[int]:
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


def build_computed_cte(snapshot_clause: str, target_clause: str) -> str:
    """
    Build the common CTE that computes day_avg and weekly_avg from snapshots.
    """
    return f"""
WITH snapshots AS (
    SELECT
        ls.player_id,
        ls.game_mode,
        ls.region,
        ls.rating,
        (ls.snapshot_time AT TIME ZONE 'America/Los_Angeles')::date AS day_start_pt,
        LAG(ls.rating) OVER (
            PARTITION BY ls.player_id, ls.game_mode, ls.region
            ORDER BY ls.snapshot_time
        ) AS prev_rating
    FROM {LEADERBOARD_SNAPSHOTS} ls
    {snapshot_clause}
),
rating_changes AS (
    SELECT
        player_id,
        game_mode,
        region,
        day_start_pt,
        estimate_placement(prev_rating, rating) AS placement
    FROM snapshots
    WHERE prev_rating IS NOT NULL
      AND prev_rating IS DISTINCT FROM rating
),
daily_placements AS (
    SELECT
        player_id,
        game_mode,
        region,
        day_start_pt AS day_start,
        AVG(placement) AS day_avg
    FROM rating_changes
    GROUP BY player_id, game_mode, region, day_start_pt
),
target_rows AS (
    SELECT
        dls.player_id,
        dls.game_mode,
        dls.region,
        dls.day_start,
        dls.day_start - EXTRACT(DOW FROM dls.day_start)::integer
            + CASE WHEN EXTRACT(DOW FROM dls.day_start) = 0 THEN -6 ELSE 1 END AS week_start
    FROM {DAILY_LEADERBOARD_STATS} dls
    {target_clause}
),
computed AS (
    SELECT
        tr.player_id,
        tr.game_mode,
        tr.region,
        tr.day_start,
        dp.day_avg,
        (
            SELECT AVG(rc.placement)
            FROM rating_changes rc
            WHERE rc.player_id = tr.player_id
              AND rc.game_mode = tr.game_mode
              AND rc.region = tr.region
              AND rc.day_start_pt >= tr.week_start
              AND rc.day_start_pt <= tr.day_start
        ) AS weekly_avg
    FROM target_rows tr
    LEFT JOIN daily_placements dp
      ON dp.player_id = tr.player_id
     AND dp.game_mode = tr.game_mode
     AND dp.region = tr.region
     AND dp.day_start = tr.day_start
)
"""


def run_dry_run(
    cursor, computed_cte: str, params: Sequence, sample_limit: int = 20
) -> None:
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
WHERE d.day_avg IS DISTINCT FROM c.day_avg
   OR d.weekly_avg IS DISTINCT FROM c.weekly_avg;
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
  d.day_avg AS current_day_avg,
  c.day_avg AS recomputed_day_avg,
  d.weekly_avg AS current_weekly_avg,
  c.weekly_avg AS recomputed_weekly_avg
FROM {DAILY_LEADERBOARD_STATS} d
INNER JOIN computed c
  ON d.player_id = c.player_id
 AND d.game_mode = c.game_mode
 AND d.region = c.region
 AND d.day_start = c.day_start
WHERE d.day_avg IS DISTINCT FROM c.day_avg
   OR d.weekly_avg IS DISTINCT FROM c.weekly_avg
ORDER BY d.day_start DESC
LIMIT %s;
""",
        list(params) + [sample_limit],
    )
    sample = cursor.fetchall()

    print("\n[DRY RUN] Summary")
    print(f"Target rows considered: {target_rows}")
    print(f"Rows that would update: {rows_to_update}")
    if sample:
        print("\nSample differences (up to {limit}):".format(limit=sample_limit))
        for row in sample:
            print(
                f"- {row['player_id']} {row['game_mode']} {row['region']} {row['day_start']}: "
                f"day_avg {row['current_day_avg']} -> {row['recomputed_day_avg']}, "
                f"weekly_avg {row['current_weekly_avg']} -> {row['recomputed_weekly_avg']}"
            )
    else:
        print("No differences detected.")


def apply_updates(cursor, computed_cte: str, params: Sequence) -> int:
    cursor.execute(
        f"""{computed_cte}
UPDATE {DAILY_LEADERBOARD_STATS} d
SET
  day_avg = c.day_avg,
  weekly_avg = c.weekly_avg
FROM computed c
WHERE d.player_id = c.player_id
  AND d.game_mode = c.game_mode
  AND d.region = c.region
  AND d.day_start = c.day_start
  AND (
    d.day_avg IS DISTINCT FROM c.day_avg
    OR d.weekly_avg IS DISTINCT FROM c.weekly_avg
  );
""",
        params,
    )
    return cursor.rowcount


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(
        description="Recompute day_avg and weekly_avg in daily_leaderboard_stats using leaderboard_snapshots (PT-based)."
    )
    parser.add_argument(
        "--env",
        choices=["prod", "staging"],
        required=True,
        help="Environment to target; loads .env.<env> if present.",
    )
    parser.add_argument(
        "--apply",
        action="store_true",
        help="Apply updates (default is dry-run log only).",
    )
    parser.add_argument(
        "--all-players",
        action="store_true",
        help="Process all players/regions/game modes (ignores test defaults).",
    )
    parser.add_argument(
        "--player-name",
        default=DEFAULT_TEST_PLAYER,
        help="Player name filter (default: gaiabot). Ignored if --all-players.",
    )
    parser.add_argument(
        "--region",
        default=DEFAULT_TEST_REGION,
        help="Region filter (default: AP). Ignored if --all-players.",
    )
    parser.add_argument(
        "--game-mode",
        type=int,
        choices=[0, 1],
        default=DEFAULT_TEST_GAME_MODE,
        help="Game mode filter: 0=solo, 1=duo (default: 0). Ignored if --all-players.",
    )
    parser.add_argument(
        "--sample-limit",
        type=int,
        default=20,
        help="Max sample rows to print during dry-run.",
    )
    return parser.parse_args()


def main() -> int:
    args = parse_args()
    load_env(args.env)

    conn = None
    try:
        conn = get_db_connection()
        cursor = conn.cursor(cursor_factory=DictCursor)

        player_id: Optional[int] = None
        region: Optional[str] = None
        game_mode: Optional[int] = None

        if not args.all_players:
            player_id = get_player_id(cursor, args.player_name)
            if player_id is None:
                print(f"Player '{args.player_name}' not found; aborting.")
                return 1
            region = args.region
            game_mode = args.game_mode
            print(
                f"Testing scope -> player_id={player_id}, region={region}, game_mode={game_mode} "
                "(pass --all-players to process everything)."
            )
        else:
            print("Processing all players/regions/game modes.")

        snapshot_clause, snapshot_params = build_filter_clauses(
            player_id, region, game_mode, "ls"
        )
        target_clause, target_params = build_filter_clauses(
            player_id, region, game_mode, "dls"
        )
        params = snapshot_params + target_params

        computed_cte = build_computed_cte(snapshot_clause, target_clause)

        if not args.apply:
            run_dry_run(cursor, computed_cte, params, sample_limit=args.sample_limit)
            return 0

        print("Applying updates...")
        updated = apply_updates(cursor, computed_cte, params)
        conn.commit()
        print(f"Updated rows: {updated}")
        return 0

    except Exception as exc:  # pragma: no cover - defensive logging
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
