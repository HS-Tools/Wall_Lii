import os

import boto3
from dotenv import load_dotenv


def test_aws_connection():
    load_dotenv()

    # List of common AWS regions to check
    regions = [
        "us-west-2",  # Oregon
        "us-east-1",  # N. Virginia
        "us-east-2",  # Ohio
        "us-west-1",  # N. California
        "eu-west-1",  # Ireland
    ]

    for region in regions:
        print(f"\nChecking region: {region}")
        try:
            dynamodb = boto3.resource(
                "dynamodb",
                region_name=region,
                aws_access_key_id=os.getenv("AWS_ACCESS_KEY_ID"),
                aws_secret_access_key=os.getenv("AWS_SECRET_ACCESS_KEY"),
            )

            # List all tables
            client = dynamodb.meta.client
            tables = client.list_tables()
            if tables["TableNames"]:
                print("Found tables:")
                for table in tables["TableNames"]:
                    print(f"- {table}")
            else:
                print("No tables found in this region")

        except Exception as e:
            print(f"Error checking {region}: {e}")


if __name__ == "__main__":
    test_aws_connection()
