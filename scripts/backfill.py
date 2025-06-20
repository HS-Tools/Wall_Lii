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
    conn = get_db_connection()
    cur = conn.cursor()

    cur.execute(
        """
        WITH weekly_accumulation AS (
          SELECT 
            player_name,
            game_mode,
            region,
            day_start,
            games_played,
            -- Calculate cumulative weekly games using existing games_played
            SUM(games_played) OVER (
              PARTITION BY player_name, game_mode, region, date_trunc('week', day_start)
              ORDER BY day_start
              ROWS BETWEEN UNBOUNDED PRECEDING AND CURRENT ROW
            ) AS weekly_games_played
          FROM daily_leaderboard_stats
        )
        UPDATE daily_leaderboard_stats 
        SET weekly_games_played = weekly_accumulation.weekly_games_played
        FROM weekly_accumulation
        WHERE daily_leaderboard_stats.player_name = weekly_accumulation.player_name
          AND daily_leaderboard_stats.game_mode = weekly_accumulation.game_mode
          AND daily_leaderboard_stats.region = weekly_accumulation.region
          AND daily_leaderboard_stats.day_start = weekly_accumulation.day_start;
        """
    )

    conn.commit()
    cur.close()
    conn.close()


if __name__ == "__main__":
    main()
