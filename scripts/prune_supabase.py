import os
import psycopg2
from dotenv import load_dotenv

load_dotenv()

DB_HOST = os.getenv("DB_HOST")
DB_PORT = os.getenv("DB_PORT", "5432")
DB_NAME = os.getenv("DB_NAME")
DB_USER = os.getenv("DB_USER")
DB_PASSWORD = os.getenv("DB_PASSWORD")

PRUNE_QUERY = """
WITH recent_rows AS (
  SELECT *
  FROM leaderboard_snapshots
  WHERE snapshot_time > NOW() - interval '24 hours'
),

ranked AS (
  SELECT *,
         ROW_NUMBER() OVER (
           PARTITION BY player_name, game_mode, region, rating
           ORDER BY snapshot_time ASC
         ) AS row_asc,
         ROW_NUMBER() OVER (
           PARTITION BY player_name, game_mode, region, rating
           ORDER BY snapshot_time DESC
         ) AS row_desc,
         RANK() OVER (
           PARTITION BY player_name, game_mode, region
           ORDER BY snapshot_time DESC
         ) AS rating_rank
  FROM recent_rows
),

to_delete AS (
  SELECT *
  FROM ranked
  WHERE
    -- Not the oldest row for this rating
    row_asc > 1
    -- AND not the most recent version of the most recent rating
    AND NOT (rating_rank = 1 AND row_desc = 1)
)

DELETE FROM leaderboard_snapshots
USING to_delete
WHERE leaderboard_snapshots.player_name = to_delete.player_name
  AND leaderboard_snapshots.game_mode = to_delete.game_mode
  AND leaderboard_snapshots.region = to_delete.region
  AND leaderboard_snapshots.snapshot_time = to_delete.snapshot_time;
"""

def main():
    print("Pruning redundant snapshots from the last 24 hours...")

    conn = psycopg2.connect(
        host=DB_HOST,
        port=DB_PORT,
        dbname=DB_NAME,
        user=DB_USER,
        password=DB_PASSWORD,
        sslmode="require"
    )
    try:
        with conn:
            with conn.cursor() as cur:
                cur.execute(PRUNE_QUERY)
                print("Pruning completed successfully.")
    except Exception as e:
        print("Error during pruning:", str(e))
    finally:
        conn.close()

if __name__ == "__main__":
    main()