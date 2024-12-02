import json
import os
from datetime import datetime
from decimal import Decimal

import boto3
from api import getLeaderboardSnapshot
from boto3.session import Config

from logger import setup_logger

logger = setup_logger("dbUpdater")


def decimal_default(obj):
    if isinstance(obj, Decimal):
        return int(obj)
    raise TypeError


def handler(event, context):
    """
    AWS Lambda handler to fetch and store leaderboard data
    """
    try:
        logger.info("Starting leaderboard fetch")

        # Configure boto3 with specific settings
        config = Config(
            region_name="us-east-1",
            retries={"max_attempts": 2, "mode": "standard"},
            connect_timeout=10,  # Increased timeout for Lambda
            read_timeout=10,
        )

        # Initialize DynamoDB client with better configuration
        dynamodb = boto3.resource("dynamodb", config=config, region_name="us-east-1")
        table = dynamodb.Table(os.environ["TABLE_NAME"])

        # Debug check - get beterbabbit's latest entry before update
        beter_key = "beterbabbit#US#battlegrounds"
        beter_response = table.query(
            KeyConditionExpression="player_key = :pk",
            ExpressionAttributeValues={":pk": beter_key},
            ScanIndexForward=False,
            Limit=1,
        )
        if beter_response["Items"]:
            last_beter = beter_response["Items"][0]
            logger.info(
                f"beterbabbit's last entry: MMR={last_beter['MMR']}, Rank={last_beter['rank']}, Time={last_beter['timestamp']}"
            )
        else:
            logger.info("No previous entries found for beterbabbit")

        # Get leaderboard data for both game modes
        bg_data = getLeaderboardSnapshot(game_type="battlegrounds")
        duo_data = getLeaderboardSnapshot(game_type="battlegroundsduo")

        # Debug check - print beterbabbit's new data if present
        if "US" in bg_data and "battlegrounds" in bg_data["US"]:
            if "beterbabbit" in bg_data["US"]["battlegrounds"]:
                new_beter = bg_data["US"]["battlegrounds"]["beterbabbit"]
                logger.info(
                    f"beterbabbit's new data: MMR={new_beter['rating']}, Rank={new_beter['rank']}"
                )
            else:
                logger.warning("beterbabbit not found in new leaderboard data")

        timestamp = datetime.now().strftime("%Y-%m-%dT%H:%M:%S.%f")
        current_time = datetime.strptime(timestamp, "%Y-%m-%dT%H:%M:%S.%f")

        def store_player_data(data, game_type):
            updates = 0
            skips = 0
            for server, server_data in data.items():
                for mode, players in server_data.items():
                    for player_name, stats in players.items():
                        player_key = f"{player_name}#{server}#{game_type}"

                        # Check last entry for this player
                        response = table.query(
                            KeyConditionExpression="player_key = :pk",
                            ScanIndexForward=False,
                            Limit=1,
                            ExpressionAttributeValues={":pk": player_key},
                        )

                        # Special logging for lii
                        if player_name == "lii":
                            if response["Items"]:
                                last_entry = response["Items"][0]
                                logger.info(
                                    f"lii comparison - API: MMR={stats['rating']}, Rank={stats['rank']} | "
                                    f"DB: MMR={last_entry['MMR']}, Rank={last_entry['rank']}, Time={last_entry['timestamp']}"
                                )
                            else:
                                logger.info(f"No previous entries for lii, new data: MMR={stats['rating']}, Rank={stats['rank']}")

                        should_store = True
                        if response["Items"]:
                            last_entry = response["Items"][0]
                            # Only store if MMR or rank changed
                            if (
                                int(last_entry["MMR"]) == stats["rating"]
                                and int(last_entry["rank"]) == stats["rank"]
                            ):
                                should_store = False
                                skips += 1
                            else:
                                logger.info(
                                    f"Updating {player_name} due to: MMR change: {last_entry['MMR']} != {stats['rating']}, "
                                    f"Rank change: {last_entry['rank']} != {stats['rank']}"
                                )

                        if should_store:
                            updates += 1
                            table.put_item(
                                Item={
                                    "player_key": player_key,
                                    "timestamp": timestamp,
                                    "player_name": player_name,
                                    "server": server,
                                    "server_key": f"{server}#{game_type}",
                                    "rank": stats["rank"],
                                    "MMR": stats["rating"],
                                }
                            )

            logger.info(
                f"Game type {game_type}: Updated {updates} players, skipped {skips} unchanged entries"
            )
            return updates, skips

        # Store data for both game modes
        bg_updates, bg_skips = store_player_data(bg_data, "battlegrounds")
        duo_updates, duo_skips = store_player_data(duo_data, "battlegroundsduo")

        return {
            "statusCode": 200,
            "body": json.dumps(
                {
                    "message": "Successfully updated leaderboard data",
                    "updates": {
                        "battlegrounds": {"updated": bg_updates, "skipped": bg_skips},
                        "battlegroundsduo": {
                            "updated": duo_updates,
                            "skipped": duo_skips,
                        },
                    },
                }
            ),
        }

    except Exception as e:
        logger.error(f"Error: {str(e)}")
        return {
            "statusCode": 500,
            "body": json.dumps(f"Error updating leaderboard data: {str(e)}"),
        }

def get_player_mmr_changes(player_name, server=None, game_type="battlegrounds"):
    # Get current time in UTC
    now = datetime.now()
    today_start = now.replace(hour=0, minute=0, second=0, microsecond=0)
    
    # Format for DynamoDB comparison
    today_start_str = today_start.strftime("%Y-%m-%dT%H:%M:%S.%f")

    # Calculate MMR changes between consecutive entries
    mmr_changes = []
    for i in range(1, len(items)):
        prev_mmr = int(items[i-1]["MMR"])
        curr_mmr = int(items[i]["MMR"])
        mmr_changes.append(curr_mmr - prev_mmr)
