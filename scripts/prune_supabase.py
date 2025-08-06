import os
import psycopg2
from dotenv import load_dotenv
from datetime import datetime, timedelta

load_dotenv()

DB_HOST = os.getenv("DB_HOST")
DB_PORT = os.getenv("DB_PORT", "5432")
DB_NAME = os.getenv("DB_NAME")
DB_USER = os.getenv("DB_USER")
DB_PASSWORD = os.getenv("DB_PASSWORD")

PRUNE_QUERY_TEMPLATE = """
WITH recent_rows AS (
  SELECT *
  FROM leaderboard_snapshots
  WHERE snapshot_time > '{start_time}' AND snapshot_time <= '{end_time}'
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
    row_asc > 1
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
    print("Pruning redundant snapshots from the last 10 days...")

    conn = psycopg2.connect(
        host=DB_HOST,
        port=DB_PORT,
        dbname=DB_NAME,
        user=DB_USER,
        password=DB_PASSWORD,
        sslmode="require",
    )
    now = datetime.utcnow()

    for i in range(20, 30):
        end_time = now - timedelta(days=i)
        start_time = end_time - timedelta(days=1)

        query = PRUNE_QUERY_TEMPLATE.format(
            start_time=start_time.isoformat(), end_time=end_time.isoformat()
        )

        print(f"Pruning snapshots from {start_time} to {end_time}...")

        try:
            with conn:
                with conn.cursor() as cur:
                    cur.execute(query)
                    print(f"Pruning for {start_time.date()} completed.")
        except Exception as e:
            print(f"Error during pruning for {start_time.date()}: {str(e)}")

    conn.close()


if __name__ == "__main__":
    main()
