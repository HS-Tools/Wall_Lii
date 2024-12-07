#!/usr/bin/env python3
import argparse
import os
import sys
import time

import boto3


def create_table(dynamodb):
    """Create the HearthstoneLeaderboard table"""
    table = dynamodb.create_table(
        TableName="HearthstoneLeaderboard",
        KeySchema=[{"AttributeName": "GameModeServerPlayer", "KeyType": "HASH"}],
        AttributeDefinitions=[
            {"AttributeName": "GameModeServerPlayer", "AttributeType": "S"},
            {"AttributeName": "GameModeServer", "AttributeType": "S"},
            {"AttributeName": "CurrentRank", "AttributeType": "N"},
        ],
        GlobalSecondaryIndexes=[
            {
                "IndexName": "RankLookupIndex",
                "KeySchema": [
                    {"AttributeName": "GameModeServer", "KeyType": "HASH"},
                    {"AttributeName": "CurrentRank", "KeyType": "RANGE"},
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
    return table


def delete_table(dynamodb):
    """Delete the HearthstoneLeaderboard table"""
    table = dynamodb.Table("HearthstoneLeaderboard")
    table.delete()


def main():
    parser = argparse.ArgumentParser(description="Manage local DynamoDB table")
    parser.add_argument(
        "action",
        choices=["create", "delete", "recreate"],
        help="Action to perform on the table",
    )
    args = parser.parse_args()

    # Connect to local DynamoDB
    dynamodb = boto3.resource(
        "dynamodb",
        endpoint_url="http://localhost:8000",
        region_name="us-east-1",
        aws_access_key_id="dummy",
        aws_secret_access_key="dummy",
    )

    try:
        if args.action == "delete" or args.action == "recreate":
            print("Deleting table...")
            delete_table(dynamodb)
            print("Table deleted.")
            if args.action == "delete":
                return

        if args.action == "create" or args.action == "recreate":
            print("Creating table...")
            table = create_table(dynamodb)
            print("Waiting for table to be ready...")
            table.wait_until_exists()
            print("Table created successfully.")

    except Exception as e:
        print(f"Error: {str(e)}")
        sys.exit(1)


if __name__ == "__main__":
    main()
