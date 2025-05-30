#!/usr/bin/env python3
import os
import psycopg2
from psycopg2.extras import DictCursor
from datetime import datetime, timedelta
import pytz

# ─── CONFIGURE ────────────────────────────────────────────────────────────────
PT = pytz.timezone("America/Los_Angeles")
# ────────────────────────────────────────────────────────────────────────────────

# IMPORTANT: This script is for backfilling the new table daily_leaderboard_stats. It does not add entries for days where there are no games which breaks some stuff
# This breaks rating/rank delta initially but this should be fixed by June 03?


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
        WITH base AS (
          SELECT
            player_name,
            game_mode,
            region,
            (date_trunc('day', snapshot_time AT TIME ZONE 'America/Los_Angeles'))::date AS day_start,
            rating,
            rank,
            lag(rating) OVER w AS prev_rating
          FROM leaderboard_snapshots
          WINDOW w AS (
            PARTITION BY player_name, game_mode, region
            ORDER BY snapshot_time
            ROWS BETWEEN UNBOUNDED PRECEDING AND CURRENT ROW
          )
        ),
        daily AS (
          SELECT
            player_name,
            game_mode,
            region,
            day_start,
            last_value(rating) OVER w1 AS rating,
            last_value(rank) OVER w1 AS rank,
            SUM(CASE WHEN prev_rating IS NOT NULL AND rating <> prev_rating THEN 1 ELSE 0 END)
              OVER w1 AS games_played,
            CASE
              WHEN day_start = date_trunc('week', day_start) THEN
                SUM(CASE WHEN prev_rating IS NOT NULL AND rating <> prev_rating THEN 1 ELSE 0 END)
                  OVER w1
              ELSE
                SUM(CASE WHEN prev_rating IS NOT NULL AND rating <> prev_rating THEN 1 ELSE 0 END)
                  OVER w2
            END AS weekly_games_played
          FROM base
          WINDOW
            w1 AS (
              PARTITION BY player_name, game_mode, region, day_start
              ORDER BY day_start
              ROWS BETWEEN UNBOUNDED PRECEDING AND UNBOUNDED FOLLOWING
            ),
            w2 AS (
              PARTITION BY player_name, game_mode, region,
                date_trunc('week', day_start)
              ORDER BY day_start
              ROWS BETWEEN UNBOUNDED PRECEDING AND CURRENT ROW
            )
        ),
        daily_uniq AS (
          SELECT DISTINCT ON (player_name, game_mode, region, day_start)
            player_name, game_mode, region, day_start, rating, rank,
            games_played, weekly_games_played
          FROM daily
        )
        INSERT INTO daily_leaderboard_stats
          (player_name, game_mode, region, day_start,
           rating, rank, games_played, weekly_games_played)
        SELECT player_name, game_mode, region, day_start,
               rating, rank, games_played, weekly_games_played
        FROM daily_uniq
        ON CONFLICT (player_name, game_mode, region, day_start) DO UPDATE
          SET rating = EXCLUDED.rating,
              rank = EXCLUDED.rank,
              games_played = EXCLUDED.games_played,
              weekly_games_played = EXCLUDED.weekly_games_played,
              updated_at = now();
        """
    )

    conn.commit()
    cur.close()
    conn.close()


if __name__ == "__main__":
    main()
