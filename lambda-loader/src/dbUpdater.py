import json
import os
from datetime import datetime

import boto3

from api import getLeaderboardSnapshot


def handler(event, context):
    """
    AWS Lambda handler to fetch and store leaderboard data
    """
    try:
        # Get leaderboard data for both game modes
        bg_data = getLeaderboardSnapshot(game_type="battlegrounds")
        duo_data = getLeaderboardSnapshot(game_type="battlegroundsduo")

        # Initialize DynamoDB client
        dynamodb = boto3.resource("dynamodb")
        table = dynamodb.Table(os.environ["TABLE_NAME"])

        timestamp = datetime.now().strftime("%Y-%m-%dT%H:%M:%S.%f")

        def store_player_data(data, game_type):
            for region, region_data in data.items():
                for mode, players in region_data.items():
                    for player_name, stats in players.items():
                        player_key = f"{player_name}#{region}#{game_type}"

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
                                int(last_entry["MMR"]["N"]) == stats["rating"]
                                and int(last_entry["rank"]["N"]) == stats["rank"]
                            ):
                                should_store = False

                        if should_store:
                            table.put_item(
                                Item={
                                    "player_key": player_key,
                                    "timestamp": timestamp,
                                    "player_name": player_name,
                                    "region": region,
                                    "region_key": f"{region}#{game_type}",
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
        print(f"Error: {str(e)}")
        return {
            "statusCode": 500,
            "body": json.dumps(f"Error updating leaderboard data: {str(e)}"),
        }
