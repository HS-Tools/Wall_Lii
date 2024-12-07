import time

import boto3


def create_local_table():
    """Create a local DynamoDB table"""
    ddb = boto3.client(
        "dynamodb",
        endpoint_url="http://localhost:8000",
        region_name="us-east-1",
        aws_access_key_id="dummy",
        aws_secret_access_key="dummy",
    )

    try:
        # First, delete existing table if it exists
        try:
            ddb.delete_table(TableName="HearthstoneLeaderboard")
            print("Deleted existing table")
            time.sleep(2)  # Wait for deletion
        except:
            pass

        response = ddb.create_table(
            TableName="HearthstoneLeaderboard",
            KeySchema=[
                {"AttributeName": "GameModeServerPlayer", "KeyType": "HASH"},
                {"AttributeName": "CurrentRank", "KeyType": "RANGE"},
            ],
            AttributeDefinitions=[
                {"AttributeName": "GameModeServerPlayer", "AttributeType": "S"},
                {"AttributeName": "CurrentRank", "AttributeType": "N"},
                {"AttributeName": "GameModeServer", "AttributeType": "S"},
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
                        "ReadCapacityUnits": 5,
                        "WriteCapacityUnits": 5,
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
                        "ReadCapacityUnits": 5,
                        "WriteCapacityUnits": 5,
                    },
                },
            ],
            ProvisionedThroughput={"ReadCapacityUnits": 5, "WriteCapacityUnits": 5},
        )
        print("Table created successfully!")
        return response
    except Exception as e:
        print(f"Error creating table: {str(e)}")
        raise e


def wait_for_table_active():
    """Wait until table is active"""
    ddb = boto3.client(
        "dynamodb",
        endpoint_url="http://localhost:8000",
        region_name="us-east-1",
        aws_access_key_id="dummy",
        aws_secret_access_key="dummy",
    )

    print("Waiting for table to become active...")
    waiter = ddb.get_waiter("table_exists")
    waiter.wait(
        TableName="HearthstoneLeaderboard", WaiterConfig={"Delay": 1, "MaxAttempts": 20}
    )
    print("Table is active!")


def verify_table():
    """Verify table and indexes exist and are active"""
    ddb = boto3.client(
        "dynamodb",
        endpoint_url="http://localhost:8000",
        region_name="us-east-1",
        aws_access_key_id="dummy",
        aws_secret_access_key="dummy",
    )

    try:
        response = ddb.describe_table(TableName="HearthstoneLeaderboard")
        table = response["Table"]

        # Check table status
        if table["TableStatus"] != "ACTIVE":
            print(f"Table status is {table['TableStatus']}, waiting...")
            wait_for_table_active()

        # Check indexes
        indexes = {idx["IndexName"] for idx in table.get("GlobalSecondaryIndexes", [])}
        required = {"RankLookupIndex", "PlayerLookupIndex"}

        if not required.issubset(indexes):
            missing = required - indexes
            raise Exception(f"Missing required indexes: {missing}")

        print("Table verification successful!")
        return True

    except Exception as e:
        print(f"Table verification failed: {str(e)}")
        return False


def delete_existing_table():
    """Delete existing table if it exists"""
    ddb = boto3.client(
        "dynamodb",
        endpoint_url="http://localhost:8000",
        region_name="us-east-1",
        aws_access_key_id="dummy",
        aws_secret_access_key="dummy",
    )

    try:
        ddb.delete_table(TableName="HearthstoneLeaderboard")
        print("Deleted existing table")
    except:
        pass  # Table might not exist


if __name__ == "__main__":
    delete_existing_table()
    time.sleep(2)  # Wait for deletion
    create_local_table()
    wait_for_table_active()
    verify_table()
