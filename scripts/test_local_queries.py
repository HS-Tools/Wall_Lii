#!/usr/bin/env python3
"""Test cases for leaderboard queries using local DynamoDB data"""

import os
import sys
import unittest
import logging
from datetime import datetime, timezone

sys.path.append(os.path.join(os.path.dirname(__file__), '../src'))
from leaderboard_queries import LeaderboardDB, VALID_SERVERS

# Configure logging to suppress warnings
logging.getLogger('leaderboard_queries').setLevel(logging.ERROR)

class TestLocalLeaderboardQueries(unittest.TestCase):
    """Test cases for leaderboard queries using local DynamoDB data"""
    
    @classmethod
    def setUpClass(cls):
        """Initialize DB connection to local DynamoDB"""
        cls.queries = LeaderboardDB(use_local=True)

    def setUp(self):
        """Print test name before each test"""
        print(f"\nTesting !{self._testMethodName[5:]}")

    def shortDescription(self):
        """Don't print test docstrings"""
        return None

    def _run_test_cases(self, test_cases, func):
        """Run test cases and print results"""
        for command, expected in test_cases:
            result = func(command)
            print(f"\n✓ {command}")
            print(f"  Got: {result}")
            print(f"  Expected something like: {expected}")

    def test_day(self):
        """Test !day command with local data"""
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

        self._run_test_cases(test_cases, lambda command: self.queries.format_daily_stats(*self.parse_command(command)))

    def test_peak(self):
        """Test !peak command with local data"""
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

        self._run_test_cases(test_cases, lambda command: self.queries.format_peak_stats(*self.parse_command(command)))

    def test_rank(self):
        """Test !rank command with local data"""
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

        self._run_test_cases(test_cases, lambda command: self.queries.format_player_stats(*self.parse_command(command)))

    def test_top(self):
        """Test !top command with local data"""
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
            _, server, game_mode = self.parse_command(command)
            result = self.queries.format_top_players(server, game_mode)
            print(f"\n✓ {command}")
            print(f"  Got: {result}")
            print(f"  Expected something like: {expected}")

    def test_week(self):
        """Test !week command with local data"""
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

        self._run_test_cases(test_cases, lambda command: self.queries.format_weekly_stats(*self.parse_command(command)))

    def test_lastweek(self):
        """Test !lastweek command with local data"""
        test_cases = [
            # Basic cases
            ("!lastweek dogdog NA", "Expected last week's stats for dogdog in NA"),
            ("!lastweek xqn EU", "Expected last week's stats for xqn in EU"),
            ("!lastweek kripp AP", "Expected last week's stats for kripp in AP"),
            
            # Server inference
            ("!lastweek dogdog", "Expected last week's stats for dogdog in their most active server"),
            
            # Error cases
            ("!lastweek nonexistent NA", "nonexistent is not on NA BG leaderboards."),
            ("!lastweek 1 XX", "Invalid server: XX. Valid servers are: NA, EU, AP"),
        ]

        self._run_test_cases(test_cases, lambda command: self.queries.format_last_week_stats(*self.parse_command(command)))

    def parse_command(self, command):
        """Parse command into player_name, server, and game_mode"""
        parts = command.split()
        command_name = parts[0][1:]  # Remove ! from command
        parts = parts[1:]  # Skip the command name
        
        # Default values
        player_name = None
        server = None
        game_mode = "0"
        
        if command_name == "top":
            # !top [server]
            if parts:
                server = parts[0]
            return player_name, server, game_mode
            
        if command_name == "rank":
            # !rank <rank> [server]
            if len(parts) >= 1:
                player_name = parts[0]  # rank number
            if len(parts) >= 2:
                server = parts[1]
            return player_name, server, game_mode
            
        # For peak, day, week commands
        # !command <player> [server]
        if len(parts) >= 1:
            player_name = parts[0]
        if len(parts) >= 2:
            server = parts[1]
            
        return player_name, server, game_mode

if __name__ == '__main__':
    # Configure test runner for minimal output
    import unittest.runner
    class MinimalTestRunner(unittest.runner.TextTestRunner):
        def __init__(self, *args, **kwargs):
            kwargs['verbosity'] = 0
            super().__init__(*args, **kwargs)

    # Run tests with minimal output
    runner = MinimalTestRunner()
    result = runner.run(unittest.TestLoader().loadTestsFromTestCase(TestLocalLeaderboardQueries))
    
    # Print summary
    print("\nTest Summary:")
    print(f"Tests Run: {result.testsRun}")
    print(f"Tests Passed: {result.testsRun - len(result.failures) - len(result.errors)}")
    if result.wasSuccessful():
        print("✅ All tests completed!")
    else:
        print("❌ Some tests had unexpected results")
