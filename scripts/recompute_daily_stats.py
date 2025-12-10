"""
Recompute day_avg and weekly_avg in DAILY_LEADERBOARD_STATS using the
current estimate_placement logic from src/utils/placement_utils.py and
historical snapshots from LEADERBOARD_SNAPSHOTS.

Usage:
  python3 scripts/recompute_daily_stats.py [--days 30]

Env:
  DB_HOST, DB_PORT, DB_NAME, DB_USER, DB_PASSWORD (loaded from env or .env)
"""

import argparse
import os
import sys
from collections import defaultdict
from datetime import date, timedelta

import psycopg2
from psycopg2.extras import execute_batch
from dotenv import load_dotenv

# Import estimate_placement from the repo
ROOT = os.path.abspath(os.path.join(os.path.dirname(__file__), ".."))
sys.path.append(ROOT)
from config import NORMALIZED_TABLES  # type: ignore
from src.utils.placement_utils import estimate_placement  # type: ignore

load_dotenv()


def _require(name: str, default=None):
    val = os.getenv(name, default)
    if val is None:
        raise RuntimeError(f"Environment variable {name} is required.")
    return val


def get_conn():
    return psycopg2.connect(
        host=_require("DB_HOST"),
        port=os.getenv("DB_PORT", 5432),
        dbname=_require("DB_NAME"),
        user=_require("DB_USER"),
        password=_require("DB_PASSWORD"),
    )


def fetch_snapshots(conn, days_back):
    """Fetch snapshots for the last N days, ordered for processing."""
    snapshots_table = NORMALIZED_TABLES["leaderboard_snapshots"]
    with conn.cursor() as cur:
        cur.execute(
            f"""
            SELECT player_id,
                   game_mode,
                   region,
                   rating,
                   snapshot_time::date AS day_start,
                   snapshot_time
            FROM {snapshots_table}
            WHERE snapshot_time >= CURRENT_DATE - interval %s
            ORDER BY player_id, game_mode, region, snapshot_time
            """,
            (f"{days_back} days",),
        )
        return cur.fetchall()


def compute_day_metrics(rows):
    """
    Compute day-level averages and games_played from ordered snapshots.
    rows: list of tuples (player_id, game_mode, region, rating, day_start, snapshot_time)
    Returns dict keyed by (player_id, game_mode, region, day_start) ->
      {games_played, day_avg}
    """
    grouped = defaultdict(list)
    for pid, gm, reg, rating, day_start, snap_ts in rows:
        grouped[(pid, gm, reg, day_start)].append((snap_ts, rating))

    results = {}
    for key, items in grouped.items():
        # items already ordered by snapshot_time
        ratings = [r for _, r in items]
        placements = []
        for i in range(len(ratings) - 1):
            placements.append(
                estimate_placement(ratings[i], ratings[i + 1])["placement"]
            )

        games_played = len(placements)
        day_avg = None
        if games_played > 0:
            day_avg = sum(placements) / games_played

        results[key] = {"games_played": games_played, "day_avg": day_avg}
    return results


def compute_weekly_metrics(day_metrics):
    """
    Compute weekly averages/games from day-level metrics.
    day_metrics: dict keyed by (pid, gm, reg, day_start) -> {games_played, day_avg}
    Returns dict keyed by same -> {weekly_games_played, weekly_avg}
    """
    # Organize by player/game_mode/region then by day
    by_player = defaultdict(list)
    for (pid, gm, reg, day_start), vals in day_metrics.items():
        by_player[(pid, gm, reg)].append((day_start, vals))

    weekly = {}
    for pkey, entries in by_player.items():
        entries.sort(key=lambda x: x[0])
        for idx, (day, vals) in enumerate(entries):
            window_start = day - timedelta(days=6)
            # Collect last 7 days including current
            w_games = 0
            w_weighted_sum = 0.0
            for d2, v2 in entries:
                if window_start <= d2 <= day:
                    gp = v2["games_played"]
                    if gp and v2["day_avg"] is not None:
                        w_games += gp
                        w_weighted_sum += v2["day_avg"] * gp
            if w_games > 0:
                w_avg = w_weighted_sum / w_games
            else:
                w_avg = None
            weekly[(pkey[0], pkey[1], pkey[2], day)] = {
                "weekly_games_played": w_games,
                "weekly_avg": w_avg,
            }
    return weekly


def apply_updates(conn, day_metrics, weekly_metrics):
    """Update DAILY_LEADERBOARD_STATS with recomputed averages."""
    daily_table = NORMALIZED_TABLES["daily_leaderboard_stats"]
    rows = []
    for key, dvals in day_metrics.items():
        pid, gm, reg, day = key
        wvals = weekly_metrics.get(
            key, {"weekly_games_played": None, "weekly_avg": None}
        )
        rows.append(
            (
                dvals["games_played"],
                dvals["day_avg"],
                wvals["weekly_games_played"],
                wvals["weekly_avg"],
                pid,
                gm,
                reg,
                day,
            )
        )

    with conn.cursor() as cur:
        execute_batch(
            cur,
            f"""
            UPDATE {daily_table}
            SET games_played = %(games_played)s,
                day_avg = %(day_avg)s,
                weekly_games_played = %(weekly_games_played)s,
                weekly_avg = %(weekly_avg)s,
                updated_at = now()
            WHERE player_id = %(pid)s
              AND game_mode = %(gm)s
              AND region = %(reg)s
              AND day_start = %(day)s
            """,
            [
                {
                    "games_played": r[0],
                    "day_avg": r[1],
                    "weekly_games_played": r[2],
                    "weekly_avg": r[3],
                    "pid": r[4],
                    "gm": r[5],
                    "reg": r[6],
                    "day": r[7],
                }
                for r in rows
            ],
            page_size=500,
        )
    conn.commit()
    print(f"Updated {len(rows)} daily rows.")


def main():
    parser = argparse.ArgumentParser(
        description="Recompute day/weekly averages from snapshots."
    )
    parser.add_argument(
        "--days", type=int, default=30, help="Days back to process (default: 30)"
    )
    args = parser.parse_args()

    conn = get_conn()
    try:
        snaps = fetch_snapshots(conn, args.days)
        if not snaps:
            print("No snapshots found in range.")
            return
        day_metrics = compute_day_metrics(snaps)
        weekly_metrics = compute_weekly_metrics(day_metrics)
        apply_updates(conn, day_metrics, weekly_metrics)
    finally:
        conn.close()


if __name__ == "__main__":
    main()
