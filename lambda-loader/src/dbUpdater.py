import json
import os
from datetime import datetime, timezone
from decimal import Decimal
from typing import Dict, List
import logging
import boto3

from api import getLeaderboardSnapshot
from logger import setup_logger

logger = setup_logger("dbUpdater")

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

def batch_get_with_retry(table, keys, projection_expression, max_retries=3):
    """Batch get items with retry logic"""
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
                
                logger.info(f"Batch get request: {kwargs}")
                response = table.meta.client.batch_get_item(**kwargs)
                logger.info(f"Batch get response: {response}")
                
                items = response['Responses'][table.name]
                all_items.extend(items)
                
                # Track capacity
                if is_local_dynamodb():
                    pass
                else:
                    for cc in response.get('ConsumedCapacity', []):
                        pass
                    
                break
            except Exception as e:
                logger.error(f"Error in batch get: {e}")
                if retry == max_retries - 1:
                    raise
                logger.info(f"Retry {retry + 1} for batch get")
                # Exponential backoff
    
    logger.info(f"Total items retrieved: {len(all_items)}")
    if all_items:
        logger.info(f"Sample item: {all_items[0]}")
    return all_items

def batch_write_with_retry(table, items, max_retries=3):
    """Batch write items with retry logic"""
    if not items:
        return
        
    # Split into chunks of 25 (DynamoDB limit)
    for i in range(0, len(items), 25):
        chunk = items[i:i + 25]
        for retry in range(max_retries):
            try:
                kwargs = {
                    'RequestItems': {
                        table.name: [{'PutRequest': {'Item': item}} for item in chunk]
                    }
                }
                if not is_local_dynamodb():
                    kwargs['ReturnConsumedCapacity'] = 'TOTAL'
                
                response = table.meta.client.batch_write_item(**kwargs)
                
                # Track capacity
                if is_local_dynamodb():
                    pass
                else:
                    for cc in response.get('ConsumedCapacity', []):
                        pass
                    
                break
            except Exception as e:
                if retry == max_retries - 1:
                    raise
                logger.info(f"Retry {retry + 1} for batch write")
                # Exponential backoff

def update_rating_histories(table, items_to_update, current_time):
    """Update rating histories for multiple items in batch. Each history entry is [rating, timestamp] where both values are Decimals for DynamoDB compatibility."""
    if not items_to_update:
        return
        
    # Prepare all updates
    updates = []
    for item in items_to_update:
        gms_player = item['GameModeServerPlayer']
        current_history = item.get('RatingHistory', [])
        logger.info(f"Processing {gms_player}")
        
        # Only add new entry if rating changed
        latest_entry = current_history[-1] if current_history else None
        current_rating = Decimal(str(item['LatestRating']))
        current_timestamp = Decimal(str(current_time))
        
        if not latest_entry or latest_entry[0] != current_rating:
            current_history.append([current_rating, current_timestamp])
            
            # Create update item
            update_item = {
                'GameModeServerPlayer': gms_player,
                'GameModeServer': item['GameModeServer'],
                'PlayerName': item['PlayerName'],
                'GameMode': item['GameMode'],
                'Server': item['Server'],
                'CurrentRank': item['CurrentRank'],
                'LatestRating': current_rating,
                'RatingHistory': current_history
            }
            updates.append(update_item)
    
    # Write all updates in one batch
    if updates:
        batch_write_with_retry(table, updates)

def process_player_batch(table, players, game_mode, server, current_time):
    """Process a batch of players"""
    # Get current data for all players in one batch
    keys = [{
        'GameModeServerPlayer': f"{game_mode}#{server}#{p['PlayerName'].lower()}",
        'GameModeServer': f"{game_mode}#{server}"
    } for p in players]
    
    # First batch read: Get current data without rating history
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
            rating_history_needed.append({
                'GameModeServerPlayer': gms_player,
                'GameModeServer': gms
            })
            num_updates += 1
    
    # Second batch read: Get rating histories only for items that need updates
    if rating_history_needed:
        history_items = batch_get_with_retry(
            table,
            rating_history_needed,
            'GameModeServerPlayer, RatingHistory'
        )
        history_map = {item['GameModeServerPlayer']: item.get('RatingHistory', []) for item in history_items}
        
        # Update the updates_needed items with their histories
        for item in updates_needed:
            gms_player = item['GameModeServerPlayer']
            item['RatingHistory'] = history_map.get(gms_player, [])
    
    # Batch write updates
    if updates_needed:
        batch_write_with_retry(table, updates_needed)
    
    # Update rating histories in batch
    if rating_history_needed:
        update_rating_histories(table, updates_needed, current_time)
    
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

def get_milestone_table_name():
    """Get milestone table name based on environment"""
    if os.environ.get("AWS_LAMBDA_FUNCTION_NAME"):
        return os.environ.get("MILESTONE_TABLE_NAME", "MilestoneTracking")
    else:
        return "lambda-test-milestone-table"

def fetch_leaderboard_data(game_type: str, max_pages: int) -> dict:
    """Fetch leaderboard data for a specific game type"""
    logger.info(f"Fetching {game_type} data...")
    return getLeaderboardSnapshot(game_type=game_type, max_pages=max_pages)

def create_tasks(leaderboard_data: Dict[str, Dict[str, List[Dict]]]) -> List[Dict]:
    """Create tasks from leaderboard data"""
    tasks = []
    
    for game_mode, server_data in leaderboard_data.items():
        for server, data in server_data.items():
            # Convert dictionary to list of player data
            players = []
            for player_name, stats in data.get(game_mode, {}).items():
                players.append({
                    "PlayerName": player_name,
                    "Rank": stats["rank"],
                    "Rating": stats["rating"]
                })
            
            # Split into batches of 100 players
            for i in range(0, len(players), 100):
                batch = players[i:i + 100]
                tasks.append({
                    "game_mode": game_mode,
                    "server": server,
                    "players": batch
                })
    
    return tasks

def process_leaderboards(table, leaderboard_data: Dict[str, Dict[str, List[Dict]]], current_time: int) -> Dict[str, int]:
    """Process all leaderboards sequentially"""
    updates = {}
    
    for game_mode, server_data in leaderboard_data.items():
        # Convert game mode to database format
        mode_num = "0" if game_mode == "battlegrounds" else "1"
        for server, data in server_data.items():
            # Convert dictionary to list of player data
            players = []
            for player_name, stats in data.get(game_mode, {}).items():
                players.append({
                    "PlayerName": player_name,
                    "Rank": stats["rank"],
                    "Rating": stats["rating"]
                })
            
            # Process in batches of 100
            for i in range(0, len(players), 100):
                batch = players[i:i + 100]
                num_updates = process_player_batch(table, batch, mode_num, server, current_time)
                key = f"{mode_num}#{server}"  # Use # as separator for consistency
                updates[key] = updates.get(key, 0) + num_updates
                logger.info(f"[{key}] Processed batch with {num_updates} updates")
    
    return updates

def lambda_handler(event, context):
    """AWS Lambda handler to fetch and store leaderboard data"""
    try:
        # Get max_pages from event or use default (40 pages = 1000 players)
        max_pages = event.get("max_pages", 40) if event else 40
        
        # Initialize DynamoDB
        table = get_dynamodb_resource().Table(get_table_name())
        
        # Get current timestamp
        current_time = int(datetime.now(timezone.utc).timestamp())
        
        # Fetch leaderboard data sequentially
        logger.info("Fetching battlegrounds data...")
        bg_data = fetch_leaderboard_data("battlegrounds", max_pages)
        logger.info("Fetching battlegroundsduo data...")
        duo_data = fetch_leaderboard_data("battlegroundsduo", max_pages)
        
        leaderboard_data = {
            "battlegrounds": bg_data,
            "battlegroundsduo": duo_data
        }
        
        # Process all leaderboards
        updates = process_leaderboards(table, leaderboard_data, current_time)
        
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
        logger.error(f"Error updating leaderboard data: {str(e)}")
        return {
            "statusCode": 500,
            "body": json.dumps({"error": f"Error updating leaderboard data: {str(e)}"}),
        }

if __name__ == "__main__":
    lambda_handler(None, None)