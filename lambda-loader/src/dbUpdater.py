import json
import os
from datetime import datetime, timezone
from decimal import Decimal

import boto3
from api import getLeaderboardSnapshot

from logger import setup_logger

logger = setup_logger("dbUpdater")


def lambda_handler(event, context):
    """AWS Lambda handler to fetch and store leaderboard data"""
    try:
        logger.info("Starting leaderboard fetch")

        # Get max_pages from event or use default (4 pages = 100 players)
        max_pages = event.get("max_pages", 4)

        # Get DynamoDB table - handle local testing
        table_name = os.environ["TABLE_NAME"]
        endpoint_url = os.environ.get("DYNAMODB_ENDPOINT_URL")  # None in production

        # Initialize DynamoDB client
        dynamodb_kwargs = {"region_name": "us-east-1"}
        if endpoint_url:
            dynamodb_kwargs["endpoint_url"] = endpoint_url

        dynamodb = boto3.resource("dynamodb", **dynamodb_kwargs)
        table = dynamodb.Table(table_name)

        # Get leaderboard data for both game modes
        bg_data = getLeaderboardSnapshot(game_type="battlegrounds", max_pages=max_pages)
        duo_data = getLeaderboardSnapshot(
            game_type="battlegroundsduo", max_pages=max_pages
        )

        def update_player_data(player_name, rank, rating, game_mode, server, table):
            """Update a player's data in DynamoDB"""
            # Normalize server name
            server_mapping = {"US": "NA", "EU": "EU", "AP": "AP"}
            server = server_mapping.get(server, server)

            # Create composite keys
            game_mode_server_player = f"{game_mode}#{server}#{player_name.lower()}"
            game_mode_server = f"{game_mode}#{server}"

            try:
                # Get existing item
                response = table.query(
                    KeyConditionExpression="GameModeServerPlayer = :gmsp",
                    ExpressionAttributeValues={":gmsp": game_mode_server_player},
                )

                # Get existing history or start new
                if response.get("Items"):
                    rating_history = response["Items"][0].get("RatingHistory", [])
                    current_rating = rating_history[-1][0] if rating_history else None
                else:
                    rating_history = []
                    current_rating = None

                # Add new rating if changed
                current_time = int(datetime.now(timezone.utc).timestamp())
                rating_decimal = Decimal(str(rating))

                # Only update if rating changed and enough time passed
                should_update = not rating_history or (
                    current_rating != rating_decimal
                    and not any(h[0] == rating_decimal for h in rating_history[-3:])
                    and (
                        not rating_history or current_time - rating_history[-1][1] >= 60
                    )
                )

                if should_update:
                    rating_history.append([rating_decimal, current_time])

                    item = {
                        "GameModeServerPlayer": game_mode_server_player,
                        "GameModeServer": game_mode_server,
                        "PlayerName": player_name.lower(),
                        "GameMode": game_mode,
                        "Server": server,
                        "CurrentRank": Decimal(str(rank)),
                        "LatestRating": rating_decimal,
                        "RatingHistory": rating_history,
                    }

                    table.put_item(Item=item)

                    # Only log significant rating changes (e.g., >301)
                    old_rating = (
                        rating_history[-2][0] if len(rating_history) > 1 else None
                    )
                    if old_rating:
                        change = rating - old_rating
                        if abs(change) > 301:
                            logger.info(
                                f"Significant rating change for {player_name}: {old_rating} → {rating} ({'+' if change > 0 else ''}{change}) in {server}"
                            )

                    return True

                return False

            except Exception as e:
                logger.error(f"Error updating {player_name}: {str(e)}")
                return False

        # Process updates for each game mode
        updates = {"battlegrounds": 0, "battlegroundsduo": 0}

        for game_type, data in [
            ("battlegrounds", bg_data),
            ("battlegroundsduo", duo_data),
        ]:
            mode_num = "0" if game_type == "battlegrounds" else "1"
            for server, server_data in data.items():
                for mode, players in server_data.items():
                    for player_name, stats in players.items():
                        if update_player_data(
                            player_name=player_name,
                            rank=stats["rank"],
                            rating=stats["rating"],
                            game_mode=mode_num,
                            server=server,
                            table=table,
                        ):
                            updates[game_type] += 1

        return {
            "statusCode": 200,
            "body": json.dumps(
                {
                    "message": "Successfully updated leaderboard data",
                    "updates": updates,
                }
            ),
        }

    except Exception as e:
        logger.error(f"Error: {str(e)}")
        return {
            "statusCode": 500,
            "body": json.dumps({"error": f"Error updating leaderboard data: {str(e)}"}),
        }
