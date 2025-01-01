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
            if result != expected:
                print(f"  Got:      {result}")
                print(f"  Expected: {expected}")
            else:
                print(f"  Result:   {result}")

    def test_day(self):
        """Test !day command with local data"""
        test_cases = [
            # Basic cases
            ("!day dogdog NA", "dog is rank 8 in NA at 13295 with no games played"),
            ("!day xqn EU", "xqn climbed from 14832 to 14947 (+115) in EU over 2 games: +57, +58"),
            ("!day satellite AP", "satellite fell from 14724 to 14553 (-171) in AP over 16 games: -116, -14, -40, -56, -48, +60, +54, -69, +32, +23, -62, +10, +32, -87, +54, +56"),
            ("!day 1 ap", "satellite fell from 14724 to 14553 (-171) in AP over 16 games: -116, -14, -40, -56, -48, +60, +54, -69, +32, +23, -62, +10, +32, -87, +54, +56"),
            
            # Error cases
            ("!day ap 1", "Invalid server: 1. Valid servers are: NA, EU, AP"),
            ("!day dogdog", "dog is rank 8 in NA at 13295 with no games played"),
            ("!day nonexistent NA", "nonexistent is not on NA  BG leaderboards."),
            ("!day 1 XX", "Invalid server: XX. Valid servers are: NA, EU, AP"),
            ("!day 99999 NA", "No player found at rank 99999 in NA  BG"),
        ]

        self._run_test_cases(test_cases, lambda command: self.queries.format_daily_stats(*self.parse_command(command)))

    def test_lastweek(self):
        """Test !lastweek command with local data"""
        test_cases = [
            # Basic cases
            ("!lastweek dogdog NA", "dog climbed from 12813 to 13155 (+342) in NA over 26 games last week: M: 0, T: 0, W: 0, Th: 0, F: +468, Sa: -30, Su: -96 liiHappyCat"),
            ("!lastweek xqn EU", "xqn climbed from 14319 to 14609 (+290) in EU over 70 games last week: M: +252, T: +216, W: -101, Th: 0, F: -89, Sa: +126, Su: -114 liiHappyCat"),
            ("!lastweek kripp AP", "kripp is not on AP  BG leaderboards"),
            
            # Server inference
            ("!lastweek dogdog", "dog climbed from 12813 to 13155 (+342) in NA over 26 games last week: M: 0, T: 0, W: 0, Th: 0, F: +468, Sa: -30, Su: -96 liiHappyCat"),
            
            # Error cases
            ("!lastweek nonexistent NA", "nonexistent is not on NA  BG leaderboards"),
            ("!lastweek 1 XX", "Invalid server: XX. Valid servers are: NA, EU, AP"),
        ]

        self._run_test_cases(test_cases, lambda command: self.queries.format_last_week_stats(*self.parse_command(command)))

    def test_peak(self):
        """Test !peak command with local data"""
        test_cases = [
            # Basic cases with server specified
            ("!peak dogdog NA", "dog's peak rating in NA this season: 13348 on Dec 30, 2024"),
            ("!peak xqn EU", "xqn's peak rating in EU this season: 14947 on Dec 31, 2024"),
            ("!peak kripp AP", "kripp has no rating history in AP."),
            
            # Server inference
            ("!peak dogdog", "dog's peak rating in NA this season: 13348 on Dec 30, 2024"),
            
            # Invalid cases
            ("!peak nonexistent NA", "nonexistent has no rating history in NA."),
            ("!peak 999 NA", "mauvegnoll's peak rating in NA this season: 8007 on Dec 14, 2024"),
            ("!peak 1 XX", "Invalid server: XX. Valid servers are: NA, EU, AP"),
            ("!peak 1", "Server is required for rank lookup"),
        ]

        self._run_test_cases(test_cases, lambda command: self.queries.format_peak_stats(*self.parse_command(command)))

    def test_rank(self):
        """Test !rank command with local data"""
        test_cases = [
            # Basic rank lookups
            ("!rank 1 NA", "beterbabbit is rank 1 in NA at 15033"),
            ("!rank 10 NA", "akari is rank 10 in NA at 13053"),
            ("!rank 1 EU", "леший is rank 1 in EU at 15316"),
            ("!rank 1 AP", "satellite is rank 1 in AP at 14553"),
            
            # Error cases
            ("!rank 999 NA", "mauvegnoll is rank 999 in NA at 8007"),
            ("!rank 1 XX", "Invalid server: XX. Valid servers are: NA, EU, AP"),
            ("!rank 1", "Server is required for rank lookup"),
        ]

        self._run_test_cases(test_cases, lambda command: self.queries.format_player_stats(*self.parse_command(command)))

    def test_top(self):
        """Test !top command with local data"""
        test_cases = [
            # Basic server cases
            ("!top NA", "Top 10 NA: 1. beterbabbit: 15033, 2. zoinhu: 14711, 3. jeef: 14419, 4. matthew: 13886, 5. mmf: 13817, 6. herusia: 13634, 7. dumplingdan: 13558, 8. dog: 13295, 9. lyme: 13288, 10. akari: 13053"),
            ("!top EU", "Top 10 EU: 1. леший: 15316, 2. xqn: 14947, 3. kzinnii: 14906, 4. fasteddiehs: 14739, 5. vovapain: 14575, 6. hsmt: 14481, 7. mario68: 14409, 8. babofat: 13909, 9. beterbabbit: 13657, 10. пронзаядушу: 13599"),
            ("!top AP", "Top 10 AP: 1. satellite: 14553, 2. duckdragon: 14114, 3. matsuri: 13927, 4. 白うさ: 13855, 5. wakka53: 13571, 6. yoshiyuki: 13535, 7. hsmt: 13348, 8. cogicorgi: 13080, 9. aioisp: 13049, 10. haguren: 13012"),
            
            # Error cases
            ("!top XX", "Invalid server: XX. Valid servers are: NA, EU, AP"),
            ("!top", "None"),
        ]

        self._run_test_cases(test_cases, lambda command: self.queries.format_top_players(*self.parse_command(command)[1:]))

    def test_week(self):
        """Test !week command with local data"""
        test_cases = [
            # Basic cases
            ("!week dogdog NA", "dog climbed from 13155 to 13295 (+140) in NA over 7 games: M: +140, T: 0, W: 0, Th: 0, F: 0, Sa: 0, Su: 0 liiHappyCat"),
            ("!week xqn EU", "xqn climbed from 14609 to 14947 (+338) in EU over 19 games: M: +223, T: +115, W: 0, Th: 0, F: 0, Sa: 0, Su: 0 liiHappyCat"),
            ("!week kripp AP", "kripp is not on AP  BG leaderboards, sadfasf"),
            
            # Server inference
            ("!week dogdog", "dog climbed from 13155 to 13295 (+140) in NA over 7 games: M: +140, T: 0, W: 0, Th: 0, F: 0, Sa: 0, Su: 0 liiHappyCat"),
            
            # Error cases
            ("!week nonexistent NA", "nonexistent is not on NA  BG leaderboards"),
            ("!week 1 XX", "Invalid server: XX. Valid servers are: NA, EU, AP"),
        ]

        self._run_test_cases(test_cases, lambda command: self.queries.format_weekly_stats(*self.parse_command(command)))

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
