import os
import json
from logger import setup_logger
from db_utils import get_db_connection

# Set up logger
logger = setup_logger("prune_supabase")

# Table names
LEADERBOARD_SNAPSHOTS = "leaderboard_snapshots"

PRUNE_QUERY = f"""
WITH recent_rows AS (
  SELECT *
  FROM {LEADERBOARD_SNAPSHOTS}
  WHERE snapshot_time > NOW() - interval '30 days'
),

with_lag AS (
  SELECT *,
         LAG(rating) OVER (
           PARTITION BY player_name, game_mode, region
           ORDER BY snapshot_time
         ) AS previous_rating
  FROM recent_rows
),

with_blocks AS (
  SELECT *,
         SUM(CASE WHEN rating != previous_rating OR previous_rating IS NULL THEN 1 ELSE 0 END)
           OVER (PARTITION BY player_name, game_mode, region ORDER BY snapshot_time)
         AS rating_block
  FROM with_lag
),

ranked AS (
  SELECT *,
         ROW_NUMBER() OVER (
           PARTITION BY player_name, game_mode, region, rating_block
           ORDER BY snapshot_time
         ) AS row_in_block,
         COUNT(*) OVER (
           PARTITION BY player_name, game_mode, region, rating_block
         ) AS block_size
  FROM with_blocks
),

to_delete AS (
  SELECT *
  FROM ranked
  WHERE block_size > 2 AND row_in_block NOT IN (1, block_size)
)

DELETE FROM {LEADERBOARD_SNAPSHOTS}
USING to_delete
WHERE {LEADERBOARD_SNAPSHOTS}.player_name = to_delete.player_name
  AND {LEADERBOARD_SNAPSHOTS}.game_mode = to_delete.game_mode
  AND {LEADERBOARD_SNAPSHOTS}.region = to_delete.region
  AND {LEADERBOARD_SNAPSHOTS}.snapshot_time = to_delete.snapshot_time;
"""


def prune_database():
    """
    Prune redundant snapshots from the database
    """
    logger.info("Pruning redundant snapshots from the last 24 hours...")
    conn = None
    try:
        conn = get_db_connection()
        with conn:
            with conn.cursor() as cur:
                cur.execute(PRUNE_QUERY)
                rows_affected = cur.rowcount
                logger.info(
                    f"Pruning completed successfully. Removed {rows_affected} rows."
                )
                return rows_affected
    except Exception as e:
        logger.error(f"Error during pruning: {str(e)}")
        raise
    finally:
        if conn:
            conn.close()


def lambda_handler(event, context):
    """
    AWS Lambda entry point
    """
    try:
        rows_affected = prune_database()
        return {
            "statusCode": 200,
            "body": json.dumps(
                {
                    "message": "Pruning completed successfully",
                    "rows_affected": rows_affected,
                }
            ),
        }
    except Exception as e:
        logger.error(f"Lambda execution failed: {str(e)}")
        return {
            "statusCode": 500,
            "body": json.dumps({"message": f"Error during execution: {str(e)}"}),
        }


# For local testing
if __name__ == "__main__":
    print(lambda_handler({}, None))
