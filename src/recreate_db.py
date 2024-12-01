import boto3


def recreate_table(table_name="HearthstoneLeaderboard"):
    """Recreate DynamoDB table with new schema"""
    dynamodb = boto3.resource(
        "dynamodb",
        endpoint_url="http://localhost:8000",
        region_name="us-west-2",
        aws_access_key_id="dummy",
        aws_secret_access_key="dummy",
    )

    # Delete existing table if it exists
    try:
        table = dynamodb.Table(table_name)
        table.delete()
        print("Deleted existing table")
        table.wait_until_not_exists()
    except Exception as e:
        print(f"Error deleting table: {e}")

    # Create new table
    table = dynamodb.create_table(
        TableName=table_name,
        KeySchema=[
            {
                "AttributeName": "player_key",
                "KeyType": "HASH",
            },  # player_name#region#game_type
            {"AttributeName": "timestamp", "KeyType": "RANGE"},
        ],
        AttributeDefinitions=[
            {"AttributeName": "player_key", "AttributeType": "S"},
            {"AttributeName": "timestamp", "AttributeType": "S"},
            {"AttributeName": "region_key", "AttributeType": "S"},  # region#game_type
            {"AttributeName": "rank", "AttributeType": "N"},
        ],
        GlobalSecondaryIndexes=[
            {
                "IndexName": "RankIndex",
                "KeySchema": [
                    {"AttributeName": "region_key", "KeyType": "HASH"},
                    {"AttributeName": "rank", "KeyType": "RANGE"},
                ],
                "Projection": {"ProjectionType": "ALL"},
                "ProvisionedThroughput": {
                    "ReadCapacityUnits": 5,
                    "WriteCapacityUnits": 5,
                },
            }
        ],
        ProvisionedThroughput={"ReadCapacityUnits": 5, "WriteCapacityUnits": 5},
    )
    print("Created new table with updated schema")
    return table


if __name__ == "__main__":
    recreate_table()
