#!/usr/bin/env python3
import argparse
from datetime import datetime
from decimal import Decimal

import boto3


def format_timestamp(ts):
    """Convert epoch to readable time"""
    return datetime.fromtimestamp(int(ts)).strftime("%Y-%m-%d %H:%M:%S")


def show_table_contents(mode=None, server=None, limit=None):
    """Show contents of the DynamoDB table"""
    # Connect to local DynamoDB
    dynamodb = boto3.resource(
        "dynamodb",
        endpoint_url="http://localhost:8000",
        region_name="us-east-1",
        aws_access_key_id="dummy",
        aws_secret_access_key="dummy",
    )

    table = dynamodb.Table("HearthstoneLeaderboard")

    # Build scan parameters
    scan_params = {}
    filter_expressions = []
    expression_values = {}

    if mode:
        filter_expressions.append("GameMode = :mode")
        expression_values[":mode"] = mode

    if server:
        filter_expressions.append("Server = :server")
        expression_values[":server"] = server

    if filter_expressions:
        scan_params["FilterExpression"] = " AND ".join(filter_expressions)
        scan_params["ExpressionAttributeValues"] = expression_values

    if limit:
        scan_params["Limit"] = limit

    # Scan table
    response = table.scan(**scan_params)
    items = response["Items"]

    # Print results
    print(f"\nTable contents ({len(items)} items):")
    print("-" * 100)

    for item in items:
        print(f"\nPlayer: {item['PlayerName']}")
        print(f"Server: {item['Server']}")
        print(f"Game Mode: {'BG' if item['GameMode']=='0' else 'Duos'}")
        print(f"Current Rank: {item['CurrentRank']}")
        print(f"Latest Rating: {item['LatestRating']}")
        print("Rating History:")
        for rating, timestamp in item.get("RatingHistory", []):
            print(f"  {format_timestamp(timestamp)}: {rating}")
        print("-" * 50)


def main():
    parser = argparse.ArgumentParser(description="Show DynamoDB table contents")
    parser.add_argument("--mode", choices=["0", "1"], help="Game mode (0=BG, 1=Duos)")
    parser.add_argument("--server", choices=["NA", "EU", "AP"], help="Server region")
    parser.add_argument("--limit", type=int, help="Maximum number of items to show")
    args = parser.parse_args()

    show_table_contents(mode=args.mode, server=args.server, limit=args.limit)


if __name__ == "__main__":
    main()
