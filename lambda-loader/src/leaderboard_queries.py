from collections import defaultdict
from datetime import datetime, timedelta

import boto3


def view_table_contents(table_name="HearthstoneLeaderboard"):
    # Create a DynamoDB client for local instance
    dynamodb = boto3.resource(
        "dynamodb",
        endpoint_url="http://localhost:8000",
        region_name="us-west-2",
        aws_access_key_id="dummy",
        aws_secret_access_key="dummy",
    )

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
    player_name, region, game_type="battlegrounds", table_name="HearthstoneLeaderboard"
):
    """
    Get current stats for a player.
    """
    dynamodb = boto3.resource(
        "dynamodb",
        endpoint_url="http://localhost:8000",
        region_name="us-west-2",
        aws_access_key_id="dummy",
        aws_secret_access_key="dummy",
    )

    table = dynamodb.Table(table_name)

    # Query using the PlayerNameIndex
    response = table.query(
        IndexName="PlayerNameIndex",
        KeyConditionExpression="player_name = :name",
        ExpressionAttributeValues={":name": player_name},
        ScanIndexForward=False,  # Get most recent first
        Limit=1,
    )

    if not response["Items"]:
        return f"No data found for player {player_name}"

    item = response["Items"][0]
    return {
        "name": item["player_name"],
        "rank": item["rank"],
        "rating": item["MMR"],
        "region": item["region"],
        "timestamp": item["lastUpdated"],
    }


def get_player_by_rank(
    rank, region, game_type="battlegrounds", table_name="HearthstoneLeaderboard"
):
    """
    Get player at a specific rank.
    """
    dynamodb = boto3.resource(
        "dynamodb",
        endpoint_url="http://localhost:8000",
        region_name="us-west-2",
        aws_access_key_id="dummy",
        aws_secret_access_key="dummy",
    )

    table = dynamodb.Table(table_name)
    rank_padded = str(rank).zfill(3)

    # Query the latest entry for this rank
    response = table.query(
        KeyConditionExpression="partition_key = :pk AND begins_with(sort_key, :rank)",
        ExpressionAttributeValues={
            ":pk": f"{region}#{game_type}",
            ":rank": rank_padded,
        },
        ScanIndexForward=False,  # Get most recent first
        Limit=1,
    )

    if not response["Items"]:
        return f"No player found at rank {rank} for {region}"

    item = response["Items"][0]
    return {
        "name": item["player_name"],
        "rank": item["rank"],
        "rating": item["MMR"],
        "region": item["region"],
        "timestamp": item["lastUpdated"],
    }


def get_player_mmr_changes(
    player_name,
    region,
    date=None,
    game_type="battlegrounds",
    table_name="HearthstoneLeaderboard",
):
    """
    Get MMR changes for a player on a specific date.
    """
    dynamodb = boto3.resource(
        "dynamodb",
        endpoint_url="http://localhost:8000",
        region_name="us-west-2",
        aws_access_key_id="dummy",
        aws_secret_access_key="dummy",
    )

    table = dynamodb.Table(table_name)

    # If no date specified, use today
    if date is None:
        date = datetime.now().strftime("%Y-%m-%d")

    start_time = f"{date}T00:00:00"
    end_time = f"{date}T23:59:59"

    # Query using the PlayerNameIndex
    response = table.query(
        IndexName="PlayerNameIndex",
        KeyConditionExpression="player_name = :name AND sort_key BETWEEN :start AND :end",
        FilterExpression="#region = :region",
        ExpressionAttributeNames={
            "#region": "region"  # 'region' is a reserved word in DynamoDB
        },
        ExpressionAttributeValues={
            ":name": player_name,
            ":region": region,
            ":start": f"000#{start_time}",
            ":end": f"999#{end_time}",
        },
    )

    if not response["Items"]:
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
    games = sorted(response["Items"], key=lambda x: x["lastUpdated"])

    # Calculate MMR changes
    mmr_changes = []
    for i in range(1, len(games)):
        change = games[i]["MMR"] - games[i - 1]["MMR"]
        if change != 0:  # Only count non-zero changes
            mmr_changes.append(change)

    return {
        "name": player_name,
        "region": region,
        "num_games": len(mmr_changes),
        "initial_mmr": games[0]["MMR"],
        "final_mmr": games[-1]["MMR"],
        "net_change": games[-1]["MMR"] - games[0]["MMR"],
        "mmr_changes": mmr_changes,
    }


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
    player_name,
    region,
    end_date=None,
    game_type="battlegrounds",
    days=7,
    table_name="HearthstoneLeaderboard",
):
    """
    Get player's MMR progress over the last week or specified period.
    """
    dynamodb = boto3.resource(
        "dynamodb",
        endpoint_url="http://localhost:8000",
        region_name="us-west-2",
        aws_access_key_id="dummy",
        aws_secret_access_key="dummy",
    )

    table = dynamodb.Table(table_name)

    # Calculate date range
    if end_date is None:
        end_date = datetime.now().date()
    else:
        end_date = datetime.strptime(end_date, "%Y-%m-%d").date()

    start_date = end_date - timedelta(days=days - 1)

    # Query using the PlayerNameIndex
    response = table.query(
        IndexName="PlayerNameIndex",
        KeyConditionExpression="player_name = :name AND sort_key BETWEEN :start AND :end",
        FilterExpression="#region = :region",
        ExpressionAttributeNames={
            "#region": "region"  # 'region' is a reserved word in DynamoDB
        },
        ExpressionAttributeValues={
            ":name": player_name,
            ":region": region,
            ":start": f"000#{start_date.strftime('%Y-%m-%d')}T00:00:00",
            ":end": f"999#{end_date.strftime('%Y-%m-%d')}T23:59:59",
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
            "end_date": end_date.strftime("%Y-%m-%d"),
        }

    # Group entries by date
    daily_entries = defaultdict(list)
    for item in response["Items"]:
        date = datetime.strptime(item["lastUpdated"], "%Y-%m-%dT%H:%M:%S.%f").date()
        daily_entries[date].append(item)

    # Calculate daily progress
    daily_progress = []
    current_date = start_date
    start_mmr = None
    end_mmr = None

    while current_date <= end_date:
        if current_date in daily_entries:
            day_games = sorted(
                daily_entries[current_date], key=lambda x: x["lastUpdated"]
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
        "end_date": end_date.strftime("%Y-%m-%d"),
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
    """
    Find the player with the most games played in the last 24 hours.
    """
    dynamodb = boto3.resource(
        "dynamodb",
        endpoint_url="http://localhost:8000",
        region_name="us-west-2",
        aws_access_key_id="dummy",
        aws_secret_access_key="dummy",
    )

    table = dynamodb.Table(table_name)
    player_games = defaultdict(list)

    # Calculate timestamp for 24 hours ago
    now = datetime.now()
    yesterday = now - timedelta(days=1)

    print(f"\nQuerying {region} {game_type} from {yesterday} to {now}")

    # Query for all entries in the last 24 hours for this region and game type
    response = table.query(
        KeyConditionExpression="partition_key = :pk AND sort_key BETWEEN :start AND :end",
        ExpressionAttributeValues={
            ":pk": f"{region}#{game_type}",
            ":start": f"000#{yesterday.strftime('%Y-%m-%dT%H:%M:%S')}",
            ":end": f"999#{now.strftime('%Y-%m-%dT%H:%M:%S')}",
        },
    )

    if not response["Items"]:
        return f"No games found in the last 24 hours for {region} {game_type}"

    print(f"Found {len(response['Items'])} total entries")

    # Group entries by player
    for item in response["Items"]:
        player_games[item["player_name"]].append(item)

    print(f"Found {len(player_games)} unique players")

    # Process each player's games and count actual MMR changes
    player_real_games = {}
    for player_name, games in player_games.items():
        # Sort by lastUpdated
        sorted_games = sorted(games, key=lambda x: x["lastUpdated"])
        mmr_changes = []

        # Look for actual MMR changes
        for i in range(1, len(sorted_games)):
            mmr_diff = sorted_games[i]["MMR"] - sorted_games[i - 1]["MMR"]
            time_diff = datetime.strptime(
                sorted_games[i]["lastUpdated"], "%Y-%m-%dT%H:%M:%S.%f"
            ) - datetime.strptime(
                sorted_games[i - 1]["lastUpdated"], "%Y-%m-%dT%H:%M:%S.%f"
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


if __name__ == "__main__":
    # Example usage:
    player_name = "jeef"
    server = "US"
    rank = 1

    print("\n=== Player Stats Examples ===")
    # By player name
    result = get_player_stats(player_name, server, game_type="battlegrounds")
    print("\nRegular Battlegrounds Stats (by name):")
    print("---------------------------")
    if isinstance(result, dict):
        for key, value in result.items():
            print(f"{key}: {value}")
    else:
        print(result)

    # By rank
    rank_result = get_player_by_rank(rank, server, game_type="battlegrounds")
    print("\nRegular Battlegrounds Stats (by rank):")
    print("---------------------------")
    if isinstance(rank_result, dict):
        for key, value in rank_result.items():
            print(f"{key}: {value}")
    else:
        print(rank_result)

    print("\n=== Daily MMR Changes Examples ===")
    # By player name
    mmr_result = get_player_mmr_changes(player_name, server)
    print("\nMMR Changes (by name):")
    print(format_chat_response("mmr_changes", mmr_result))

    # By rank
    rank_mmr_result = get_player_mmr_changes_by_rank(rank, server)
    print("\nMMR Changes (by rank):")
    print(format_chat_response("mmr_changes", rank_mmr_result))

    print("\n=== Weekly Progress Examples ===")
    # By player name (default to last 7 days)
    weekly_result = get_weekly_progress(player_name, server)
    print("\nWeekly Progress (by name, default date range):")
    print(format_chat_response("weekly_progress", weekly_result))

    # By rank (default to last 7 days)
    rank_weekly_result = get_weekly_progress_by_rank(rank, server)
    print("\nWeekly Progress (by rank, default date range):")
    print(format_chat_response("weekly_progress", rank_weekly_result))

    # By player name (specific end date)
    weekly_result = get_weekly_progress(player_name, server, end_date="2024-11-30")
    print("\nWeekly Progress (by name, specific date):")
    print(format_chat_response("weekly_progress", weekly_result))

    # By rank (specific end date)
    rank_weekly_result = get_weekly_progress_by_rank(
        rank, server, end_date="2024-11-30"
    )
    print("\nWeekly Progress (by rank, specific date):")
    print(format_chat_response("weekly_progress", rank_weekly_result))

    print("\n=== Different Game Types ===")
    # Example with Duo Queue
    duo_result = get_player_stats(player_name, server, game_type="battlegroundsduo")
    print("\nDuo Queue Stats:")
    print(format_chat_response("player_stats", duo_result))

    # Example with different regions
    eu_result = get_player_by_rank(1, "EU", game_type="battlegrounds")
    print("\nEU Region Example:")
    print(format_chat_response("rank_lookup", eu_result))

    print("\n=== Most Active Player Examples ===")
    # Check most active players across all regions in regular BGs
    for region in ["US", "EU", "AP"]:
        active_result = get_most_active_player(region, "battlegrounds")
        print(f"\nMost Active Player ({region}):")
        print(format_chat_response("most_active", active_result))
