import boto3
import time

def create_test_table():
    """Create a test DynamoDB table with the new schema"""
    ddb = boto3.client(
        'dynamodb',
        endpoint_url='http://localhost:8000',
        region_name='us-east-1',
        aws_access_key_id='dummy',
        aws_secret_access_key='dummy'
    )

    try:
        # Delete existing test table if it exists
        try:
            ddb.delete_table(TableName='HearthstoneLeaderboardTest')
            print("Deleted existing test table")
            time.sleep(2)
        except:
            pass

        response = ddb.create_table(
            TableName='HearthstoneLeaderboardTest',
            KeySchema=[
                {'AttributeName': 'GameModeServerPlayer', 'KeyType': 'HASH'}
            ],
            AttributeDefinitions=[
                {'AttributeName': 'GameModeServerPlayer', 'AttributeType': 'S'},
                {'AttributeName': 'GameModeServer', 'AttributeType': 'S'},
                {'AttributeName': 'CurrentRank', 'AttributeType': 'N'},
                {'AttributeName': 'PlayerName', 'AttributeType': 'S'},
                {'AttributeName': 'GameMode', 'AttributeType': 'S'}
            ],
            GlobalSecondaryIndexes=[
                {
                    'IndexName': 'RankLookupIndex',
                    'KeySchema': [
                        {'AttributeName': 'GameModeServer', 'KeyType': 'HASH'},
                        {'AttributeName': 'CurrentRank', 'KeyType': 'RANGE'}
                    ],
                    'Projection': {'ProjectionType': 'ALL'},
                    'ProvisionedThroughput': {
                        'ReadCapacityUnits': 5,
                        'WriteCapacityUnits': 5
                    }
                },
                {
                    'IndexName': 'PlayerLookupIndex',
                    'KeySchema': [
                        {'AttributeName': 'PlayerName', 'KeyType': 'HASH'},
                        {'AttributeName': 'GameMode', 'KeyType': 'RANGE'}
                    ],
                    'Projection': {'ProjectionType': 'ALL'},
                    'ProvisionedThroughput': {
                        'ReadCapacityUnits': 5,
                        'WriteCapacityUnits': 5
                    }
                }
            ],
            ProvisionedThroughput={
                'ReadCapacityUnits': 5,
                'WriteCapacityUnits': 5
            }
        )
        print("Created test table successfully!")
        return response
    except Exception as e:
        print(f"Error creating table: {str(e)}")
        raise e

if __name__ == "__main__":
    create_test_table() 