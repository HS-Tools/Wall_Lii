from datetime import datetime

import boto3


def update_leaderboard_data_local(table_name, leaderboard_data, season_id):
    """
    Updates the local DynamoDB table with leaderboard data.
    Writes new entries only if the MMR is different from the last recorded value.

    Args:
        table_name (str): Name of the DynamoDB table.
        leaderboard_data (dict): Data fetched from the leaderboard API.
        season_id (int): Current season ID.
    """
    # Connect to DynamoDB Local
    dynamodb = boto3.resource("dynamodb", endpoint_url="http://localhost:8000")
    table = dynamodb.Table(table_name)

    # Process leaderboard data
    for region, game_modes in leaderboard_data.items():
        for game_mode, players in game_modes.items():
            for player_name, player_data in players.items():
                # Construct primary and sort keys
                pk = f"player#{player_name}#{region}"
                sk = (
                    f"{datetime.now().strftime('%Y-%m-%dT%H:%M')}#{player_data['rank']}"
                )

                # Query the latest record for the player
                response = table.query(
                    KeyConditionExpression="PK = :pk",
                    ExpressionAttributeValues={":pk": pk},
                    ScanIndexForward=False,  # Descending order
                    Limit=1,
                )

                # Check if the MMR has changed
                if response["Count"] > 0:
                    latest_mmr = response["Items"][0]["MMR"]
                    if latest_mmr == player_data["rating"]:
                        # print(f"Skipping {player_name} in {region}: MMR unchanged.")
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

                # Insert or update the record
                table.put_item(Item=item)
                print(
                    f"Updated {player_name} in {region} with new MMR: {player_data['rating']}."
                )

    print("Leaderboard data update completed.")


# Example usage:
if __name__ == "__main__":
    # Example leaderboard data (replace with actual fetch logic)
    leaderboard_data = {}
    season_id = 13
    update_leaderboard_data_local("HearthstoneLeaderboard", leaderboard_data, season_id)
