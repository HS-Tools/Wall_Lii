import json
import os
from datetime import datetime, timezone
from decimal import Decimal

import boto3
import random
import time
from botocore.exceptions import ClientError

from api import getLeaderboardSnapshot

from logger import setup_logger

logger = setup_logger("dbUpdater")

def exponential_backoff(attempt, base_delay=0.1, max_delay=5.0):
    """Calculate delay with exponential backoff and jitter"""
    delay = min(base_delay * (2 ** attempt), max_delay)
    jitter = random.uniform(0, 0.1 * delay)  # Add up to 10% jitter
    return delay + jitter

def handle_dynamodb_error(e: Exception, operation: str, retry: int, max_retries: int):
    """Handle DynamoDB errors with appropriate logging and retry logic"""
    if isinstance(e, ClientError):
        error_code = e.response['Error']['Code']
        if error_code == 'ProvisionedThroughputExceededException':
            if retry < max_retries - 1:
                delay = exponential_backoff(retry)
                logger.warning(f"{operation} - Throughput exceeded, retry {retry + 1}/{max_retries} after {delay:.2f}s")
                time.sleep(delay)
                return True
            else:
                logger.error(f"{operation} - Max retries ({max_retries}) reached for throughput exceeded")
        else:
            logger.error(f"{operation} - DynamoDB error: {error_code}")
    return False

def get_dynamodb_resource():
    """Get DynamoDB resource based on environment"""
    if os.environ.get("AWS_LAMBDA_FUNCTION_NAME"):
        return boto3.resource("dynamodb", region_name="us-east-1")
    else:
        return boto3.resource(
            "dynamodb",
            endpoint_url="http://localhost:8000",
            region_name="us-west-2",
            aws_access_key_id="dummy",
            aws_secret_access_key="dummy"
        )

def get_table_name():
    """Get the DynamoDB table name based on environment"""
    if os.environ.get('AWS_SAM_LOCAL') == 'true':
        return "lambda-test-table"
    elif os.environ.get('AWS_LAMBDA_FUNCTION_NAME'):
        return "HearthstoneLeaderboardV2"
    else:
        return "lambda-test-table"

def is_local_dynamodb():
    """Check if we're using local DynamoDB"""
    if os.environ.get('AWS_SAM_LOCAL') == 'true':
        return True
    if os.environ.get('AWS_LAMBDA_FUNCTION_NAME'):
        return False
    # If neither environment variable is set, assume local
    return True

def batch_get_with_retry(table, keys, projection_expression, max_retries=5):
    """Batch get items with improved retry logic"""
    if not keys:
        return []
        
    # Split into chunks of 100 (DynamoDB limit)
    all_items = []
    for i in range(0, len(keys), 100):
        chunk = keys[i:i + 100]
        
        for retry in range(max_retries):
            try:
                kwargs = {
                    'RequestItems': {
                        table.name: {
                            'Keys': chunk,
                            'ProjectionExpression': projection_expression
                        }
                    }
                }
                if not is_local_dynamodb():
                    kwargs['ReturnConsumedCapacity'] = 'TOTAL'
                
                response = table.meta.client.batch_get_item(**kwargs)
                items = response['Responses'][table.name]
                all_items.extend(items)
                
                # Handle unprocessed keys if any
                unprocessed = response.get('UnprocessedKeys', {}).get(table.name, {}).get('Keys', [])
                if unprocessed:
                    delay = exponential_backoff(retry)
                    logger.warning(f"Retrying {len(unprocessed)} unprocessed keys after {delay:.2f}s")
                    time.sleep(delay)
                    chunk = unprocessed
                    continue
                    
                break
                
            except Exception as e:
                should_retry = handle_dynamodb_error(e, "BatchGet", retry, max_retries)
                if not should_retry:
                    raise
                
    return all_items

def batch_write_with_retry(table, items, max_retries=5):
    """Batch write items with improved retry logic"""
    if not items:
        return
        
    # Split into chunks of 25 (DynamoDB limit)
    for i in range(0, len(items), 25):
        chunk = items[i:i + 25]
        unprocessed = chunk
        
        for retry in range(max_retries):
            try:
                if not unprocessed:
                    break
                    
                kwargs = {
                    'RequestItems': {
                        table.name: [{'PutRequest': {'Item': item}} for item in unprocessed]
                    }
                }
                if not is_local_dynamodb():
                    kwargs['ReturnConsumedCapacity'] = 'TOTAL'
                
                response = table.meta.client.batch_write_item(**kwargs)
                
                # Handle unprocessed items
                unprocessed = []
                for item in response.get('UnprocessedItems', {}).get(table.name, []):
                    if 'PutRequest' in item:
                        unprocessed.append(item['PutRequest']['Item'])
                
                if unprocessed:
                    delay = exponential_backoff(retry)
                    logger.warning(f"Retrying {len(unprocessed)} unprocessed items after {delay:.2f}s")
                    time.sleep(delay)
                    continue
                    
                break
                
            except Exception as e:
                should_retry = handle_dynamodb_error(e, "BatchWrite", retry, max_retries)
                if not should_retry:
                    raise

def update_rating_histories(table, items_to_update, current_time):
    """Update rating histories for multiple items in batch"""
    if not items_to_update:
        return
        
    # Get all histories in one batch
    keys = [{
        'GameModeServerPlayer': item['GameModeServerPlayer'],
        'GameModeServer': item['GameModeServer']
    } for item in items_to_update]
    
    histories = batch_get_with_retry(table, keys, 'GameModeServerPlayer, RatingHistory')
    
    # Create a map for quick lookup
    history_map = {item['GameModeServerPlayer']: item.get('RatingHistory', []) for item in histories}
    
    # Prepare all updates
    updates = []
    for item in items_to_update:
        gms_player = item['GameModeServerPlayer']
        current_history = history_map.get(gms_player, [])
        
        # Add new rating to history
        new_history = current_history[-99:] if current_history else []  # Keep last 99 entries
        new_history.append({
            'Rating': item['LatestRating'],
            'Timestamp': current_time
        })
        
        # Create update item
        update_item = {
            'GameModeServerPlayer': gms_player,
            'GameModeServer': item['GameModeServer'],
            'PlayerName': item['PlayerName'],
            'GameMode': item['GameMode'],
            'Server': item['Server'],
            'CurrentRank': item['CurrentRank'],
            'LatestRating': item['LatestRating'],
            'RatingHistory': new_history
        }
        updates.append(update_item)
    
    # Write all updates in one batch
    batch_write_with_retry(table, updates)

def process_player_batch(table, players, game_mode, server, current_time):
    """Process a batch of players"""
    # Get current data for all players in one batch
    keys = [{
        'GameModeServerPlayer': f"{game_mode}#{server}#{p['PlayerName'].lower()}",
        'GameModeServer': f"{game_mode}#{server}"
    } for p in players]
    
    current_items = batch_get_with_retry(
        table, 
        keys,
        'GameModeServerPlayer, CurrentRank, LatestRating'
    )
    
    # Create a map for quick lookup
    current_map = {item['GameModeServerPlayer']: item for item in current_items}
    
    # Prepare updates
    updates_needed = []
    rating_history_needed = []
    num_updates = 0
    
    for player in players:
        gms_player = f"{game_mode}#{server}#{player['PlayerName'].lower()}"  # Use # as separator and lowercase player name
        gms = f"{game_mode}#{server}"
        current_item = current_map.get(gms_player)
        
        # Check if update needed
        if not current_item or (
            current_item.get('CurrentRank') != player['Rank'] or 
            current_item.get('LatestRating') != player['Rating']
        ):
            update_item = {
                'GameModeServerPlayer': gms_player,
                'GameModeServer': gms,
                'PlayerName': player['PlayerName'].lower(),  # Store player name in lowercase
                'GameMode': game_mode,
                'Server': server,
                'CurrentRank': player['Rank'],
                'LatestRating': player['Rating']
            }
            updates_needed.append(update_item)
            rating_history_needed.append(update_item)
            num_updates += 1
    
    # Batch write updates
    if updates_needed:
        batch_write_with_retry(table, updates_needed)
    
    # Update rating histories in batch
    if rating_history_needed:
        update_rating_histories(table, rating_history_needed, current_time)
    
    return num_updates

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
                response = table.get_item(
                    Key={
                        "GameModeServerPlayer": game_mode_server_player,
                        "GameModeServer": game_mode_server,
                    },
                    ProjectionExpression="CurrentRank, LatestRating"
                )

                # Extract current values or create new entry
                item = response.get("Item", None)
                current_rating = item.get("LatestRating") if item else None
                current_rank = item.get("CurrentRank") if item else None

                # Step 2: Determine if an update is needed
                current_time = int(datetime.now(timezone.utc).timestamp())
                rating_decimal = Decimal(str(rating))
                rank_decimal = Decimal(str(rank))

                should_update = (
                    not current_rating or
                    current_rating != rating_decimal or
                    current_rank != rank_decimal
                )

                if not item:
                    # Create new player entry
                    new_item = {
                        "GameModeServerPlayer": game_mode_server_player,
                        "GameModeServer": game_mode_server,
                        "PlayerName": player_name.lower(),
                        "GameMode": game_mode,
                        "Server": server,
                        "CurrentRank": rank_decimal,
                        "LatestRating": rating_decimal,
                        "RatingHistory": [[rating_decimal, current_time]],
                    }
                    table.put_item(Item=new_item)
                    logger.info(f"New player added: {player_name} with rating {rating} and rank {rank}")
                elif should_update:
                    # Update existing player entry
                    update_expression = "SET CurrentRank = :new_rank, LatestRating = :new_rating"
                    expression_attribute_values = {
                        ":new_rank": rank_decimal,
                        ":new_rating": rating_decimal,
                    }

                    if current_rating != rating_decimal:
                        update_expression += ", RatingHistory = list_append(if_not_exists(RatingHistory, :empty_list), :new_history)"
                        expression_attribute_values.update({
                            ":empty_list": [],
                            ":new_history": [[rating_decimal, current_time]],
                        })

                    table.update_item(
                        Key={
                            "GameModeServerPlayer": game_mode_server_player,
                            "GameModeServer": game_mode_server,
                        },
                        UpdateExpression=update_expression,
                        ExpressionAttributeValues=expression_attribute_values,
                    )
                    logger.info(f"Updated player {player_name}: {rating} (rank {rank})")

                # Check milestones for rank 1 player regardless of update
                if rank == 1:
                    logger.info(
                        f"Found rank 1 player: {player_name} ({rating}) in {server}"
                    )
                    check_milestones(player_name, rating, game_mode, server, table)

                return should_update or not item

            except Exception as e:
                logger.error(f"Error updating player {player_name}: {e}")
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
