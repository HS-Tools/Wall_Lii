import boto3
import time
from datetime import datetime, timedelta
import requests
from botocore.exceptions import EndpointConnectionError

def wait_for_dynamodb(max_attempts=5):
    """Wait for local DynamoDB to be ready"""
    for i in range(max_attempts):
        try:
            requests.get('http://localhost:8000')
            print("DynamoDB is running")
            return True
        except requests.exceptions.ConnectionError:
            if i < max_attempts - 1:
                print(f"Waiting for DynamoDB... (attempt {i+1}/{max_attempts})")
                time.sleep(2)
            else:
                print("Error: DynamoDB is not running. Please start it with:")
                print("docker-compose up -d dynamodb-local")
                return False

def create_milestone_table():
    """Create test milestone tracking table"""
    if not wait_for_dynamodb():
        return

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
            ddb.delete_table(TableName='MilestoneTracking')
            print("Deleted existing milestone table")
            time.sleep(2)
        except:
            pass

        # Create new table
        response = ddb.create_table(
            TableName='MilestoneTracking',
            KeySchema=[
                {'AttributeName': 'SeasonGameModeServer', 'KeyType': 'HASH'},
                {'AttributeName': 'Milestone', 'KeyType': 'RANGE'}
            ],
            AttributeDefinitions=[
                {'AttributeName': 'SeasonGameModeServer', 'AttributeType': 'S'},
                {'AttributeName': 'Milestone', 'AttributeType': 'N'}
            ],
            BillingMode='PAY_PER_REQUEST'
        )
        print("Created milestone table successfully!")
        return response
    except Exception as e:
        print(f"Error creating table: {str(e)}")
        raise e

def populate_test_data():
    """Add mock milestone data"""
    ddb = boto3.resource(
        'dynamodb',
        endpoint_url='http://localhost:8000',
        region_name='us-east-1',
        aws_access_key_id='dummy',
        aws_secret_access_key='dummy'
    )
    
    table = ddb.Table('MilestoneTracking')
    
    # Mock data - Season 1, Regular BG (mode 0)
    milestones = [
        # NA Server
        {
            'SeasonGameModeServer': '1-0-NA',
            'Milestone': 8000,
            'PlayerName': 'beterbabbit',
            'Timestamp': int((datetime.now() - timedelta(days=60)).timestamp()),
            'Rating': 8123
        },
        {
            'SeasonGameModeServer': '1-0-NA',
            'Milestone': 9000,
            'PlayerName': 'beterbabbit',
            'Timestamp': int((datetime.now() - timedelta(days=45)).timestamp()),
            'Rating': 9045
        },
        # EU Server
        {
            'SeasonGameModeServer': '1-0-EU',
            'Milestone': 8000,
            'PlayerName': 'sevel',
            'Timestamp': int((datetime.now() - timedelta(days=55)).timestamp()),
            'Rating': 8234
        }
    ]
    
    # Add items
    with table.batch_writer() as batch:
        for milestone in milestones:
            batch.put_item(Item=milestone)
    
    print(f"Added {len(milestones)} test milestones")

if __name__ == "__main__":
    create_milestone_table()
    time.sleep(2)  # Wait for table creation
    populate_test_data() 