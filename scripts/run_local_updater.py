#!/usr/bin/env python3
import os
import sys
import time
from datetime import datetime

# Add lambda-loader/src to Python path
sys.path.append(os.path.join(os.path.dirname(__file__), "..", "lambda-loader", "src"))

# Set environment variables for local testing
os.environ["DYNAMODB_ENDPOINT_URL"] = "http://localhost:8000"
os.environ["TABLE_NAME"] = "HearthstoneLeaderboard"

from dbUpdater import lambda_handler  # Updated import name


def main():
    while True:
        print(f"\nRunning update at {datetime.now()}")
        lambda_handler({}, None)
        time.sleep(120)  # Wait 2 minutes


if __name__ == "__main__":
    main()
