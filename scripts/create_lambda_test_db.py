import boto3
import sys
from decimal import Decimal

def create_local_dynamodb():
    # Connect to the local DynamoDB
    dynamodb = boto3.resource('dynamodb', endpoint_url='http://localhost:8000')

    # Define the table structure
    table_name = "lambda-test-table"
    try:
        # Delete table if it already exists (for testing purposes)
        table = dynamodb.Table(table_name)
        table.delete()
        table.wait_until_not_exists()
    except Exception as e:
        print(f"Error deleting table (if exists): {e}")

    # Create the table
    table = dynamodb.create_table(
        TableName=table_name,
        KeySchema=[
            {"AttributeName": "GameModeServerPlayer", "KeyType": "HASH"},
            {"AttributeName": "GameModeServer", "KeyType": "RANGE"},
        ],
        AttributeDefinitions=[
            {"AttributeName": "GameModeServerPlayer", "AttributeType": "S"},
            {"AttributeName": "GameModeServer", "AttributeType": "S"},
            {"AttributeName": "CurrentRank", "AttributeType": "N"},
            {"AttributeName": "PlayerName", "AttributeType": "S"},
            {"AttributeName": "GameMode", "AttributeType": "S"},
        ],
        GlobalSecondaryIndexes=[
            {
                "IndexName": "RankLookupIndex",
                "KeySchema": [
                    {"AttributeName": "GameModeServer", "KeyType": "HASH"},
                    {"AttributeName": "CurrentRank", "KeyType": "RANGE"},
                ],
                "Projection": {"ProjectionType": "ALL"},
                "ProvisionedThroughput": {
                    "ReadCapacityUnits": 2,
                    "WriteCapacityUnits": 2,
                },
            },
            {
                "IndexName": "PlayerLookupIndex",
                "KeySchema": [
                    {"AttributeName": "PlayerName", "KeyType": "HASH"},
                    {"AttributeName": "GameMode", "KeyType": "RANGE"},
                ],
                "Projection": {"ProjectionType": "ALL"},
                "ProvisionedThroughput": {
                    "ReadCapacityUnits": 2,
                    "WriteCapacityUnits": 2,
                },
            },
        ],
        BillingMode="PAY_PER_REQUEST",  # Use on-demand for local testing
    )

    # Wait until the table is created
    table.wait_until_exists()
    print(f"Table {table_name} created successfully!")

def create_milestone_table(dynamodb):
    """Create milestone tracking table"""
    table_name = 'lambda-test-milestone-table'
    try:
        # Delete table if it already exists (for testing purposes)
        table = dynamodb.Table(table_name)
        table.delete()
        table.wait_until_not_exists()
    except Exception as e:
        print(f"Error deleting milestone table (if exists): {e}")

    try:
        table = dynamodb.create_table(
            TableName=table_name,
            KeySchema=[
                {
                    'AttributeName': 'SeasonGameModeServer',
                    'KeyType': 'HASH'
                },
                {
                    'AttributeName': 'Milestone',
                    'KeyType': 'RANGE'
                }
            ],
            AttributeDefinitions=[
                {
                    'AttributeName': 'SeasonGameModeServer',
                    'AttributeType': 'S'
                },
                {
                    'AttributeName': 'Milestone',
                    'AttributeType': 'N'
                }
            ],
            ProvisionedThroughput={
                'ReadCapacityUnits': 1,
                'WriteCapacityUnits': 1
            }
        )
        table.wait_until_exists()
        print(f"Table {table_name} created successfully!")
        return table
    except Exception as e:
        print("Error creating milestone table:", str(e))
        return None

def main():
    """Create tables in local DynamoDB"""
    # Connect to local DynamoDB
    dynamodb = boto3.resource(
        'dynamodb',
        endpoint_url='http://localhost:8000',
        region_name='us-west-2',
        aws_access_key_id='dummy',
        aws_secret_access_key='dummy'
    )

    # Create leaderboard table
    create_local_dynamodb()

    # Create milestone table
    milestone_table = create_milestone_table(dynamodb)
    if not milestone_table:
        print("Failed to create milestone table")
        sys.exit(1)

    print("Successfully created all tables!")

if __name__ == "__main__":
    main()