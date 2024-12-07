#!/usr/bin/env python3
import json
import os
import sys
from datetime import datetime
from decimal import Decimal

import boto3

# Add src directory to Python path
sys.path.append(os.path.join(os.path.dirname(__file__), "..", "src"))


def format_timestamp(ts):
    """Convert epoch to readable time"""
    return datetime.fromtimestamp(int(ts)).strftime("%Y-%m-%d %H:%M:%S")


def show_top_players(region="NA", game_mode="0", limit=25):
    """Show top players for a given region and game mode"""
    # Set up DynamoDB
    dynamodb = boto3.resource(
        "dynamodb",
        endpoint_url="http://localhost:8000",
        region_name="us-east-1",
        aws_access_key_id="dummy",
        aws_secret_access_key="dummy",
    )

    table = dynamodb.Table("HearthstoneLeaderboard")

    # Query using RankLookupIndex
    game_mode_server = f"{game_mode}#{region}"
    response = table.query(
        IndexName="RankLookupIndex",
        KeyConditionExpression="GameModeServer = :gms",
        ExpressionAttributeValues={":gms": game_mode_server},
    )

    # Group by player name and keep latest entry
    player_data = {}
    for item in response["Items"]:
        player_name = item["PlayerName"]
        if player_name not in player_data or int(item["CurrentRank"]) < int(
            player_data[player_name]["CurrentRank"]
        ):
            player_data[player_name] = item

    # Sort by rank and take top N
    sorted_items = sorted(player_data.values(), key=lambda x: int(x["CurrentRank"]))[
        :limit
    ]

    # Print results
    print(
        f"\nTop {limit} players in {region} (Game Mode: {'BG' if game_mode=='0' else 'Duos'}):"
    )
    print("-" * 80)
    print(f"{'Rank':<6} {'Player':<20} {'Rating':<8} {'History'}")
    print("-" * 80)

    for item in sorted_items:
        rank = item["CurrentRank"]
        name = item["PlayerName"]
        rating = item["LatestRating"]
        history = item.get("RatingHistory", [])

        # Format history
        if history:
            history_str = " → ".join([str(h[0]) for h in history])
            if len(history) > 1:
                change = int(history[-1][0]) - int(history[0][0])
                change_str = f" ({'+' if change > 0 else ''}{change})"
                history_str += change_str
        else:
            history_str = "No history"

        print(f"{rank:<6} {name:<20} {rating:<8} {history_str}")


if __name__ == "__main__":
    show_top_players()
