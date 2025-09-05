#!/usr/bin/env python3
"""
Test file for common Twitch bot queries using live database.
Run this to manually evaluate the responses from the migrated code.
"""

import sys
import os

# Add the src directory to the path
sys.path.append(os.path.join(os.path.dirname(__file__), "..", "src"))

from leaderboard import LeaderboardDB


def test_rank_queries():
    """Test rank-based queries"""
    print("=== RANK QUERIES ===")

    # Test rank 1 (should work with new structure)
    print("\n1. !rank 1")
    try:
        result = db.rank("1")
        print(f"Result: {result}")
    except Exception as e:
        print(f"Error: {e}")

    # Test rank 1 with region
    print("\n2. !rank 1 NA")
    try:
        result = db.rank("1", "NA")
        print(f"Result: {result}")
    except Exception as e:
        print(f"Error: {e}")

    # Test rank 1000
    print("\n3. !rank 1000")
    try:
        result = db.rank("1000")
        print(f"Result: {result}")
    except Exception as e:
        print(f"Error: {e}")

    # Test rank 1001 (should use current_leaderboard)
    print("\n4. !rank 1001")
    try:
        result = db.rank("1001")
        print(f"Result: {result}")
    except Exception as e:
        print(f"Error: {e}")


def test_name_queries():
    """Test name-based queries"""
    print("\n=== NAME QUERIES ===")

    # Test player name lookup
    print("\n1. !rank beter")
    try:
        result = db.rank("beter")
        print(f"Result: {result}")
    except Exception as e:
        print(f"Error: {e}")

    # Test player name with region
    print("\n2. !rank beter NA")
    try:
        result = db.rank("beter", "NA")
        print(f"Result: {result}")
    except Exception as e:
        print(f"Error: {e}")

    # Test another player
    print("\n3. !rank lii")
    try:
        result = db.rank("lii")
        print(f"Result: {result}")
    except Exception as e:
        print(f"Error: {e}")


def test_top10_queries():
    """Test top10 queries"""
    print("\n=== TOP 10 QUERIES ===")

    # Test global top 10
    print("\n1. !top10")
    try:
        result = db.top10()
        print(f"Result: {result}")
    except Exception as e:
        print(f"Error: {e}")

    # Test NA top 10
    print("\n2. !top10 NA")
    try:
        result = db.top10("NA")
        print(f"Result: {result}")
    except Exception as e:
        print(f"Error: {e}")

    # Test EU top 10
    print("\n3. !top10 EU")
    try:
        result = db.top10("EU")
        print(f"Result: {result}")
    except Exception as e:
        print(f"Error: {e}")


def test_peak_queries():
    """Test peak queries"""
    print("\n=== PEAK QUERIES ===")

    # Test peak for a player
    print("\n1. !peak beter")
    try:
        result = db.peak("beter")
        print(f"Result: {result}")
    except Exception as e:
        print(f"Error: {e}")

    # Test peak with region
    print("\n2. !peak beter NA")
    try:
        result = db.peak("beter", "NA")
        print(f"Result: {result}")
    except Exception as e:
        print(f"Error: {e}")


def test_day_queries():
    """Test day queries"""
    print("\n=== DAY QUERIES ===")

    # Test today's progress
    print("\n1. !day beter")
    try:
        result = db.day("beter")
        print(f"Result: {result}")
    except Exception as e:
        print(f"Error: {e}")

    # Test yesterday's progress
    print("\n2. !day beter 1")
    try:
        result = db.day("beter", None, "0", 1)
        print(f"Result: {result}")
    except Exception as e:
        print(f"Error: {e}")


def test_week_queries():
    """Test week queries"""
    print("\n=== WEEK QUERIES ===")

    # Test this week's progress
    print("\n1. !week beter")
    try:
        result = db.week("beter")
        print(f"Result: {result}")
    except Exception as e:
        print(f"Error: {e}")

    # Test last week's progress
    print("\n2. !week beter 1")
    try:
        result = db.week("beter", None, "0", 1)
        print(f"Result: {result}")
    except Exception as e:
        print(f"Error: {e}")


def test_region_stats():
    """Test region stats"""
    print("\n=== REGION STATS ===")

    # Test global stats
    print("\n1. !regionstats")
    try:
        result = db.region_stats()
        print(f"Result: {result}")
    except Exception as e:
        print(f"Error: {e}")

    # Test NA stats
    print("\n2. !regionstats NA")
    try:
        result = db.region_stats("NA")
        print(f"Result: {result}")
    except Exception as e:
        print(f"Error: {e}")


def test_milestone_queries():
    """Test milestone queries"""
    print("\n=== MILESTONE QUERIES ===")

    # Test milestone 8000
    print("\n1. !milestone 8000")
    try:
        result = db.milestone("8000")
        print(f"Result: {result}")
    except Exception as e:
        print(f"Error: {e}")

    # Test milestone 10000
    print("\n2. !milestone 10000")
    try:
        result = db.milestone("10000")
        print(f"Result: {result}")
    except Exception as e:
        print(f"Error: {e}")


def test_edge_cases():
    """Test edge cases and error conditions"""
    print("\n=== EDGE CASES ===")

    # Test non-existent player
    print("\n1. !rank nonexistentplayer")
    try:
        result = db.rank("nonexistentplayer")
        print(f"Result: {result}")
    except Exception as e:
        print(f"Error: {e}")

    # Test invalid region
    print("\n2. !rank 1 INVALID")
    try:
        result = db.rank("1", "INVALID")
        print(f"Result: {result}")
    except Exception as e:
        print(f"Error: {e}")

    # Test very high rank
    print("\n3. !rank 999999")
    try:
        result = db.rank("999999")
        print(f"Result: {result}")
    except Exception as e:
        print(f"Error: {e}")


def test_case_sensitivity():
    """Test case sensitivity for player name queries"""
    print("\n=== CASE SENSITIVITY TESTS ===")

    # Test different cases of "beterbabbit"
    test_cases = [
        "beterbabbit",  # lowercase
        "Beterbabbit",  # title case
        "BETERBABBIT",  # uppercase
        "BeTeRbAbBiT",  # mixed case
        "BEter",  # mixed case (as requested)
        "BETER",  # uppercase
        "beter",  # lowercase
    ]

    for i, test_case in enumerate(test_cases, 1):
        print(f"\n{i}. !rank {test_case}")
        try:
            result = db.rank(test_case)
            print(f"Result: {result}")
        except Exception as e:
            print(f"Error: {e}")

    # Test peak queries with different cases
    print(f"\n{len(test_cases) + 1}. !peak BEter")
    try:
        result = db.peak("BEter")
        print(f"Result: {result}")
    except Exception as e:
        print(f"Error: {e}")

    print(f"\n{len(test_cases) + 2}. !peak BeTeRbAbBiT")
    try:
        result = db.peak("BeTeRbAbBiT")
        print(f"Result: {result}")
    except Exception as e:
        print(f"Error: {e}")


if __name__ == "__main__":
    print("Testing Twitch Bot Queries with Live Database")
    print("=" * 50)

    # Initialize the database connection
    try:
        db = LeaderboardDB(use_local=False)
        print("✓ Database connection established")
    except Exception as e:
        print(f"✗ Failed to connect to database: {e}")
        sys.exit(1)

    # Run all tests
    test_rank_queries()
    test_name_queries()
    test_top10_queries()
    test_peak_queries()
    test_day_queries()
    test_week_queries()
    test_region_stats()
    test_milestone_queries()
    test_edge_cases()
    test_case_sensitivity()

    print("\n" + "=" * 50)
    print("All tests completed. Review the results above.")
    print("Check for any errors or unexpected behavior.")
