import json
import os
from datetime import datetime
from decimal import Decimal

import boto3

from api import getLeaderboardSnapshot
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
        # Get leaderboard data for both game modes
        bg_data = getLeaderboardSnapshot(game_type="battlegrounds")
        duo_data = getLeaderboardSnapshot(game_type="battlegroundsduo")
        logger.debug("BG Data: %s", bg_data)

        # Look specifically for shadybunny
        eu_players = bg_data.get("EU", {}).get("battlegrounds", {})
        if "shadybunny" in eu_players:
            logger.info("Debug - Shadybunny data: %s", eu_players["shadybunny"])

        # Initialize DynamoDB client
        dynamodb = boto3.resource("dynamodb")
        table = dynamodb.Table(os.environ["TABLE_NAME"])

        timestamp = datetime.now().strftime("%Y-%m-%dT%H:%M:%S.%f")

        def store_player_data(data, game_type):
            for server, server_data in data.items():
                for mode, players in server_data.items():
                    for player_name, stats in players.items():
                        if player_name == "shadybunny":  # Debug for shadybunny
                            player_key = f"{player_name}#{server}#{game_type}"
                            logger.info(
                                f"Debug - Checking shadybunny with key: {player_key}"
                            )

                            response = table.query(
                                KeyConditionExpression="player_key = :pk",
                                ScanIndexForward=False,
                                Limit=1,
                                ExpressionAttributeValues={":pk": player_key},
                            )
                            logger.info(
                                "Debug - Last entry: %s",
                                json.dumps(
                                    response.get("Items", []),
                                    default=decimal_default,
                                    indent=2,
                                ),
                            )

                            should_store = True
                            if response["Items"]:
                                last_entry = response["Items"][0]
                                logger.info(
                                    f"Debug - Comparing MMR: {last_entry['MMR']} vs {stats['rating']}"
                                )
                                logger.info(
                                    f"Debug - Comparing rank: {last_entry['rank']} vs {stats['rank']}"
                                )
                                if (
                                    int(last_entry["MMR"]) == stats["rating"]
                                    and int(last_entry["rank"]) == stats["rank"]
                                ):
                                    should_store = False

                            logger.info(f"Debug - Should store: {should_store}")

                        player_key = f"{player_name}#{server}#{game_type}"

                        # Check last entry for this player
                        response = table.query(
                            KeyConditionExpression="player_key = :pk",
                            ScanIndexForward=False,  # Get most recent first
                            Limit=1,
                            ExpressionAttributeValues={":pk": player_key},
                        )

                        # Only store if this is first entry or data changed
                        should_store = True
                        if response["Items"]:
                            last_entry = response["Items"][0]
                            if (
                                int(last_entry["MMR"]) == stats["rating"]
                                and int(last_entry["rank"]) == stats["rank"]
                            ):
                                should_store = False

                        if should_store:
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

        # Store data for both game modes
        store_player_data(bg_data, "battlegrounds")
        store_player_data(duo_data, "battlegroundsduo")

        return {
            "statusCode": 200,
            "body": json.dumps("Successfully updated leaderboard data"),
        }

    except Exception as e:
        logger.error(f"Error: {str(e)}")
        return {
            "statusCode": 500,
            "body": json.dumps(f"Error updating leaderboard data: {str(e)}"),
        }
