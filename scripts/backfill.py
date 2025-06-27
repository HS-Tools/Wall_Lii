#!/usr/bin/env python3
import os
import psycopg2
from psycopg2.extras import DictCursor
from datetime import datetime, timedelta
import pytz

# ─── CONFIGURE ────────────────────────────────────────────────────────────────
PT = pytz.timezone("America/Los_Angeles")
# ────────────────────────────────────────────────────────────────────────────────

# IMPORTANT: This script recalculates weekly_games_played using existing games_played data
# It assumes the daily_leaderboard_stats table is correct except for weekly_games_played


def get_db_connection():
    """
    Create and return a connection to the database using environment variables
    """
    return psycopg2.connect(
        host=os.environ.get("DB_HOST"),
        port=os.environ.get("DB_PORT", "5432"),
        dbname=os.environ.get("DB_NAME"),
        user=os.environ.get("DB_USER"),
        password=os.environ.get("DB_PASSWORD"),
        sslmode="require",
        cursor_factory=DictCursor,
    )


def main():
    DRY_RUN = False  # Set to False to enable writes
    conn = get_db_connection()
    cur = conn.cursor()

    pacific = pytz.timezone("America/Los_Angeles")
    now_pt = datetime.now(pacific)
    week_start = (now_pt - timedelta(days=now_pt.weekday())).date()

    # Step 1: Fetch relevant snapshots
    snapshots_by_player_day = {}
    snapshots_cursor = conn.cursor(name="snapshots_cursor", cursor_factory=DictCursor)
    snapshots_cursor.itersize = 10000
    snapshots_cursor.execute(
        """
        SELECT player_name, region, game_mode, snapshot_time, rating
        FROM leaderboard_snapshots
        WHERE snapshot_time >= %s
        ORDER BY snapshot_time
        """,
        (datetime.combine(week_start, datetime.min.time()).astimezone(pytz.utc),),
    )
    for row in snapshots_cursor:
        key = f"{row['player_name']}#{row['region']}#{row['game_mode']}"
        pt_date = row["snapshot_time"].astimezone(pacific).date()
        if pt_date >= week_start:
            snapshots_by_player_day.setdefault(key, {}).setdefault(pt_date, []).append(
                row["rating"]
            )
    snapshots_cursor.close()

    # Step 2: Fetch daily_leaderboard_stats for this week only
    cur.execute(
        """
        SELECT player_name, region, game_mode, day_start, rating
        FROM daily_leaderboard_stats
        WHERE day_start >= %s
        ORDER BY player_name, region, game_mode, day_start
        """,
        (week_start,),
    )
    stats_rows = cur.fetchall()
    stats_by_player = {}
    for row in stats_rows:
        key = f"{row['player_name']}#{row['region']}#{row['game_mode']}"
        stats_by_player.setdefault(key, []).append(row)

    # Step 3: Process each player
    total_updates = 0
    all_updates = []
    for key, stat_list in stats_by_player.items():
        prev_rating = None
        prev_weekly = 0
        snapshot_days = snapshots_by_player_day.get(key, {})

        for row in stat_list:
            day = row["day_start"]
            today_ratings = snapshot_days.get(day, [])

            if not today_ratings:
                curr_rating = row["rating"]
                games_played = 0
            else:
                games_played = 0
                last_rating = prev_rating
                for r in today_ratings:
                    if last_rating is not None and r != last_rating:
                        games_played += 1
                    last_rating = r
                curr_rating = last_rating

            is_monday = day.weekday() == 0
            weekly = games_played if is_monday else prev_weekly + games_played

            player_name, region, game_mode = (
                row["player_name"],
                row["region"],
                row["game_mode"],
            )
            all_updates.append(
                (games_played, weekly, player_name, region, game_mode, day)
            )
            prev_rating = curr_rating
            prev_weekly = weekly

        print(
            f"{'[DRY RUN]' if DRY_RUN else '[UPDATED]'} {key}: {len(stat_list)} rows processed"
        )
        total_updates += len(stat_list)

    # Step 4: Perform batch update
    if not DRY_RUN:
        from psycopg2.extras import execute_batch

        execute_batch(
            cur,
            """
            UPDATE daily_leaderboard_stats
            SET games_played = %s,
                weekly_games_played = %s
            WHERE player_name = %s AND region = %s AND game_mode = %s AND day_start = %s
        """,
            all_updates,
        )
        conn.commit()

    print(f"Total rows processed: {total_updates}")
    cur.close()
    conn.close()


if __name__ == "__main__":
    main()
