#!/usr/bin/env python3
import os
import sys
import time
import argparse
from datetime import datetime

# Add lambda-loader/src to Python path
sys.path.append(os.path.join(os.path.dirname(__file__), "..", "lambda-loader", "src"))

# Set environment variables for local testing
os.environ["DYNAMODB_ENDPOINT_URL"] = "http://localhost:8000"
os.environ["TABLE_NAME"] = "HearthstoneLeaderboardTest"

from dbUpdater import lambda_handler


def main(once=False):
    """Run the updater, optionally just once"""
    print(f"\nRunning update at {datetime.now()}")
    lambda_handler({}, None)
    
    if not once:
        while True:
            time.sleep(120)  # Wait 2 minutes
            print(f"\nRunning update at {datetime.now()}")
            lambda_handler({}, None)


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description='Run local DynamoDB updater')
    parser.add_argument('--once', action='store_true', help='Run once and exit')
    args = parser.parse_args()
    main(once=args.once)
