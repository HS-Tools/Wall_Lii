#!/usr/bin/env python3
"""
Local test script for the UpdateEntitiesFunction
"""

import os
import sys
from dotenv import load_dotenv

# Add the parent directory to the path to import the lambda function
sys.path.append(os.path.dirname(os.path.abspath(__file__)))

# Load environment variables
load_dotenv()

from lambda_function import lambda_handler, check_recent_news_posts, update_entities


def test_check_recent_news_posts():
    """Test the news posts check function"""
    print("Testing check_recent_news_posts...")
    try:
        has_recent = check_recent_news_posts()
        print(f"Has recent news posts: {has_recent}")
        return True
    except Exception as e:
        print(f"Error testing check_recent_news_posts: {e}")
        return False


def test_update_entities():
    """Test the entity update function"""
    print("Testing update_entities...")
    try:
        total_updated = update_entities()
        print(f"Total entities updated: {total_updated}")
        return True
    except Exception as e:
        print(f"Error testing update_entities: {e}")
        return False


def test_lambda_handler():
    """Test the full lambda handler"""
    print("Testing lambda_handler...")
    try:
        result = lambda_handler({}, None)
        print(f"Lambda result: {result}")
        return True
    except Exception as e:
        print(f"Error testing lambda_handler: {e}")
        return False


if __name__ == "__main__":
    print("Running UpdateEntitiesFunction tests...")
    print("=" * 50)

    # Test individual functions
    test_check_recent_news_posts()
    print()

    # Uncomment the line below to test entity updates (this will make actual API calls)
    # test_update_entities()
    # print()

    # Test full lambda handler
    test_lambda_handler()

    print("=" * 50)
    print("Tests completed!")
