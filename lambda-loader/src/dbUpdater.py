import json
import os
from datetime import datetime, timezone
from decimal import Decimal
from typing import List, Dict, Any, Tuple
from concurrent.futures import ThreadPoolExecutor, as_completed
import threading
from functools import partial
import time
import logging
from queue import Queue
from dataclasses import dataclass

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

class CapacityTracker:
    def __init__(self):
        self.read_units = 0
        self.write_units = 0
        self._start_time = time.time()
        self.is_local = is_local_dynamodb()
    
    def add_consumed_capacity(self, capacity):
        if self.is_local:
            # Estimate capacity units for local development
            # Read: 1 unit per 4KB, Write: 1 unit per 1KB
            if hasattr(self, '_last_operation'):
                if self._last_operation == 'read':
                    # Rough estimation: assume each item is about 1KB
                    self.read_units += (len(self._last_items) * 1.0) / 4.0
                elif self._last_operation == 'write':
                    # Each write costs at least 1 WCU
                    self.write_units += len(self._last_items) * 1.0
        else:
            if capacity:
                self.read_units += capacity.get('ReadCapacityUnits', 0)
                self.write_units += capacity.get('WriteCapacityUnits', 0)
    
    def track_operation(self, operation_type, items):
        self._last_operation = operation_type
        self._last_items = items
        self.add_consumed_capacity(None)  # Trigger estimation for local mode
    
    def log_consumption(self):
        elapsed_time = time.time() - self._start_time
        env_type = "Local" if self.is_local else "Production"
        logger.info(f"DynamoDB Consumption ({env_type}, over {elapsed_time:.1f}s):")
        logger.info(f"Total Read Capacity Units: {self.read_units:.2f}")
        logger.info(f"Total Write Capacity Units: {self.write_units:.2f}")
        logger.info(f"Average RCU/s: {self.read_units/elapsed_time:.2f}")
        logger.info(f"Average WCU/s: {self.write_units/elapsed_time:.2f}")
        if self.is_local:
            logger.info("Note: Local consumption is estimated based on item counts and sizes")

# Global capacity tracker
capacity_tracker = CapacityTracker()

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
                if not capacity_tracker.is_local:
                    kwargs['ReturnConsumedCapacity'] = 'TOTAL'
                
                response = table.meta.client.batch_get_item(**kwargs)
                items = response['Responses'][table.name]
                all_items.extend(items)
                
                # Track capacity
                if capacity_tracker.is_local:
                    capacity_tracker.track_operation('read', items)
                else:
                    for cc in response.get('ConsumedCapacity', []):
                        capacity_tracker.add_consumed_capacity(cc)
                    
                break
            except Exception as e:
                if retry == max_retries - 1:
                    raise
                logger.info(f"Retry {retry + 1} for batch get")
                time.sleep(0.1 * (retry + 1))  # Exponential backoff
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
                if not capacity_tracker.is_local:
                    kwargs['ReturnConsumedCapacity'] = 'TOTAL'
                
                response = table.meta.client.batch_write_item(**kwargs)
                
                # Track capacity
                if capacity_tracker.is_local:
                    capacity_tracker.track_operation('write', chunk)
                else:
                    for cc in response.get('ConsumedCapacity', []):
                        capacity_tracker.add_consumed_capacity(cc)
                    
                break
            except Exception as e:
                if retry == max_retries - 1:
                    raise
                logger.info(f"Retry {retry + 1} for batch write")
                time.sleep(0.1 * (retry + 1))  # Exponential backoff

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
        'GameModeServerPlayer': f"{game_mode}-{server}-{p['PlayerName']}",
        'GameModeServer': f"{game_mode}-{server}"
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
        gms_player = f"{game_mode}-{server}-{player['PlayerName']}"
        gms = f"{game_mode}-{server}"
        current_item = current_map.get(gms_player)
        
        # Check if update needed
        if not current_item or (
            current_item.get('CurrentRank') != player['Rank'] or 
            current_item.get('LatestRating') != player['Rating']
        ):
            update_item = {
                'GameModeServerPlayer': gms_player,
                'GameModeServer': gms,
                'PlayerName': player['PlayerName'],
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

@dataclass
class LeaderboardTask:
    """Represents a task to process a batch of players for a specific game mode and server"""
    game_mode: str
    server: str
    players: List[Dict]
    batch_size: int = 100  # Default batch size
    priority: int = 0      # Higher priority = processed first

    def __lt__(self, other):
        # For priority queue ordering - higher priority first
        return self.priority > other.priority

def create_tasks(leaderboard_data: Dict[str, Dict[str, List[Dict]]]) -> List[LeaderboardTask]:
    """Create tasks from leaderboard data with appropriate priorities"""
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
            
            # Set priority based on batch size
            priority = len(players)
            
            # Split into batches of 100 players
            for i in range(0, len(players), 100):
                batch = players[i:i + 100]
                tasks.append(LeaderboardTask(
                    game_mode=game_mode,
                    server=server,
                    players=batch,
                    priority=priority
                ))
    
    # Sort tasks by priority (larger batches first)
    tasks.sort(reverse=True)
    return tasks

def process_leaderboards(table, leaderboard_data: Dict[str, Dict[str, List[Dict]]], current_time: int) -> Dict[str, int]:
    """Process all leaderboards using dynamic task allocation"""
    # Create prioritized tasks
    tasks = create_tasks(leaderboard_data)
    
    # Create task queue
    task_queue = Queue()
    for task in tasks:
        task_queue.put(task)
    
    # Calculate optimal number of threads
    total_players = sum(
        len(data.get(game_mode, {}))
        for game_mode, server_data in leaderboard_data.items()
        for server, data in server_data.items()
    )
    num_threads = min(
        max(4, total_players // 500),  # At least 4 threads, 1 thread per 500 players
        16  # Maximum threads
    )
    
    log_with_context("info", f"Processing {total_players} players using {num_threads} threads")
    
    # Create thread pool and process tasks
    updates_by_thread = {}
    with ThreadPoolExecutor(max_workers=num_threads) as executor:
        futures = [
            executor.submit(worker, task_queue, table, current_time)
            for _ in range(num_threads)
        ]
        
        # Wait for all tasks to complete and collect results
        for future in futures:
            try:
                thread_updates = future.result()
                for key, count in thread_updates.items():
                    updates_by_thread[key] = updates_by_thread.get(key, 0) + count
            except Exception as e:
                log_with_context("error", f"Thread failed: {str(e)}")
                raise
    
    # Log completion for each game mode and server
    for key, count in updates_by_thread.items():
        log_with_context("info", f"[{key}] Completed processing with {count} updates")
    
    return updates_by_thread

def worker(task_queue: Queue, table, current_time: int) -> Dict[str, int]:
    """Worker function to process tasks from the queue"""
    updates = {}
    thread_id = threading.get_ident()
    
    while True:
        try:
            task = task_queue.get_nowait()
        except:
            break
            
        try:
            set_thread_context(f"{task.game_mode}-{task.server}")
            
            # Process the batch
            num_updates = process_player_batch(
                table,
                task.players,
                task.game_mode,
                task.server,
                current_time
            )
            
            # Record updates
            key = f"{task.game_mode}-{task.server}"
            updates[key] = updates.get(key, 0) + num_updates
            
            log_with_context("info", f"Thread {thread_id} completed batch with {num_updates} updates")
            
        except Exception as e:
            log_with_context("error", f"Error processing batch: {str(e)}")
            raise
        finally:
            task_queue.task_done()
    
    return updates

def lambda_handler(event, context):
    """AWS Lambda handler to fetch and store leaderboard data"""
    try:
        # Reset capacity tracker
        global capacity_tracker
        capacity_tracker = CapacityTracker()
        
        # Get max_pages from event or use default (40 pages = 1000 players)
        max_pages = event.get("max_pages", 40) if event else 40
        
        # Initialize DynamoDB
        table = get_dynamodb_resource().Table(get_table_name())
        
        # Get current timestamp
        current_time = int(datetime.now(timezone.utc).timestamp())
        
        # Fetch leaderboard data concurrently
        with ThreadPoolExecutor(max_workers=2) as executor:
            log_with_context("info", "Fetching battlegrounds data...")
            log_with_context("info", "Fetching battlegroundsduo data...")
            
            futures = {
                executor.submit(fetch_leaderboard_data, "battlegrounds", max_pages): "battlegrounds",
                executor.submit(fetch_leaderboard_data, "battlegroundsduo", max_pages): "battlegroundsduo"
            }
            
            # Collect results
            leaderboard_data = {}
            for future in as_completed(futures):
                game_type = futures[future]
                try:
                    leaderboard_data[game_type] = future.result()
                except Exception as e:
                    log_with_context("error", f"Error fetching {game_type} data: {str(e)}")
                    raise
        
        # Process all leaderboards with dynamic task allocation
        updates = process_leaderboards(table, leaderboard_data, current_time)
        
        # Log consumption at the end
        capacity_tracker.log_consumption()
        
        return {
            "statusCode": 200,
            "body": json.dumps({
                "message": "Successfully updated leaderboard data",
                "updates": updates
            })
        }
        
    except Exception as e:
        # Log consumption even on error
        capacity_tracker.log_consumption()
        
        logger.error(f"Error updating leaderboard data: {str(e)}")
        return {
            "statusCode": 500,
            "body": json.dumps({
                "error": str(e)
            })
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
