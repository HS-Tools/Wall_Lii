import boto3
import json
from botocore.exceptions import ClientError

def create_local_dynamodb_client():
    return boto3.client(
        'dynamodb',
        endpoint_url='http://localhost:8000',
        region_name='local',
        aws_access_key_id='dummy',
        aws_secret_access_key='dummy'
    )

def create_table_if_not_exists(dynamodb, table_name, key_schema, attribute_definitions, global_secondary_indexes=None):
    try:
        dynamodb.describe_table(TableName=table_name)
        print(f"Table {table_name} already exists")
    except ClientError as e:
        if e.response['Error']['Code'] == 'ResourceNotFoundException':
            print(f"Creating table {table_name}...")
            params = {
                'TableName': table_name,
                'KeySchema': key_schema,
                'AttributeDefinitions': attribute_definitions,
                'BillingMode': 'PAY_PER_REQUEST'
            }
            if global_secondary_indexes:
                params['GlobalSecondaryIndexes'] = global_secondary_indexes
            dynamodb.create_table(**params)
            waiter = dynamodb.get_waiter('table_exists')
            waiter.wait(TableName=table_name)
            print(f"Table {table_name} created successfully")
        else:
            raise e

def load_json_data(file_path):
    with open(file_path, 'r') as f:
        return json.load(f)

def main():
    dynamodb = create_local_dynamodb_client()
    
    # Create alias table
    create_table_if_not_exists(
        dynamodb,
        'alias',
        key_schema=[{'AttributeName': 'Alias', 'KeyType': 'HASH'}],
        attribute_definitions=[{'AttributeName': 'Alias', 'AttributeType': 'S'}]
    )
    
    # Create leaderboard table
    create_table_if_not_exists(
        dynamodb,
        'leaderboard',
        key_schema=[
            {'AttributeName': 'GameModeServerPlayer', 'KeyType': 'HASH'}
        ],
        attribute_definitions=[
            {'AttributeName': 'GameModeServerPlayer', 'AttributeType': 'S'},
            {'AttributeName': 'GameModeServer', 'AttributeType': 'S'},
            {'AttributeName': 'CurrentRank', 'AttributeType': 'N'},
            {'AttributeName': 'PlayerName', 'AttributeType': 'S'},
            {'AttributeName': 'GameMode', 'AttributeType': 'S'}
        ],
        global_secondary_indexes=[
            {
                'IndexName': 'RankLookupIndex',
                'KeySchema': [
                    {'AttributeName': 'GameModeServer', 'KeyType': 'HASH'},
                    {'AttributeName': 'CurrentRank', 'KeyType': 'RANGE'}
                ],
                'Projection': {'ProjectionType': 'ALL'}
            },
            {
                'IndexName': 'PlayerLookupIndex',
                'KeySchema': [
                    {'AttributeName': 'PlayerName', 'KeyType': 'HASH'},
                    {'AttributeName': 'GameMode', 'KeyType': 'RANGE'}
                ],
                'Projection': {'ProjectionType': 'ALL'}
            }
        ]
    )
    
    # Load data from snapshots
    try:
        # Load alias data
        alias_data = load_json_data('scripts/data_snapshots/alias_snapshot.json')
        for item in alias_data.get('Items', []):
            dynamodb.put_item(TableName='alias', Item=item)
        print("Loaded alias data successfully")
        
        # Load leaderboard data
        leaderboard_data = load_json_data('scripts/data_snapshots/leaderboard_snapshot.json')
        for item in leaderboard_data.get('Items', []):
            # Ensure required attributes exist
            if 'PlayerName' not in item:
                continue
                
            player_name = item['PlayerName']['S'].lower()
            server = item.get('Server', {'S': 'NA'})['S']
            game_mode = item.get('GameMode', {'S': '0'})['S']
            
            # Add required composite keys
            item['GameModeServerPlayer'] = {'S': f"{game_mode}#{server}#{player_name}"}
            item['GameModeServer'] = {'S': f"{game_mode}#{server}"}
            
            # Add other required fields
            if 'CurrentRank' not in item:
                item['CurrentRank'] = {'N': '999999'}
            if 'LatestRating' not in item:
                item['LatestRating'] = {'N': '0'}
            if 'RatingHistory' not in item:
                item['RatingHistory'] = {'L': []}
                
            dynamodb.put_item(TableName='leaderboard', Item=item)
        print("Loaded leaderboard data successfully")
        
    except Exception as e:
        print(f"Error loading data: {str(e)}")

if __name__ == '__main__':
    main()
