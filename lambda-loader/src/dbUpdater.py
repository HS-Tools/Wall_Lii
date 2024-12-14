import json
import os
from datetime import datetime, timezone
from decimal import Decimal

import boto3
from api import getLeaderboardSnapshot

from logger import setup_logger

logger = setup_logger("dbUpdater")


def check_milestones(player_name, rating, game_mode, server, table):
    """Check if player has reached a new milestone"""
    try:
        # Current season is 14
        season = "14"
        season_game_mode_server = f"{season}-{game_mode}-{server}"

        logger.info(
            f"Checking milestones for {player_name} ({rating}) in {season_game_mode_server}"
        )

        # Get milestone table name from environment
        milestone_table_name = os.environ.get(
            "MILESTONE_TABLE_NAME", "MilestoneTracking"
        )
        logger.info(f"Using milestone table: {milestone_table_name}")

        # Use same resource as main table but different table name
        milestone_table = boto3.resource("dynamodb").Table(milestone_table_name)

        # Get highest milestone achieved for this server/mode
        response = milestone_table.query(
            KeyConditionExpression="SeasonGameModeServer = :sgs",
            ExpressionAttributeValues={":sgs": season_game_mode_server},
        )

        # Find next milestone to check
        items = response.get("Items", [])
        current_milestones = [int(float(item["Milestone"])) for item in items]
        logger.info(f"Current milestones: {current_milestones}")

        # Get highest possible milestone for this rating
        max_possible = (rating // 1000) * 1000

        next_milestone = 8000  # Start at 8k
        if current_milestones:
            highest_milestone = max(current_milestones)
            next_milestone = (highest_milestone // 1000 + 1) * 1000

        logger.info(
            f"Next milestone to check: {next_milestone} (max possible: {max_possible})"
        )

        # Check if player has reached next milestone
        if rating >= next_milestone and next_milestone <= max_possible:
            milestone_table.put_item(
                Item={
                    "SeasonGameModeServer": season_game_mode_server,
                    "Milestone": next_milestone,
                    "PlayerName": player_name,
                    "Timestamp": int(datetime.now(timezone.utc).timestamp()),
                    "Rating": rating,
                }
            )
            logger.info(
                f"New milestone: {player_name} reached {next_milestone} in {server}"
            )
        else:
            logger.info(f"No new milestone: {rating} < {next_milestone}")

    except Exception as e:
        logger.error(f"Error checking milestones: {str(e)}")


def lambda_handler(event, context):
    """AWS Lambda handler to fetch and store leaderboard data"""
    try:
        logger.info("Starting leaderboard fetch")

        # Get max_pages from event or use default (40 pages = 1000 players)
        max_pages = event.get("max_pages", 40)

        # Get DynamoDB table
        table_name = os.environ["TABLE_NAME"]

        # Initialize DynamoDB client
        dynamodb = boto3.resource("dynamodb", region_name="us-east-1")
        table = dynamodb.Table(table_name)

        # Get leaderboard data for both game modes
        bg_data = getLeaderboardSnapshot(game_type="battlegrounds", max_pages=max_pages)
        duo_data = getLeaderboardSnapshot(
            game_type="battlegroundsduo", max_pages=max_pages
        )

        def update_player_data(player_name, rank, rating, game_mode, server, table):
            """Update a player's data in DynamoDB"""
            try:
                # Normalize server name
                server_mapping = {"US": "NA", "EU": "EU", "AP": "AP"}
                server = server_mapping.get(server, server)

                # Create composite keys
                game_mode_server_player = f"{game_mode}#{server}#{player_name.lower()}"
                game_mode_server = f"{game_mode}#{server}"

                # Step 1: Fetch only CurrentRank and LatestRating
                response = table.query(
                    KeyConditionExpression="GameModeServerPlayer = :gmsp",
                    ExpressionAttributeValues={":gmsp": game_mode_server_player},
                    ProjectionExpression="CurrentRank, LatestRating"
                )

                # Extract current values
                if response.get("Items"):
                    item = response["Items"][0]
                    current_rating = item.get("LatestRating")
                    current_rank = item.get("CurrentRank")
                else:
                    current_rating = None
                    current_rank = None

                # Step 2: Determine if an update is needed
                current_time = int(datetime.now(timezone.utc).timestamp())
                rating_decimal = Decimal(str(rating))
                rank_decimal = Decimal(str(rank))

                should_update = (
                    not current_rating or
                    current_rating != rating_decimal or
                    current_rank != rank_decimal
                )

                # Step 3: Perform conditional update with update_item
                if should_update:
                    # Incrementally update attributes
                    update_expression = "SET CurrentRank = :new_rank, LatestRating = :new_rating"
                    expression_attribute_values = {
                        ":new_rank": rank_decimal,
                        ":new_rating": rating_decimal,
                    }

                    # Append to RatingHistory if necessary
                    if current_rating != rating_decimal:
                        update_expression += ", RatingHistory = list_append(if_not_exists(RatingHistory, :empty_list), :new_history)"
                        expression_attribute_values.update({
                            ":empty_list": [],
                            ":new_history": [[rating_decimal, current_time]],
                        })

                    table.update_item(
                        Key={"GameModeServerPlayer": game_mode_server_player},
                        UpdateExpression=update_expression,
                        ExpressionAttributeValues=expression_attribute_values,
                    )

                    # Log significant rating changes (>301 MMR)
                    if current_rating:
                        change = rating - float(current_rating)
                        if abs(change) > 301:
                            logger.info(
                                f"Significant rating change for {player_name}: {current_rating} → {rating} "
                                f"({'+' if change > 0 else ''}{change}) in {server}"
                            )

                # Check milestones for rank 1 player regardless of update
                if rank == 1:
                    logger.info(
                        f"Found rank 1 player: {player_name} ({rating}) in {server}"
                    )
                    check_milestones(player_name, rating, game_mode, server, table)

                return should_update

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
