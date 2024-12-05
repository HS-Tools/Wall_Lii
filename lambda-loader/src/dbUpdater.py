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

        # Get max_pages from event or use default (4 pages = 100 players)
        max_pages = event.get("max_pages", 4)

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

                # Get existing item
                response = table.query(
                    KeyConditionExpression="GameModeServerPlayer = :gmsp",
                    ExpressionAttributeValues={":gmsp": game_mode_server_player},
                )

                # Get existing history or start new
                if response.get("Items"):
                    item = response["Items"][0]
                    rating_history = item.get("RatingHistory", [])
                    current_rating = rating_history[-1][0] if rating_history else None
                    current_rank = item.get("CurrentRank")
                else:
                    rating_history = []
                    current_rating = None
                    current_rank = None

                # Add new rating if changed
                current_time = int(datetime.now(timezone.utc).timestamp())
                rating_decimal = Decimal(str(rating))
                rank_decimal = Decimal(str(rank))

                # Determine if an update is needed
                should_update = (
                    not rating_history or
                    (current_rating != rating_decimal and not any(h[0] == rating_decimal for h in rating_history[-3:]) and
                     (not rating_history or current_time - rating_history[-1][1] >= 60)) or
                    (current_rank != rank_decimal)
                )

                if should_update:
                    if current_rating != rating_decimal:
                        rating_history.append([rating_decimal, current_time])

                    item = {
                        "GameModeServerPlayer": game_mode_server_player,
                        "GameModeServer": game_mode_server,
                        "PlayerName": player_name.lower(),
                        "GameMode": game_mode,
                        "Server": server,
                        "CurrentRank": rank_decimal,
                        "LatestRating": rating_decimal,
                        "RatingHistory": rating_history,
                    }

                    table.put_item(Item=item)

                    # Log significant rating changes (>301 MMR)
                    old_rating = rating_history[-2][0] if len(rating_history) > 1 else None
                    if old_rating:
                        change = rating - old_rating
                        if abs(change) > 301:
                            logger.info(
                                f"Significant rating change for {player_name}: {old_rating} → {rating} ({'+' if change > 0 else ''}{change}) in {server}"
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
