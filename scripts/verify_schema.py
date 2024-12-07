from decimal import Decimal

import boto3


def get_dynamodb():
    return boto3.resource(
        "dynamodb",
        endpoint_url="http://localhost:8000",
        region_name="us-east-1",
        aws_access_key_id="dummy",
        aws_secret_access_key="dummy",
    )


def verify_table_contents():
    """Verify no duplicate entries exist"""
    ddb = get_dynamodb()
    table = ddb.Table("HearthstoneLeaderboard")

    # Scan the table
    response = table.scan()
    items = response["Items"]

    # Group by GameModeServer
    by_server = {}
    for item in items:
        key = item["GameModeServer"]
        if key not in by_server:
            by_server[key] = []
        by_server[key].append(item)

    # Check for rank duplicates
    for server, server_items in by_server.items():
        ranks = {}
        for item in server_items:
            rank = item["CurrentRank"]
            if rank in ranks:
                print(f"Duplicate rank {rank} found in {server}:")
                print(
                    f"  1: {ranks[rank]['PlayerName']} - {ranks[rank]['LatestRating']}"
                )
                print(f"  2: {item['PlayerName']} - {item['LatestRating']}")
            ranks[rank] = item


if __name__ == "__main__":
    verify_table_contents()
