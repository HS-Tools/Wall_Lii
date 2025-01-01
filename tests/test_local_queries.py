#!/usr/bin/env python3
"""Test cases for leaderboard queries using local DynamoDB data"""

import os
import sys
import unittest
import logging
from datetime import datetime, timezone

sys.path.append(os.path.join(os.path.dirname(__file__), '../src'))
from leaderboard_queries import LeaderboardDB, VALID_SERVERS

# Set logging level to WARNING to suppress INFO messages during tests
logging.getLogger('leaderboard_queries').setLevel(logging.WARNING)

class TestLocalLeaderboardQueries(unittest.TestCase):
    """Test cases for leaderboard queries using local DynamoDB data"""
    
    def setUp(self):
        """Initialize DB connection to local DynamoDB"""
        self.queries = LeaderboardDB(use_local=True)

    def test_peak(self):
        """Test !peak command with local data"""
        print("\nTesting !peak:")

        test_cases = [
            # Basic cases with server specified
            ("!peak dogdog NA", "Expected peak rating for dogdog in NA"),
            ("!peak xqn EU", "Expected peak rating for xqn in EU"),
            ("!peak kripp AP", "Expected peak rating for kripp in AP"),
            
            # Server inference (should use player's most recent server)
            ("!peak dogdog", "Expected peak rating for dogdog in their most active server"),
            
            # Invalid cases
            ("!peak nonexistent NA", "nonexistent is not on NA BG leaderboards."),
            ("!peak 999 NA", "No player found at rank 999 in NA"),
            ("!peak 1 XX", "Invalid server: XX. Valid servers are: NA, EU, AP"),
            ("!peak 1", "Server is required for rank lookup"),
        ]

        for command, expected in test_cases:
            print(f"\n✓ Test: {command}")
            result = self.queries.format_peak_stats(*self.parse_command(command))
            print(f"  Got: {result}")
            print(f"  Expected something like: {expected}")
            # We'll fill in actual expectations after seeing the real data

    def test_top(self):
        """Test !top command with local data"""
        print("\nTesting !top:")

        test_cases = [
            # Basic server cases
            ("!top NA", "Expected top 10 NA players"),
            ("!top EU", "Expected top 10 EU players"),
            ("!top AP", "Expected top 10 AP players"),
            
            # Error cases
            ("!top XX", "Invalid server: XX. Valid servers are: NA, EU, AP"),
            ("!top", "Server is required"),
        ]

        for command, expected in test_cases:
            print(f"\n✓ Test: {command}")
            player_name, server, game_mode = self.parse_command(command)
            result = self.queries.format_top_players(server, game_mode)
            print(f"  Got: {result}")
            print(f"  Expected something like: {expected}")
            # We'll fill in actual expectations after seeing the real data

    def test_rank(self):
        """Test !rank command with local data"""
        print("\nTesting !rank:")

        test_cases = [
            # Basic rank lookups
            ("!rank 1 NA", "Expected #1 player in NA"),
            ("!rank 10 NA", "Expected #10 player in NA"),
            ("!rank 1 EU", "Expected #1 player in EU"),
            ("!rank 1 AP", "Expected #1 player in AP"),
            
            # Error cases
            ("!rank 999 NA", "No player found at rank 999 in NA"),
            ("!rank 1 XX", "Invalid server: XX. Valid servers are: NA, EU, AP"),
            ("!rank 1", "Server is required for rank lookup"),
        ]

        for command, expected in test_cases:
            print(f"\n✓ Test: {command}")
            player_name, server, game_mode = self.parse_command(command)
            result = self.queries.format_player_stats(player_name, server, game_mode)
            print(f"  Got: {result}")
            print(f"  Expected something like: {expected}")
            # We'll fill in actual expectations after seeing the real data

    def test_day(self):
        """Test !day command with local data"""
        print("\nTesting !day:")

        test_cases = [
            # Basic cases
            ("!day dogdog NA", "Expected daily stats for dogdog in NA"),
            ("!day xqn EU", "Expected daily stats for xqn in EU"),
            ("!day kripp AP", "Expected daily stats for kripp in AP"),
            
            # Server inference
            ("!day dogdog", "Expected daily stats for dogdog in their most active server"),
            
            # Error cases
            ("!day nonexistent NA", "nonexistent is not on NA BG leaderboards."),
            ("!day 1 XX", "Invalid server: XX. Valid servers are: NA, EU, AP"),
        ]

        for command, expected in test_cases:
            print(f"\n✓ Test: {command}")
            result = self.queries.format_daily_stats(*self.parse_command(command))
            print(f"  Got: {result}")
            print(f"  Expected something like: {expected}")
            # We'll fill in actual expectations after seeing the real data

    def test_week(self):
        """Test !week command with local data"""
        print("\nTesting !week:")

        test_cases = [
            # Basic cases
            ("!week dogdog NA", "Expected weekly stats for dogdog in NA"),
            ("!week xqn EU", "Expected weekly stats for xqn in EU"),
            ("!week kripp AP", "Expected weekly stats for kripp in AP"),
            
            # Server inference
            ("!week dogdog", "Expected weekly stats for dogdog in their most active server"),
            
            # Error cases
            ("!week nonexistent NA", "nonexistent is not on NA BG leaderboards."),
            ("!week 1 XX", "Invalid server: XX. Valid servers are: NA, EU, AP"),
        ]

        for command, expected in test_cases:
            print(f"\n✓ Test: {command}")
            result = self.queries.format_weekly_stats(*self.parse_command(command))
            print(f"  Got: {result}")
            print(f"  Expected something like: {expected}")
            # We'll fill in actual expectations after seeing the real data

    def parse_command(self, command):
        """Parse command into player_name and server"""
        parts = command.split()[1:]  # Skip the command name

        # Handle duo mode
        game_mode = "1" if "duo" in parts else "0"
        parts = [p for p in parts if p != "duo"]

        # Handle reversed rank arguments
        if len(parts) >= 2 and parts[0] in VALID_SERVERS:
            parts = [parts[1], parts[0]]
        elif len(parts) >= 2 and parts[0] not in VALID_SERVERS and parts[1] not in VALID_SERVERS:
            parts = [parts[0], "XX"]  # Use XX as invalid server for consistent error message

        player_name = parts[0]
        server = parts[1] if len(parts) > 1 else None

        return player_name, server, game_mode

if __name__ == '__main__':
    test_suite = unittest.TestLoader().loadTestsFromTestCase(TestLocalLeaderboardQueries)
    test_result = unittest.TextTestRunner(verbosity=2).run(test_suite)
    
    print("\nTest Summary:")
    print(f"Tests Run: {test_result.testsRun}")
    print(f"Tests Passed: {test_result.testsRun - len(test_result.failures) - len(test_result.errors)}")
    if test_result.wasSuccessful():
        print("✅ All tests completed!")
    else:
        print("❌ Some tests had unexpected results")
        print("This is expected since we need to update the test cases with actual data")
