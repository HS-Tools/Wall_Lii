from datetime import datetime

import boto3


def update_leaderboard_data(table_name, leaderboard_data, season_id):
    """
    Batch writes leaderboard data into the DynamoDB table only if the MMR is different.

    Args:
        table_name (str): The name of the DynamoDB table.
        leaderboard_data (dict): Processed leaderboard data from the API.
        season_id (int): The current season ID.
    """
    dynamodb = boto3.resource("dynamodb")
    table = dynamodb.Table(table_name)

    # Batch write using a batch writer
    with table.batch_writer() as batch:
        for region, game_modes in leaderboard_data.items():
            for game_mode, players in game_modes.items():
                for player_name, player_data in players.items():
                    # Construct PK and SK
                    pk = f"player#{player_name}#{region}"
                    sk = f"{datetime.now().strftime('%Y-%m-%dT%H:%M')}#{player_data['rank']}"

                    # Query the latest record for this player
                    latest_record = table.query(
                        KeyConditionExpression="PK = :pk",
                        ExpressionAttributeValues={":pk": pk},
                        ScanIndexForward=False,  # Descending order
                        Limit=1,
                    )

                    # Check if the MMR has changed
                    if latest_record["Count"] > 0:
                        latest_mmr = latest_record["Items"][0]["MMR"]
                        if latest_mmr == player_data["rating"]:
                            # Skip writing if MMR hasn't changed
                            continue

                    # Prepare the item
                    item = {
                        "PK": pk,
                        "SK": sk,
                        "playerName": player_name,
                        "rank": player_data["rank"],
                        "server": region,
                        "MMR": player_data["rating"],
                        "gameType": game_mode,
                        "seasonID": season_id,
                        "lastUpdated": datetime.now().isoformat(),
                    }

                    # Add to the batch
                    batch.put_item(Item=item)

    print("Leaderboard data updated successfully.")


def create_table(table_name="HearthstoneLeaderboard"):
    dynamodb = boto3.resource(
        "dynamodb",
        endpoint_url="http://localhost:8000",
        region_name="us-west-2",
        aws_access_key_id="dummy",
        aws_secret_access_key="dummy",
    )

    table = dynamodb.create_table(
        TableName=table_name,
        KeySchema=[
            {
                "AttributeName": "partition_key",  # region#gameType (e.g., "US#battlegrounds")
                "KeyType": "HASH",
            },
            {
                "AttributeName": "sort_key",  # rank#timestamp (e.g., "001#2024-11-30T00:00:00")
                "KeyType": "RANGE",
            },
        ],
        AttributeDefinitions=[
            {"AttributeName": "partition_key", "AttributeType": "S"},
            {"AttributeName": "sort_key", "AttributeType": "S"},
            {"AttributeName": "player_name", "AttributeType": "S"},
        ],
        GlobalSecondaryIndexes=[
            {
                "IndexName": "PlayerNameIndex",
                "KeySchema": [
                    {"AttributeName": "player_name", "KeyType": "HASH"},
                    {"AttributeName": "sort_key", "KeyType": "RANGE"},
                ],
                "Projection": {"ProjectionType": "ALL"},
            }
        ],
        BillingMode="PAY_PER_REQUEST",
    )

    return table
