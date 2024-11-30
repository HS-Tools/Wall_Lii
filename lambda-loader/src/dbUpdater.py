import time
from datetime import datetime, timedelta

import boto3
from api import getLeaderboardSnapshot


def get_latest_timestamp(table, region, game_type):
    """
    Get the timestamp of the most recent entry for a given region and game type.
    """
    try:
        # Get the current timestamp for the sort key
        current_time = datetime.now().strftime("%Y-%m-%dT%H:%M:%S.%f")

        response = table.query(
            KeyConditionExpression="partition_key = :pk AND sort_key <= :sk",
            ExpressionAttributeValues={
                ":pk": f"{region}#{game_type}",
                ":sk": f"999#{current_time}",
            },
            ScanIndexForward=False,  # Get most recent first
            Limit=1,
        )

        if response["Items"]:
            return response["Items"][0]["lastUpdated"]
        return None

    except Exception as e:
        print(f"Error getting latest timestamp: {e}")
        return None


def write_leaderboard_entry(table, player_data, region, game_type):
    """
    Write a single leaderboard entry to DynamoDB.
    """
    # Validate player data
    if (
        not player_data.get("name")
        or not player_data.get("rank")
        or not player_data.get("rating")
    ):
        print(f"Skipping invalid player data: {player_data}")
        return

    timestamp = datetime.now().strftime("%Y-%m-%dT%H:%M:%S.%f")
    rank_padded = str(player_data["rank"]).zfill(
        3
    )  # Pad rank with zeros for proper sorting

    # Ensure player name is valid for DynamoDB
    player_name = player_data["name"].lower().strip()
    if not player_name:
        print(f"Skipping empty player name: {player_data}")
        return

    item = {
        "partition_key": f"{region}#{game_type}",
        "sort_key": f"{rank_padded}#{timestamp}",
        "player_name": player_name,
        "rank": player_data["rank"],
        "MMR": player_data["rating"],
        "region": region,
        "gameType": game_type,
        "lastUpdated": timestamp,
    }

    try:
        table.put_item(Item=item)
        print(
            f"New entry: {player_name} (Rank {player_data['rank']}) - {player_data['rating']} MMR on {region}"
        )
    except Exception as e:
        print(f"Error writing entry for {player_data.get('name', 'unknown')}: {e}")
        print(f"Attempted to write item: {item}")


def update_leaderboard(table_name="HearthstoneLeaderboard"):
    """
    Update the leaderboard data in DynamoDB.
    """
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
                latest_timestamp = get_latest_timestamp(table, region, game_type)

                # Count new entries for this region
                new_entries = 0

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

                    # Only write if this is new data
                    if latest_timestamp is None:
                        write_leaderboard_entry(table, entry, region, game_type)
                        new_entries += 1
                    else:
                        try:
                            # Check if player's MMR has changed in this region
                            response = table.query(
                                IndexName="PlayerNameIndex",
                                KeyConditionExpression="player_name = :name",
                                FilterExpression="#region = :region",
                                ExpressionAttributeNames={"#region": "region"},
                                ExpressionAttributeValues={
                                    ":name": player_name.lower().strip(),
                                    ":region": region,
                                },
                                ScanIndexForward=False,  # Get most recent first
                                Limit=1,
                            )

                            should_write = True
                            if response["Items"]:
                                last_entry = response["Items"][0]
                                if (
                                    last_entry["MMR"] == entry["rating"]
                                    and last_entry["region"] == region
                                ):
                                    should_write = False

                            if should_write:
                                write_leaderboard_entry(table, entry, region, game_type)
                                new_entries += 1

                        except Exception as e:
                            print(f"Error processing player {player_name}: {e}")
                            continue

                print(f"Added {new_entries} new entries for {region} {game_type}")

        print("\nUpdate completed successfully")

    except Exception as e:
        print(f"Error during update: {e}")


if __name__ == "__main__":
    while True:
        update_leaderboard()
        print("Sleeping for 2 minutes...")
        time.sleep(120)  # Sleep for 2 minutes before next update
