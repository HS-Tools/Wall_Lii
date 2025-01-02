import json
import os
from datetime import datetime, timezone
from decimal import Decimal
from typing import List, Dict, Any, Tuple
from concurrent.futures import ThreadPoolExecutor, as_completed
import threading
from functools import partial
import time

import boto3
from boto3.dynamodb.conditions import Key
from api import getLeaderboardSnapshot

from logger import setup_logger

logger = setup_logger("dbUpdater")

# Thread-local storage for thread-specific logging context
thread_local = threading.local()

def get_thread_logger():
    """Get thread-specific logger with context"""
    if not hasattr(thread_local, "logger_context"):
        thread_local.logger_context = ""
    return logger

def set_thread_context(context):
    """Set thread-specific logging context"""
    thread_local.logger_context = f"[{context}] "

def log_with_context(level, message):
    """Log message with thread context"""
    context = getattr(thread_local, "logger_context", "")
    if level == "info":
        logger.info(f"{context}{message}")
    elif level == "error":
        logger.error(f"{context}{message}")
    elif level == "debug":
        logger.debug(f"{context}{message}")

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
    """Get table name based on environment"""
    if os.environ.get("AWS_LAMBDA_FUNCTION_NAME"):
        return os.environ.get("TABLE_NAME", "LeaderboardData")
    else:
        return "lambda-test-table"

def batch_get_player_data(table, keys: List[Dict[str, Any]], projection: List[str]) -> Dict[str, Dict]:
    """
    Batch get items from DynamoDB with specified projection
    
    Args:
        table: DynamoDB table resource
        keys: List of key dictionaries
        projection: List of attributes to fetch
        
    Returns:
        Dictionary mapping GameModeServerPlayer to item data
    """
    results = {}
    logger.info(f"Batch getting {len(keys)} items with projection {projection}")
    
    # Process in batches of 100 (DynamoDB limit)
    for i in range(0, len(keys), 100):
        batch_keys = keys[i:i + 100]
        try:
            response = table.meta.client.batch_get_item(
                RequestItems={
                    table.name: {
                        'Keys': batch_keys,
                        'ProjectionExpression': ', '.join(projection)
                    }
                }
            )
            
            # Add results to our dictionary
            for item in response['Responses'][table.name]:
                results[item['GameModeServerPlayer']] = item
                
            # Handle unprocessed keys
            unprocessed = response['UnprocessedKeys'].get(table.name, {}).get('Keys', [])
            while unprocessed:
                logger.info(f"Retrying {len(unprocessed)} unprocessed keys")
                response = table.meta.client.batch_get_item(
                    RequestItems={
                        table.name: {
                            'Keys': unprocessed,
                            'ProjectionExpression': ', '.join(projection)
                        }
                    }
                )
                for item in response['Responses'][table.name]:
                    results[item['GameModeServerPlayer']] = item
                unprocessed = response['UnprocessedKeys'].get(table.name, {}).get('Keys', [])
                
        except Exception as e:
            logger.error(f"Error in batch_get_player_data: {str(e)}")
            logger.error(f"Batch keys: {batch_keys}")
            raise
    
    logger.info(f"Retrieved {len(results)} items from DynamoDB")
    return results

def batch_write_items(table, items: List[Dict[str, Any]]):
    """
    Write items to DynamoDB in batches
    
    Args:
        table: DynamoDB table resource
        items: List of items to write
    """
    with table.batch_writer() as batch:
        for item in items:
            try:
                batch.put_item(Item=item)
            except Exception as e:
                logger.error(f"Error writing item {item.get('GameModeServerPlayer')}: {str(e)}")

def process_player_batch(
    table,
    players: List[Dict[str, Any]],
    game_mode: str,
    server: str,
    current_time: int
) -> Tuple[int, List[Dict[str, Any]], List[Dict[str, Any]]]:
    """
    Process a batch of players and prepare updates
    
    Args:
        table: DynamoDB table resource
        players: List of player data from API
        game_mode: Game mode being processed
        server: Server being processed
        current_time: Current timestamp
        
    Returns:
        Tuple of (number of updates, list of items to update, list of items needing rating history)
    """
    # Normalize server names
    server_mapping = {"US": "NA", "EU": "EU", "AP": "AP"}
    server = server_mapping.get(server, server)
    
    # Prepare batch get keys
    keys = []
    for player in players:
        player_name = player["PlayerName"].lower()
        game_mode_server_player = f"{game_mode}#{server}#{player_name}"
        game_mode_server = f"{game_mode}#{server}"
        keys.append({
            "GameModeServerPlayer": game_mode_server_player,
            "GameModeServer": game_mode_server
        })
    
    # Batch get current data
    current_data = batch_get_player_data(
        table,
        keys,
        ["GameModeServerPlayer", "CurrentRank", "LatestRating"]
    ) if keys else {}
    
    # Identify players needing updates
    updates_needed = []
    rating_history_needed = []
    
    for player in players:
        player_name = player["PlayerName"].lower()
        game_mode_server_player = f"{game_mode}#{server}#{player_name}"
        game_mode_server = f"{game_mode}#{server}"
        
        rank = Decimal(str(player["Rank"]))
        rating = Decimal(str(player["Rating"]))
        
        current = current_data.get(game_mode_server_player, {})
        current_rating = current.get("LatestRating")
        current_rank = current.get("CurrentRank")
        
        # If player doesn't exist or rating/rank has changed
        if not current or current_rating != rating or current_rank != rank:
            # Prepare update item
            update_item = {
                "GameModeServerPlayer": game_mode_server_player,
                "GameModeServer": game_mode_server,
                "PlayerName": player_name,
                "GameMode": game_mode,
                "Server": server,
                "CurrentRank": rank,
                "LatestRating": rating,
            }
            
            # Only set initial rating history for new players
            if not current:
                update_item["RatingHistory"] = [[rating, current_time]]
            else:
                # If player exists and rating changed, need to update rating history
                if current.get("LatestRating") is not None and current_rating != rating:
                    rating_history_needed.append(update_item)
            
            updates_needed.append(update_item)
            
            # Check for rank 1 milestone
            if rank == 1:
                check_milestones(player_name, rating, game_mode, server, table)
    
    return len(updates_needed), updates_needed, rating_history_needed

def update_rating_histories(table, items: List[Dict[str, Any]], current_time: int):
    """Update rating histories for items that need it"""
    if not items:
        return
    
    logger.info(f"Updating rating histories for {len(items)} items")
    logger.debug(f"First item to update: {items[0] if items else None}")
        
    # Prepare keys for batch get
    keys = [{
        "GameModeServerPlayer": item["GameModeServerPlayer"],
        "GameModeServer": item["GameModeServer"]
    } for item in items]
        
    # Batch get current rating histories
    try:
        current_histories = batch_get_player_data(
            table,
            keys,
            ["GameModeServerPlayer", "RatingHistory"]
        )
    except Exception as e:
        logger.error(f"Error getting current histories: {str(e)}")
        logger.error(f"Items: {items}")
        raise
    
    logger.info(f"Retrieved {len(current_histories)} current histories")
    
    # Prepare updates with rating histories
    updates = []
    for item in items:
        try:
            gmsp = item["GameModeServerPlayer"]
            current = current_histories.get(gmsp, {})
            logger.debug(f"Processing {gmsp}: Current data = {current}")
            
            if current and "RatingHistory" in current:
                item["RatingHistory"] = current["RatingHistory"] + [[item["LatestRating"], current_time]]
            else:
                item["RatingHistory"] = [[item["LatestRating"], current_time]]
            updates.append(item)
        except Exception as e:
            logger.error(f"Error processing item {item}: {str(e)}")
            raise
    
    # Write updates in batches
    try:
        batch_write_items(table, updates)
        logger.info(f"Successfully wrote {len(updates)} rating history updates")
    except Exception as e:
        logger.error(f"Error writing updates: {str(e)}")
        logger.error(f"Updates: {updates}")
        raise

def check_milestones(player_name, rating, game_mode, server, table):
    """Check if player has reached a new milestone"""
    try:
        # Current season is 14
        season = "14"
        season_game_mode_server = f"{season}-{game_mode}-{server}"

        logger.info(
            f"Checking milestones for {player_name} ({rating}) in {season_game_mode_server}"
        )

        # Get milestone table
        milestone_table_name = get_milestone_table_name()
        logger.info(f"Using milestone table: {milestone_table_name}")

        # Use same resource as main table but different table name
        milestone_table = get_dynamodb_resource().Table(milestone_table_name)

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

def batch_get_with_retry(table, keys, projection_expression, max_retries=3):
    """Batch get items with retry logic"""
    for retry in range(max_retries):
        try:
            response = table.meta.client.batch_get_item(
                RequestItems={
                    table.name: {
                        'Keys': keys,
                        'ProjectionExpression': projection_expression
                    }
                }
            )
            return response['Responses'][table.name]
        except Exception as e:
            if retry == max_retries - 1:
                raise
            logger.info(f"Retry {retry + 1} for batch get")
            time.sleep(0.1 * (retry + 1))  # Exponential backoff

def batch_write_with_retry(table, items, max_retries=3):
    """Batch write items with retry logic"""
    for retry in range(max_retries):
        try:
            with table.batch_writer() as batch:
                for item in items:
                    batch.put_item(Item=item)
            return
        except Exception as e:
            if retry == max_retries - 1:
                raise
            logger.info(f"Retry {retry + 1} for batch write")
            time.sleep(0.1 * (retry + 1))  # Exponential backoff

def lambda_handler(event, context):
    """AWS Lambda handler to fetch and store leaderboard data"""
    try:
        # Get max_pages from event or use default (40 pages = 1000 players)
        max_pages = event.get("max_pages", 40)
        
        # Get table
        table = get_dynamodb_resource().Table(get_table_name())
        
        # Get current time once for all updates
        current_time = int(datetime.now(timezone.utc).timestamp())
        
        # Fetch all data in parallel
        with ThreadPoolExecutor(max_workers=2) as executor:
            futures = {
                executor.submit(fetch_leaderboard_data, "battlegrounds", max_pages): "battlegrounds",
                executor.submit(fetch_leaderboard_data, "battlegroundsduo", max_pages): "battlegroundsduo"
            }
            
            # Wait for all API calls to complete
            data = {}
            for future in as_completed(futures):
                game_type = futures[future]
                try:
                    data[game_type] = future.result()
                except Exception as e:
                    logger.error(f"Error fetching {game_type} data: {str(e)}")
                    data[game_type] = None
        
        # Define tasks using the pre-fetched data
        tasks = []
        
        # Add battlegrounds tasks
        if data.get("battlegrounds"):
            for server in ["NA", "EU", "AP"]:
                if server in data["battlegrounds"]:
                    tasks.append(("0", "battlegrounds", server, data["battlegrounds"][server].get("battlegrounds", {})))
        
        # Add duo tasks
        if data.get("battlegroundsduo"):
            for server in ["NA", "EU", "AP"]:
                if server in data["battlegroundsduo"]:
                    tasks.append(("1", "battlegroundsduo", server, data["battlegroundsduo"][server].get("battlegroundsduo", {})))
        
        # Process updates for each game mode in parallel
        updates = {"battlegrounds": 0, "battlegroundsduo": 0}
        
        def process_task(task):
            """Process a single task with pre-fetched data"""
            game_mode, game_type, server, player_data = task
            
            # Set thread context for logging
            set_thread_context(f"{game_type}-{server}")
            
            try:
                # Convert dictionary to list of player data
                players = []
                for player_name, stats in player_data.items():
                    players.append({
                        "PlayerName": player_name,
                        "Rank": stats["rank"],
                        "Rating": stats["rating"]
                    })
                
                total_updates = 0
                pages_per_batch = 4  # Process 100 players at a time
                
                # Process players in batches
                for i in range(0, len(players), pages_per_batch * 25):
                    batch = players[i:i + pages_per_batch * 25]
                    
                    # Process the batch with retries
                    max_retries = 3
                    for retry in range(max_retries):
                        try:
                            num_updates, updates_needed, rating_history_needed = process_player_batch(
                                table, batch, game_mode, server, current_time
                            )
                            
                            if rating_history_needed:
                                # Update items needing rating history updates
                                update_rating_histories(table, rating_history_needed, current_time)
                            
                            if updates_needed:
                                # Write all updates
                                batch_write_with_retry(table, updates_needed)
                            
                            total_updates += num_updates
                            break
                        except Exception as e:
                            if retry == max_retries - 1:
                                log_with_context("error", f"Failed to process batch after {max_retries} retries: {str(e)}")
                                raise
                            log_with_context("info", f"Retry {retry + 1} for batch processing")
                
                log_with_context("info", f"Completed processing with {total_updates} updates")
                return game_type, total_updates
                
            except Exception as e:
                log_with_context("error", f"Error processing {game_type} {server}: {str(e)}")
                raise
        
        # Use ThreadPoolExecutor with a maximum of 3 concurrent threads
        with ThreadPoolExecutor(max_workers=3) as executor:
            # Submit all tasks
            futures = [executor.submit(process_task, task) for task in tasks]
            
            # Process completed futures
            for future in as_completed(futures):
                try:
                    game_type, num_updates = future.result()
                    updates[game_type] += num_updates
                except Exception as e:
                    logger.error(f"Task failed: {str(e)}")
        
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

def main():
    """Main function for local execution"""
    event = {
        "game_modes": ["0", "1"],
        "servers": ["NA", "EU", "AP"]
    }
    lambda_handler(event, None)

if __name__ == "__main__":
    main()
