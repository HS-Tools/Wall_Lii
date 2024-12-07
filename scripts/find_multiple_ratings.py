import json
from datetime import datetime

import boto3


def get_dynamodb():
    return boto3.resource(
        "dynamodb",
        endpoint_url="http://localhost:8000",
        region_name="us-east-1",
        aws_access_key_id="dummy",
        aws_secret_access_key="dummy",
    )


def find_multiple_ratings():
    ddb = get_dynamodb()
    table = ddb.Table("HearthstoneLeaderboard")

    response = table.scan(
        FilterExpression="size(RatingHistory) > :val",
        ExpressionAttributeValues={":val": 1},
        ProjectionExpression="PlayerName, GameModeServerPlayer, RatingHistory",
    )

    for item in response["Items"]:
        history = [
            {
                "rating": int(entry[0]),
                "timestamp": datetime.fromtimestamp(int(entry[1])).strftime(
                    "%Y-%m-%d %H:%M:%S"
                ),
            }
            for entry in item["RatingHistory"]
        ]

        print(
            json.dumps(
                {
                    "player": item["PlayerName"],
                    "key": item["GameModeServerPlayer"],
                    "history": history,
                },
                indent=2,
            )
        )


if __name__ == "__main__":
    find_multiple_ratings()
