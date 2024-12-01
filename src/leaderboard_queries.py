from collections import defaultdict
from datetime import datetime, timedelta

import boto3

try:
    dynamodb = boto3.resource(
        "dynamodb",
        endpoint_url="http://localhost:8000",
        region_name="us-west-2",
        aws_access_key_id="dummy",
        aws_secret_access_key="dummy",
    )
    print("Debug - Successfully established DynamoDB connection")
except Exception as e:
    print(f"Error establishing DynamoDB connection: {e}")
    raise  # Re-raise the exception to prevent the module from loading with a bad connection


def view_table_contents(table_name="HearthstoneLeaderboard"):
    # Use the global dynamodb connection
    table = dynamodb.Table(table_name)

    # Scan the table
    response = table.scan()
    items = response["Items"]

    # Print each item nicely formatted
    print(f"\nFound {len(items)} items in table '{table_name}':")
    for item in items:
        print("\n-------------------")
        for key, value in item.items():
            print(f"{key}: {value}")


def get_player_stats(
    player_name,
    region=None,
    game_type="battlegrounds",
    table_name="HearthstoneLeaderboard",
):
    """Get current stats for a player. If region is None, returns highest MMR across all regions."""
    print(
        f"Debug - get_player_stats input: player={player_name}, region={region}, game_type={game_type}"
    )

    # Use the global dynamodb connection
    table = dynamodb.Table(table_name)

    # If region is specified, query just that region
    if region:
        player_key = f"{player_name.lower()}#{region}#{game_type}"
        print(f"Debug - Querying with player_key: {player_key}")
        response = table.query(
            KeyConditionExpression="player_key = :pk",
            ExpressionAttributeValues={":pk": player_key},
            ScanIndexForward=False,  # Get most recent first
            Limit=1,
        )
        print(f"Debug - Query response: {response}")

        if not response["Items"]:
            return f"No data found for player {player_name} in {region}"

        item = response["Items"][0]
        return {
            "name": item["player_name"],
            "rank": item["rank"],
            "rating": item["MMR"],
            "region": item["region"],
            "timestamp": item["timestamp"],
        }

    # If no region specified, check all regions
    all_items = []
    for region in ["US", "EU", "AP"]:
        player_key = f"{player_name.lower()}#{region}#{game_type}"
        response = table.query(
            KeyConditionExpression="player_key = :pk",
            ExpressionAttributeValues={":pk": player_key},
            ScanIndexForward=False,  # Get most recent first
            Limit=1,
        )
        if response["Items"]:
            all_items.append(response["Items"][0])  # Already sorted by timestamp

    if not all_items:
        return f"No data found for player {player_name} in any region"

    # Find entry with highest MMR among most recent entries
    highest_mmr_item = max(all_items, key=lambda x: x["MMR"])
    return {
        "name": highest_mmr_item["player_name"],
        "rank": highest_mmr_item["rank"],
        "rating": highest_mmr_item["MMR"],
        "region": highest_mmr_item["region"],
        "timestamp": highest_mmr_item["timestamp"],
    }


def get_player_by_rank(
    rank, region, game_type="battlegrounds", table_name="HearthstoneLeaderboard"
):
    """Get player at a specific rank."""
    print(f"Debug - Looking up rank {rank} in {region} {game_type}")

    try:
        table = dynamodb.Table(table_name)
        region_key = f"{region}#{game_type}"

        # Convert rank to Decimal if it's not already
        if isinstance(rank, str):
            rank = int(rank)

        response = table.query(
            IndexName="RankIndex",
            KeyConditionExpression="region_key = :rk AND #r = :r",
            ExpressionAttributeNames={
                "#r": "rank"  # Use expression attribute name for reserved keyword
            },
            ExpressionAttributeValues={":rk": region_key, ":r": rank},
            ScanIndexForward=False,  # Get most recent first
            Limit=1,
        )

        if not response.get("Items"):
            print(f"Debug - No items found for rank {rank} in {region}")
            return f"No player found at rank {rank} for {region}"

        item = response["Items"][0]
        result = {
            "name": item["player_name"],
            "rank": item["rank"],
            "rating": item["MMR"],
            "region": item["region"],
            "timestamp": item["timestamp"],
        }
        return result

    except Exception as e:
        print(f"Debug - Error in get_player_by_rank: {str(e)}")
        return f"Error looking up rank {rank}: {str(e)}"


def get_player_mmr_changes(
    player_name_or_rank,
    region=None,
    date=None,
    game_type="battlegrounds",
    table_name="HearthstoneLeaderboard",
):
    """Get MMR changes for a player in the last 24 hours."""

    # First determine if this is a rank lookup
    try:
        rank = int(player_name_or_rank)
        if region is None:
            return "Region is required when looking up by rank"
        # Get the player at this rank
        player_result = get_player_by_rank(rank, region, game_type, table_name)
        if isinstance(player_result, str):  # Error message
            return player_result
        player_name = player_result["name"]
    except ValueError:
        # Not a number, treat as player name
        player_name = player_name_or_rank

    print(f"Debug - Getting MMR changes for player: {player_name}")

    # If no region specified, get the player's highest MMR region
    if region is None:
        stats = get_player_stats(player_name)
        if isinstance(stats, str):  # Error message
            return stats
        region = stats["region"]
        print(f"Debug - Using highest MMR region: {region}")

    # Use the global dynamodb connection
    table = dynamodb.Table(table_name)

    # Calculate timestamps for last 24 hours
    now = datetime.now()
    yesterday = now - timedelta(hours=24)

    start_time = yesterday.strftime("%Y-%m-%dT%H:%M:%S.%f")
    end_time = now.strftime("%Y-%m-%dT%H:%M:%S.%f")
    print(f"Debug - Querying between {start_time} and {end_time}")

    # Get all entries for this player/region in last 24 hours
    player_key = f"{player_name.lower()}#{region}#{game_type}"
    response = table.query(
        KeyConditionExpression="player_key = :pk AND #ts BETWEEN :start AND :end",
        ExpressionAttributeNames={"#ts": "timestamp"},
        ExpressionAttributeValues={
            ":pk": player_key,
            ":start": start_time,
            ":end": end_time,
        },
    )

    print(f"Debug - Found {len(response['Items'])} total entries")
    print(f"Debug - Raw entries: {response['Items']}")

    # Filter by last 24 hours - no need for this anymore since we used BETWEEN in query
    recent_items = response["Items"]  # Already filtered by timestamp

    print(f"Debug - Found {len(recent_items)} entries in last 24 hours")
    print(f"Debug - Recent entries: {recent_items}")

    if not recent_items:
        return {
            "name": player_name,
            "region": region,
            "num_games": 0,
            "initial_mmr": 0,
            "final_mmr": 0,
            "net_change": 0,
            "mmr_changes": [],
        }

    # Sort by timestamp
    games = sorted(recent_items, key=lambda x: x["timestamp"])
    print(f"Debug - Sorted games: {games}")

    # Calculate MMR changes
    mmr_changes = []
    for i in range(1, len(games)):
        change = games[i]["MMR"] - games[i - 1]["MMR"]
        if change != 0:  # Only count non-zero changes
            mmr_changes.append(change)
            print(f"Debug - Found MMR change: {change}")

    result = {
        "name": player_name,
        "region": region,
        "num_games": len(mmr_changes),
        "initial_mmr": games[0]["MMR"],
        "final_mmr": games[-1]["MMR"],
        "net_change": games[-1]["MMR"] - games[0]["MMR"],
        "mmr_changes": mmr_changes,
    }
    print(f"Debug - Final result: {result}")
    return result


def format_chat_response(query_type, result):
    """
    Format query results into chat-friendly responses.
    """
    if isinstance(result, str):  # Error message
        return result

    if query_type == "player_stats":
        return (
            f"{result['name']} is currently Rank {result['rank']} "
            f"({result['rating']} MMR) on {result['region']}"
        )

    elif query_type == "rank_lookup":
        return (
            f"Rank {result['rank']} on {result['region']} is "
            f"{result['name']} with {result['rating']} MMR"
        )

    elif query_type == "mmr_changes":
        if result["num_games"] == 0:
            return (
                f"{result['name']} hasn't played any games today on {result['region']}"
            )

        net_change = result["net_change"]
        change_str = f"+{net_change}" if net_change > 0 else str(net_change)

        # Convert Decimal values to strings with proper formatting
        mmr_changes_str = []
        for change in result["mmr_changes"]:
            change_val = int(change)  # Convert Decimal to int
            change_str = f"+{change_val}" if change_val > 0 else str(change_val)
            mmr_changes_str.append(change_str)

        deltas = f"({', '.join(mmr_changes_str)})"

        return (
            f"{result['name']} on {result['region']}: {result['initial_mmr']} → "
            f"{result['final_mmr']} MMR ({change_str}) over {result['num_games']} games {deltas}"
        )

    elif query_type == "weekly_progress":
        if result["start_mmr"] is None:
            return f"No data found for {result['player_name']} in the past week"

        # Determine if end_date is today
        end_date = datetime.strptime(result["end_date"], "%Y-%m-%d")
        today = datetime.now().date()
        days_ago = (
            "today"
            if end_date.date() == today
            else f"{(today - end_date.date()).days} days ago"
        )

        # Format daily changes (including zeros)
        daily_changes = []
        for day in result["daily_progress"]:
            change = day["net_change"]
            change_str = f"+{change}" if change > 0 else str(change)
            daily_changes.append(change_str)

        daily_summary = ", ".join(daily_changes)

        # Format total change
        total_change = result["total_net_change"]
        total_change_str = f"+{total_change}" if total_change > 0 else str(total_change)

        return (
            f"{result['player_name']} on {result['region']} (as of {days_ago}): "
            f"{result['start_mmr']} → {result['end_mmr']} MMR ({total_change_str}) "
            f"[{daily_summary}]"
        )

    elif query_type == "most_active":
        if isinstance(result, str):  # Error message
            return result

        net_change = result["net_change"]
        change_str = f"+{net_change}" if net_change > 0 else str(net_change)
        deltas = f"({', '.join(result['mmr_changes'])})"

        return (
            f"Most active player on {result['region']} {result['game_type']}: "
            f"{result['name']} with {result['num_games']} games. "
            f"MMR {result['initial_mmr']} → {result['final_mmr']} ({change_str}) {deltas}"
        )

    return "Invalid query type"


def get_weekly_progress(
    player_name_or_rank,
    region=None,
    end_date=None,
    game_type="battlegrounds",
    days=7,
    table_name="HearthstoneLeaderboard",
):
    """Get weekly progress for a player."""
    # First determine if this is a rank lookup
    try:
        rank = int(player_name_or_rank)
        if region is None:
            return "Region is required when looking up by rank"
        # Get the player at this rank
        player_result = get_player_by_rank(rank, region, game_type, table_name)
        if isinstance(player_result, str):  # Error message
            return player_result
        player_name = player_result["name"]
    except ValueError:
        # Not a number, treat as player name
        player_name = player_name_or_rank

    # If no region specified, get the player's highest MMR region
    if region is None:
        stats = get_player_stats(player_name)
        if isinstance(stats, str):  # Error message
            return stats
        region = stats["region"]
        print(f"Debug - Using highest MMR region: {region}")

    # Use the global dynamodb connection
    table = dynamodb.Table(table_name)
    player_key = f"{player_name.lower()}#{region}#{game_type}"

    # Calculate date range
    if end_date:
        end_dt = datetime.strptime(end_date, "%Y-%m-%d")
    else:
        end_dt = datetime.now()
    start_dt = end_dt - timedelta(days=days)

    start_time = start_dt.strftime("%Y-%m-%dT%H:%M:%S.%f")
    end_time = end_dt.strftime("%Y-%m-%dT%H:%M:%S.%f")

    # Query all entries in date range
    response = table.query(
        KeyConditionExpression="player_key = :pk AND #ts BETWEEN :start AND :end",
        ExpressionAttributeNames={"#ts": "timestamp"},
        ExpressionAttributeValues={
            ":pk": player_key,
            ":start": start_time,
            ":end": end_time,
        },
    )

    if not response["Items"]:
        return {
            "player_name": player_name,
            "region": region,
            "start_mmr": None,
            "end_mmr": None,
            "total_net_change": 0,
            "daily_progress": [],
            "end_date": end_dt.strftime("%Y-%m-%d"),
        }

    # Group entries by date
    daily_entries = defaultdict(list)
    for item in response["Items"]:
        date = datetime.strptime(item["timestamp"], "%Y-%m-%dT%H:%M:%S.%f").date()
        daily_entries[date].append(item)

    # Calculate daily progress
    daily_progress = []
    current_date = start_dt.date()  # Convert to date for comparison
    start_mmr = None
    end_mmr = None

    while current_date <= end_dt.date():  # Compare dates not datetimes
        if current_date in daily_entries:
            day_games = sorted(
                daily_entries[current_date],
                key=lambda x: x["timestamp"],  # Use timestamp
            )
            day_start_mmr = day_games[0]["MMR"]
            day_end_mmr = day_games[-1]["MMR"]
            net_change = day_end_mmr - day_start_mmr

            if start_mmr is None:
                start_mmr = day_start_mmr
            end_mmr = day_end_mmr
        else:
            net_change = 0

        daily_progress.append(
            {"date": current_date.strftime("%Y-%m-%d"), "net_change": net_change}
        )
        current_date += timedelta(days=1)

    if start_mmr is None:  # No data found
        start_mmr = 0
        end_mmr = 0

    return {
        "player_name": player_name,
        "region": region,
        "start_mmr": start_mmr,
        "end_mmr": end_mmr,
        "total_net_change": end_mmr - start_mmr if end_mmr and start_mmr else 0,
        "daily_progress": daily_progress,
        "end_date": end_dt.strftime("%Y-%m-%d"),
    }


def get_player_mmr_changes_by_rank(
    rank,
    region,
    date=None,
    game_type="battlegrounds",
    table_name="HearthstoneLeaderboard",
):
    """
    Get MMR changes for the player at a specific rank.

    Args:
        rank (int): Rank to look up (1-200)
        region (str): Region/server (US, EU, AP)
        date (str): Date to check in format 'YYYY-MM-DD' (defaults to today)
        game_type (str): Either "battlegrounds" or "battlegroundsduo"
        table_name (str): DynamoDB table name

    Returns:
        dict: Contains initial_mmr, final_mmr, changes list, and net change
        str: Error message if rank not found
    """
    # First get the player at this rank
    player_result = get_player_by_rank(rank, region, game_type, table_name)
    if isinstance(player_result, str):  # Error message
        return player_result

    # Now get their MMR changes
    return get_player_mmr_changes(
        player_result["name"], region, date, game_type, table_name
    )


def get_weekly_progress_by_rank(
    rank,
    region,
    end_date=None,
    game_type="battlegrounds",
    days=7,
    table_name="HearthstoneLeaderboard",
):
    """
    Get weekly progress for the player at a specific rank.

    Args:
        rank (int): Rank to look up (1-200)
        region (str): Region/server (US, EU, AP)
        end_date (str): End date in format 'YYYY-MM-DD' (defaults to today)
        game_type (str): Either "battlegrounds" or "battlegroundsduo"
        days (int): Number of days to look back (default 7)
        table_name (str): DynamoDB table name

    Returns:
        dict: Contains daily_progress, start_mmr, end_mmr, and net_change
        str: Error message if rank not found
    """
    # First get the player at this rank
    player_result = get_player_by_rank(rank, region, game_type, table_name)
    if isinstance(player_result, str):  # Error message
        return player_result

    # Now get their weekly progress
    return get_weekly_progress(
        player_result["name"], region, end_date, game_type, days, table_name
    )


def get_most_active_player(
    region, game_type="battlegrounds", table_name="HearthstoneLeaderboard"
):
    """Get the most active player in the last 24 hours."""
    # Use the global dynamodb connection
    table = dynamodb.Table(table_name)
    region_key = f"{region}#{game_type}"

    # Get all entries for this region/game_type in last 24 hours
    now = datetime.now()
    yesterday = now - timedelta(hours=24)
    start_time = yesterday.strftime("%Y-%m-%dT%H:%M:%S.%f")
    end_time = now.strftime("%Y-%m-%dT%H:%M:%S.%f")

    # Query using RankIndex to get all players
    response = table.query(
        IndexName="RankIndex",
        KeyConditionExpression="region_key = :rk",
        FilterExpression="#ts BETWEEN :start AND :end",
        ExpressionAttributeNames={"#ts": "timestamp"},
        ExpressionAttributeValues={
            ":rk": region_key,
            ":start": start_time,
            ":end": end_time,
        },
    )

    if not response["Items"]:
        return f"No games found in the last 24 hours for {region} {game_type}"

    print(f"Found {len(response['Items'])} total entries")

    # Group entries by player
    player_games = defaultdict(list)
    for item in response["Items"]:
        player_games[item["player_name"]].append(item)

    print(f"Found {len(player_games)} unique players")

    # Process each player's games and count actual MMR changes
    player_real_games = {}
    for player_name, games in player_games.items():
        # Sort by timestamp
        sorted_games = sorted(games, key=lambda x: x["timestamp"])
        mmr_changes = []

        # Look for actual MMR changes
        for i in range(1, len(sorted_games)):
            mmr_diff = sorted_games[i]["MMR"] - sorted_games[i - 1]["MMR"]
            time_diff = datetime.strptime(
                sorted_games[i]["timestamp"], "%Y-%m-%dT%H:%M:%S.%f"
            ) - datetime.strptime(
                sorted_games[i - 1]["timestamp"], "%Y-%m-%dT%H:%M:%S.%f"
            )

            # Only count as a game if:
            # 1. MMR changed
            # 2. At least 5 minutes between entries
            # 3. MMR change is reasonable (e.g., between -300 and +300)
            if (
                abs(mmr_diff) > 0
                and time_diff >= timedelta(minutes=5)
                and abs(mmr_diff) <= 300
            ):
                mmr_changes.append(mmr_diff)

        if mmr_changes:  # Only include players with actual MMR changes
            player_real_games[player_name] = {
                "games": sorted_games,
                "mmr_changes": mmr_changes,
                "num_games": len(mmr_changes),
            }

    if not player_real_games:
        return f"No games with MMR changes found in the last 24 hours for {region} {game_type}"

    # Find player with most actual games
    most_active_player = max(player_real_games.items(), key=lambda x: x[1]["num_games"])
    player_name = most_active_player[0]
    games_data = most_active_player[1]

    # Format MMR changes
    mmr_changes = [
        f"+{change}" if change > 0 else str(change)
        for change in games_data["mmr_changes"]
    ]
    all_games = games_data["games"]

    return {
        "name": player_name,
        "region": region,
        "game_type": game_type,
        "num_games": len(mmr_changes),
        "initial_mmr": all_games[0]["MMR"],
        "final_mmr": all_games[-1]["MMR"],
        "net_change": all_games[-1]["MMR"] - all_games[0]["MMR"],
        "mmr_changes": mmr_changes,
    }


def debug_print_all_items(table_name="HearthstoneLeaderboard"):
    """Print all items in the table for debugging"""
    # Use the global dynamodb connection
    table = dynamodb.Table(table_name)
    response = table.scan()
    items = response["Items"]

    print("\nAll items in table:")
    print(f"Found {len(items)} items")
    for item in items:
        print(f"\nplayer_key: {item['player_key']}")
        print(f"timestamp: {item['timestamp']}")
        print(f"player_name: {item['player_name']}")
        print(f"region: {item['region']}")
        print(f"rank: {item['rank']}")
        print(f"MMR: {item['MMR']}")


def debug_print_player_entries(player_name, table_name="HearthstoneLeaderboard"):
    """Print all entries for a specific player"""
    # Use the global dynamodb connection
    table = dynamodb.Table(table_name)

    # Query each region/game_type combination
    regions = ["US", "EU", "AP"]
    game_types = ["battlegrounds", "battlegroundsduo"]

    all_items = []
    for region in regions:
        for game_type in game_types:
            player_key = f"{player_name.lower()}#{region}#{game_type}"
            response = table.query(
                KeyConditionExpression="player_key = :pk",
                ExpressionAttributeValues={":pk": player_key},
            )
            all_items.extend(response["Items"])

    print(f"\nFound {len(all_items)} entries for player {player_name}:")
    for item in all_items:
        print("\n-------------------")
        print(f"timestamp: {item['timestamp']}")
        print(f"region: {item['region']}")
        print(f"rank: {item['rank']}")
        print(f"MMR: {item['MMR']}")


def debug_print_table_indexes(table_name="HearthstoneLeaderboard"):
    table = dynamodb.Table(table_name)
    print("\nTable Indexes:")
    for index in table.global_secondary_indexes:
        print(f"Index Name: {index['IndexName']}")
        print(f"Key Schema: {index['KeySchema']}")


if __name__ == "__main__":
    debug_print_table_indexes()
    debug_print_player_entries("shadybunny")
