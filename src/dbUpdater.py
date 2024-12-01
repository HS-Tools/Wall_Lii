import time
from datetime import datetime, timedelta

import boto3

from api import getLeaderboardSnapshot


def get_latest_timestamp(table, region, game_type):
    """
    Get the timestamp of the most recent entry for a given region and game type.
    """
    try:
        region_key = f"{region}#{game_type}"

        # Query using RankIndex to get most recent entry for this region/game_type
        response = table.query(
            IndexName="RankIndex",
            KeyConditionExpression="region_key = :rk",
            ExpressionAttributeValues={":rk": region_key},
            ScanIndexForward=False,  # Get most recent first
            Limit=1,
        )

        if response["Items"]:
            return response["Items"][0]["timestamp"]
        return None

    except Exception as e:
        print(f"Error getting latest timestamp: {e}")
        return None


def write_leaderboard_entry(table, player_data, region, game_type):
    """Write a single leaderboard entry to DynamoDB only if rank or MMR changed."""
    timestamp = datetime.now().strftime("%Y-%m-%dT%H:%M:%S.%f")
    player_name = player_data["name"].lower().strip()

    # Create composite keys
    player_key = f"{player_name}#{region}#{game_type}"
    region_key = f"{region}#{game_type}"

    # Get player's most recent entry
    response = table.query(
        KeyConditionExpression="player_key = :pk",
        ExpressionAttributeValues={":pk": player_key},
        ScanIndexForward=False,  # Get most recent first
        Limit=1,
    )

    # Only write if this is first entry or rank/MMR changed
    if response["Items"]:
        latest_entry = response["Items"][0]
        if (
            latest_entry["rank"] == player_data["rank"]
            and latest_entry["MMR"] == player_data["rating"]
        ):
            return False  # No changes in rank or MMR, don't write

    # Write new entry if it's first time seeing player or there were changes
    item = {
        "player_key": player_key,
        "timestamp": timestamp,
        "region_key": region_key,
        "player_name": player_name,
        "rank": player_data["rank"],
        "MMR": player_data["rating"],
        "region": region,
        "gameType": game_type,
    }

    try:
        table.put_item(Item=item)
        print(
            f"Added new entry for {player_name} (Rank {player_data['rank']}, MMR {player_data['rating']}) on {region}"
        )
        return True
    except Exception as e:
        print(f"Error writing entry for {player_name}: {e}")
        return False


def update_leaderboard(table_name="HearthstoneLeaderboard"):
    """Update the leaderboard data in DynamoDB."""
    print(
        f"Fetching leaderboard data at {datetime.now().strftime('%Y-%m-%dT%H:%M:%S.%f')}..."
    )

    try:
        dynamodb = boto3.resource(
            "dynamodb",
            endpoint_url="http://localhost:8000",
            region_name="us-west-2",
            aws_access_key_id="dummy",
            aws_secret_access_key="dummy",
        )

        table = dynamodb.Table(table_name)

        # Get current leaderboard data with rate limiting
        for game_type in ["battlegrounds", "battlegroundsduo"]:
            print(f"\nFetching {game_type} leaderboards...")
            ratingsDict = getLeaderboardSnapshot(game_type=game_type)

            # Process each region
            for region in ratingsDict:
                print(f"\nProcessing {region} {game_type}...")
                new_entries = 0  # Count new entries for this region

                # Process each player
                for player_name, player_data in ratingsDict[region][game_type].items():
                    # Skip empty player names
                    if not player_name or not player_name.strip():
                        print(f"Skipping empty player name in {region} {game_type}")
                        continue

                    # Create player entry with the correct structure
                    entry = {
                        "name": player_name,
                        "rank": player_data.get("rank"),
                        "rating": player_data.get("rating", player_data.get("MMR", 0)),
                    }

                    # Validate entry data
                    if not entry["rank"] or not entry["rating"]:
                        print(f"Skipping invalid entry data for {player_name}: {entry}")
                        continue

                    # Write the entry
                    if write_leaderboard_entry(table, entry, region, game_type):
                        new_entries += 1

                print(f"Added {new_entries} new entries for {region} {game_type}")

        print("\nUpdate completed successfully")

    except Exception as e:
        print(f"Error during update: {e}")


def check_db_status(table_name="HearthstoneLeaderboard"):
    """Check current database status"""
    dynamodb = boto3.resource(
        "dynamodb",
        endpoint_url="http://localhost:8000",
        region_name="us-west-2",
        aws_access_key_id="dummy",
        aws_secret_access_key="dummy",
    )

    table = dynamodb.Table(table_name)
    response = table.scan()
    items = response["Items"]

    print(f"\nDatabase status:")
    print(f"Total items: {len(items)}")
    if items:
        print(f"Sample entries:")
        for item in items[:5]:
            print(
                f"  {item['player_name']}: Rank {item['rank']}, MMR {item['MMR']}, Region {item['region']}, Game {item['gameType']}"
            )


if __name__ == "__main__":
    # First check DB status
    check_db_status()

    # Then run the update loop
    while True:
        update_leaderboard()
        print("Sleeping for 2 minutes...")
        time.sleep(120)
