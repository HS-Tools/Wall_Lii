import boto3
from decimal import Decimal
import logging
from typing import List, Dict, Any

# Setup logging
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger("migration")

def get_dynamodb_resource():
    """Get DynamoDB resource for production"""
    return boto3.resource("dynamodb", region_name="us-east-1")

def convert_rating_history(history: List[Any]) -> List[List[Decimal]]:
    """Convert rating history to standard format: [[rating, timestamp], ...]"""
    clean_history = []
    
    for entry in history:
        if isinstance(entry, dict):
            if 'M' in entry:  # DynamoDB map format
                clean_history.append([
                    Decimal(entry['M']['Rating']['N']),
                    Decimal(entry['M']['Timestamp']['N'])
                ])
            else:  # Python dict format
                clean_history.append([
                    Decimal(str(entry['Rating'])),
                    Decimal(str(entry['Timestamp']))
                ])
        elif isinstance(entry, list):
            if isinstance(entry[0], dict) and 'N' in entry[0]:  # DynamoDB list format
                clean_history.append([
                    Decimal(entry[0]['N']),
                    Decimal(entry[1]['N'])
                ])
            else:  # Already in correct format
                clean_history.append([
                    Decimal(str(entry[0])),
                    Decimal(str(entry[1]))
                ])
    
    return clean_history

def migrate_rating_histories():
    """Migrate all rating histories to the standard format"""
    dynamodb = get_dynamodb_resource()
    table = dynamodb.Table("HearthstoneLeaderboardV2")
    
    # Scan the table to get all items
    response = table.scan(
        ProjectionExpression="GameModeServerPlayer, GameModeServer, PlayerName, RatingHistory, LatestRating"
    )
    items = response.get('Items', [])
    
    # Process items in batches of 25 (DynamoDB batch write limit)
    batch_size = 25
    for i in range(0, len(items), batch_size):
        batch = items[i:i + batch_size]
        updates = []
        
        for item in batch:
            if 'RatingHistory' not in item:
                continue
                
            try:
                # Convert the rating history to standard format
                old_history = item['RatingHistory']
                new_history = convert_rating_history(old_history)
                
                # Only update if the format changed
                if new_history != old_history:
                    logger.info(f"Converting history for {item['PlayerName']}")
                    logger.info(f"Old format: {old_history}")
                    logger.info(f"New format: {new_history}")
                    
                    updates.append({
                        'PutRequest': {
                            'Item': {
                                'GameModeServerPlayer': item['GameModeServerPlayer'],
                                'GameModeServer': item['GameModeServer'],
                                'PlayerName': item['PlayerName'],
                                'RatingHistory': new_history,
                                'LatestRating': item.get('LatestRating')
                            }
                        }
                    })
            except Exception as e:
                logger.error(f"Error processing {item['PlayerName']}: {e}")
                continue
        
        # Execute batch write if there are updates
        if updates:
            try:
                dynamodb.batch_write_item(RequestItems={
                    'HearthstoneLeaderboardV2': updates
                })
                logger.info(f"Successfully updated {len(updates)} items")
            except Exception as e:
                logger.error(f"Error in batch write: {e}")

if __name__ == "__main__":
    migrate_rating_histories()
