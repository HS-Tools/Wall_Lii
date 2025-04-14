import os
import json
from logger import setup_logger
from db_utils import get_db_connection

# Set up logger
logger = setup_logger("prune_supabase")

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
