import sys
import os
import csv
from datetime import datetime, date
from unittest.mock import patch, MagicMock

sys.path.insert(
    0, os.path.abspath(os.path.join(os.path.dirname(__file__), "../../src"))
)

import pytest
from leaderboard import LeaderboardDB


def load_csv_data(csv_file_path):
    """Load CSV data and return as list of dictionaries"""
    data = []
    with open(csv_file_path, "r", encoding="utf-8") as file:
        reader = csv.DictReader(file)
        for row in reader:
            data.append(row)
    return data


def get_mock_data_for_region_and_mode(region, game_mode, day_start=None):
    """Get mock data filtered by region and game mode"""
    csv_path = os.path.join(
        os.path.dirname(__file__),
        "mock_data",
        "daily_leaderboard_top10_2025-10-20_2025-10-21.csv",
    )
    all_data = load_csv_data(csv_path)

    # Filter by region and game_mode
    filtered_data = [
        row
        for row in all_data
        if row["region"] == region and row["game_mode"] == game_mode
    ]

    # If day_start is specified, filter by that too
    if day_start:
        filtered_data = [row for row in filtered_data if row["day_start"] == day_start]

    # Sort by rank and take top 10
    filtered_data.sort(key=lambda x: x["rank"])
    return filtered_data[:10]


def get_mock_players_data():
    """Load players data from CSV"""
    csv_path = os.path.join(
        os.path.dirname(__file__),
        "mock_data",
        "daily_top10_players_2025-10-20_2025-10-21.csv",
    )
    return load_csv_data(csv_path)


def create_mock_db_response(region, game_mode, day_start=None):
    """Create mock database response by joining leaderboard and players data"""
    leaderboard_data = get_mock_data_for_region_and_mode(region, game_mode, day_start)
    players_data = get_mock_players_data()

    # Create a lookup dictionary for player names
    player_lookup = {str(row["player_id"]): row["player_name"] for row in players_data}

    # Join the data
    result = []
    for row in leaderboard_data:
        player_id = str(row["player_id"])
        if player_id in player_lookup:
            result.append(
                {
                    "player_name": player_lookup[player_id],
                    "rating": row["rating"],
                    "rank": row["rank"],
                    "region": row["region"],
                }
            )

    return result


@pytest.fixture
def mock_postgres():
    with patch("psycopg2.pool.SimpleConnectionPool") as mock_pool:
        mock_conn = MagicMock()
        mock_cursor = MagicMock()

        mock_conn.cursor.return_value.__enter__.return_value = mock_cursor
        mock_pool.return_value.getconn.return_value = mock_conn

        yield mock_cursor


@pytest.fixture
def mock_dynamo(autouse=True):
    with patch("boto3.resource") as mock_boto:
        mock_table = MagicMock()
        mock_table.scan.return_value = {
            "Items": [{"Alias": "jeefhs", "PlayerName": "jeef"}]
        }
        mock_boto.return_value.Table.return_value = mock_table
        yield


@pytest.fixture
def mock_time_range_helper():
    """Mock the TimeRangeHelper to return a consistent date"""
    with patch("leaderboard.TimeRangeHelper") as mock_helper:
        mock_helper.start_of_day_la.return_value = datetime(2025, 10, 21, 0, 0, 0)
        yield mock_helper


class TestTop10:
    """Test suite for the top10 command using CSV mock data"""

    def test_top10_global_solo(self, mock_postgres, mock_time_range_helper):
        """Test global top10 for solo mode (game_mode=0)"""
        print("\n" + "=" * 60)
        print("TESTING TOP10 COMMAND")
        print("=" * 60)

        # Mock the database responses for each region
        na_data = create_mock_db_response("NA", "0")
        eu_data = create_mock_db_response("EU", "0")
        ap_data = create_mock_db_response("AP", "0")

        # Set up the mock to return different data based on the query
        def mock_fetchall():
            # This will be called multiple times - return appropriate data based on context
            # For simplicity, we'll return all regions' data combined
            all_data = na_data + eu_data + ap_data
            return all_data

        mock_postgres.fetchall.return_value = mock_fetchall()
        mock_postgres.fetchone.return_value = {"1": 1}  # Mock the existence check

        db = LeaderboardDB()
        result = db.top10()

        print(f"\nTOP10 (global):")
        print(f"Result: {result}")
        print("-" * 40)

        # Verify the result contains expected content
        assert "Top 10 Global (No CN)" in result
        assert "wallii.gg/all" in result
        # Should contain some player names from our mock data
        assert any(
            name in result for name in ["jeef", "beterbabbit", "hsmt", "alutemu"]
        )

    def test_top10_na_region_solo(self, mock_postgres, mock_time_range_helper):
        """Test top10 for NA region in solo mode"""
        na_data = create_mock_db_response("NA", "0")
        mock_postgres.fetchall.return_value = na_data
        mock_postgres.fetchone.return_value = {"1": 1}

        db = LeaderboardDB()
        result = db.top10("NA")

        print(f"\nTOP10 (NA):")
        print(f"Result: {result}")
        print("-" * 40)

        assert "Top 10 NA:" in result
        assert "wallii.gg/na" in result
        assert "jeef" in result  # jeef should be in NA top 10
        assert "beterbabbit" in result  # beterbabbit should be in NA top 10

    def test_top10_eu_region_solo(self, mock_postgres, mock_time_range_helper):
        """Test top10 for EU region in solo mode"""
        eu_data = create_mock_db_response("EU", "0")
        mock_postgres.fetchall.return_value = eu_data
        mock_postgres.fetchone.return_value = {"1": 1}

        db = LeaderboardDB()
        result = db.top10("EU")

        print(f"\nTOP10 (EU):")
        print(f"Result: {result}")
        print("-" * 40)

        assert "Top 10 EU:" in result
        assert "wallii.gg/eu" in result
        assert "hsmt" in result  # hsmt should be in EU top 10

    def test_top10_ap_region_solo(self, mock_postgres, mock_time_range_helper):
        """Test top10 for AP region in solo mode"""
        ap_data = create_mock_db_response("AP", "0")
        mock_postgres.fetchall.return_value = ap_data
        mock_postgres.fetchone.return_value = {"1": 1}

        db = LeaderboardDB()
        result = db.top10("AP")

        print(f"\nTOP10 (AP):")
        print(f"Result: {result}")
        print("-" * 40)

        assert "Top 10 AP:" in result
        assert "wallii.gg/ap" in result
        assert "alutemu" in result  # alutemu should be in AP top 10

    def test_top10_na_region_duos(self, mock_postgres, mock_time_range_helper):
        """Test top10 for NA region in duos mode"""
        na_duos_data = create_mock_db_response("NA", "1")
        mock_postgres.fetchall.return_value = na_duos_data
        mock_postgres.fetchone.return_value = {"1": 1}

        db = LeaderboardDB()
        result = db.top10("NA", "1")

        assert "Top 10 NA:" in result
        assert "wallii.gg/na" in result
        # Should contain duos players
        assert any(name in result for name in ["upsetking", "fuglackh"])

    def test_top10_eu_region_duos(self, mock_postgres, mock_time_range_helper):
        """Test top10 for EU region in duos mode"""
        eu_duos_data = create_mock_db_response("EU", "1")
        mock_postgres.fetchall.return_value = eu_duos_data
        mock_postgres.fetchone.return_value = {"1": 1}

        db = LeaderboardDB()
        result = db.top10("EU", "1")

        assert "Top 10 EU:" in result
        assert "wallii.gg/eu" in result
        # Should contain duos players
        assert any(name in result for name in ["explosion", "viconia"])

    def test_top10_ap_region_duos(self, mock_postgres, mock_time_range_helper):
        """Test top10 for AP region in duos mode"""
        ap_duos_data = create_mock_db_response("AP", "1")
        mock_postgres.fetchall.return_value = ap_duos_data
        mock_postgres.fetchone.return_value = {"1": 1}

        db = LeaderboardDB()
        result = db.top10("AP", "1")

        assert "Top 10 AP:" in result
        assert "wallii.gg/ap" in result
        # Should contain duos players
        assert any(name in result for name in ["kyu091", "ちぇいん"])

    def test_top10_no_data_available(self, mock_postgres, mock_time_range_helper):
        """Test top10 when no data is available"""
        mock_postgres.fetchall.return_value = []
        mock_postgres.fetchone.return_value = None  # No data exists

        db = LeaderboardDB()
        result = db.top10("NA")

        assert "No leaderboard data available for NA today" in result

    def test_top10_global_no_data_any_region(
        self, mock_postgres, mock_time_range_helper
    ):
        """Test global top10 when no data is available for any region"""
        mock_postgres.fetchall.return_value = []
        mock_postgres.fetchone.return_value = None

        db = LeaderboardDB()
        result = db.top10()

        assert "No leaderboard data available for any region today" in result

    def test_top10_database_error(self, mock_postgres, mock_time_range_helper):
        """Test top10 handles database errors gracefully"""
        mock_postgres.execute.side_effect = Exception("Database connection failed")

        db = LeaderboardDB()
        result = db.top10("NA")

        assert "Error fetching leaderboard" in result

    def test_top10_rating_sorting_global(self, mock_postgres, mock_time_range_helper):
        """Test that global top10 correctly sorts by rating across regions"""
        # Create test data with known ratings
        test_data = [
            {"player_name": "player1", "rating": 20000, "rank": 1, "region": "NA"},
            {"player_name": "player2", "rating": 19000, "rank": 1, "region": "EU"},
            {"player_name": "player3", "rating": 18000, "rank": 1, "region": "AP"},
        ]

        mock_postgres.fetchall.return_value = test_data
        mock_postgres.fetchone.return_value = {"1": 1}

        db = LeaderboardDB()
        result = db.top10()

        # Verify players are sorted by rating (highest first)
        assert "player1: 20000" in result
        assert "player2: 19000" in result
        assert "player3: 18000" in result
        # Check that player1 appears before player2
        player1_pos = result.find("player1")
        player2_pos = result.find("player2")
        assert player1_pos < player2_pos

    def test_top10_rank_ordering_region_specific(
        self, mock_postgres, mock_time_range_helper
    ):
        """Test that region-specific top10 maintains rank ordering"""
        test_data = [
            {"player_name": "rank1", "rating": 20000, "rank": 1},
            {"player_name": "rank2", "rating": 19000, "rank": 2},
            {"player_name": "rank3", "rating": 18000, "rank": 3},
        ]

        mock_postgres.fetchall.return_value = test_data
        mock_postgres.fetchone.return_value = {"1": 1}

        db = LeaderboardDB()
        result = db.top10("NA")

        # Verify rank ordering is maintained
        assert "1. rank1: 20000" in result
        assert "2. rank2: 19000" in result
        assert "3. rank3: 18000" in result


class TestPeak:
    """Test suite for the peak command using CSV mock data"""

    def test_peak_beterbabbit_na(self, mock_postgres, mock_time_range_helper):
        """Test peak command with beterbabbit in NA"""
        print("\n" + "=" * 60)
        print("TESTING PEAK COMMAND")
        print("=" * 60)

        # Load snapshot data for beterbabbit
        snapshot_path = os.path.join(
            os.path.dirname(__file__),
            "mock_data",
            "beterbabbit_lastweek_snapshots_2025-10-13.csv",
        )
        snapshot_data = load_csv_data(snapshot_path)

        # Mock the database response
        mock_postgres.fetchall.return_value = snapshot_data
        mock_postgres.fetchone.return_value = {"1": 1}

        db = LeaderboardDB()
        result = db.peak("beterbabbit", "NA")

        print(f"\nPEAK (beterbabbit, NA):")
        print(f"Result: {result}")
        print("-" * 40)

    def test_peak_rank_2(self, mock_postgres, mock_time_range_helper):
        """Test peak command with rank 2"""
        # Mock snapshot data for rank 2 player
        mock_snapshot_data = [
            {
                "player_name": "test_player",
                "rating": 19000,
                "region": "NA",
                "snapshot_time": datetime(2025, 10, 21, 12, 0, 0),
            }
        ]

        mock_postgres.fetchall.return_value = mock_snapshot_data
        mock_postgres.fetchone.return_value = {"1": 1}

        db = LeaderboardDB()
        result = db.peak("2")

        print(f"\nPEAK (2):")
        print(f"Result: {result}")
        print("-" * 40)

    def test_peak_rank_2_na(self, mock_postgres, mock_time_range_helper):
        """Test peak command with rank 2 in NA"""
        mock_snapshot_data = [
            {
                "player_name": "test_player",
                "rating": 19000,
                "region": "NA",
                "snapshot_time": datetime(2025, 10, 21, 12, 0, 0),
            }
        ]

        mock_postgres.fetchall.return_value = mock_snapshot_data
        mock_postgres.fetchone.return_value = {"1": 1}

        db = LeaderboardDB()
        result = db.peak("2", "NA")

        print(f"\nPEAK (2, NA):")
        print(f"Result: {result}")
        print("-" * 40)

    def test_peak_na_beterbabbit(self, mock_postgres, mock_time_range_helper):
        """Test peak command with NA, beterbabbit"""
        snapshot_path = os.path.join(
            os.path.dirname(__file__),
            "mock_data",
            "beterbabbit_lastweek_snapshots_2025-10-13.csv",
        )
        snapshot_data = load_csv_data(snapshot_path)

        mock_postgres.fetchall.return_value = snapshot_data
        mock_postgres.fetchone.return_value = {"1": 1}

        db = LeaderboardDB()
        result = db.peak("NA", "beterbabbit")

        print(f"\nPEAK (NA, beterbabbit):")
        print(f"Result: {result}")
        print("-" * 40)

    def test_peak_na_rank_2(self, mock_postgres, mock_time_range_helper):
        """Test peak command with NA, rank 2"""
        mock_snapshot_data = [
            {
                "player_name": "test_player",
                "rating": 19000,
                "region": "NA",
                "snapshot_time": datetime(2025, 10, 21, 12, 0, 0),
            }
        ]

        mock_postgres.fetchall.return_value = mock_snapshot_data
        mock_postgres.fetchone.return_value = {"1": 1}

        db = LeaderboardDB()
        result = db.peak("NA", "2")

        print(f"\nPEAK (NA, 2):")
        print(f"Result: {result}")
        print("-" * 40)


class TestDay:
    """Test suite for the day command using CSV mock data"""

    def test_day_beterbabbit_na_offset_0(self, mock_postgres, mock_time_range_helper):
        """Test day command with beterbabbit in NA, offset=0 (today)"""
        print("\n" + "=" * 60)
        print("TESTING DAY COMMAND")
        print("=" * 60)

        snapshot_path = os.path.join(
            os.path.dirname(__file__),
            "mock_data",
            "beterbabbit_lastweek_snapshots_2025-10-13.csv",
        )
        snapshot_data = load_csv_data(snapshot_path)

        # Mock daily leaderboard stats for rank lookup
        mock_daily_stats = [{"rank": 2}]

        def mock_fetchall():
            return snapshot_data

        def mock_fetchone():
            return mock_daily_stats[0]

        mock_postgres.fetchall.return_value = mock_fetchall()
        mock_postgres.fetchone.return_value = mock_fetchone()
        mock_postgres.fetchone.return_value = mock_daily_stats[0]

        db = LeaderboardDB()
        result = db.day("beterbabbit", "NA", offset=0)

        print(f"\nDAY (beterbabbit, NA, offset=0):")
        print(f"Result: {result}")
        print("-" * 40)

    def test_day_beterbabbit_na_offset_1(self, mock_postgres, mock_time_range_helper):
        """Test day command with beterbabbit in NA, offset=1 (yesterday)"""
        snapshot_path = os.path.join(
            os.path.dirname(__file__),
            "mock_data",
            "beterbabbit_lastweek_snapshots_2025-10-13.csv",
        )
        snapshot_data = load_csv_data(snapshot_path)

        mock_daily_stats = [{"rank": 2}]

        mock_postgres.fetchall.return_value = snapshot_data
        mock_postgres.fetchone.return_value = mock_daily_stats[0]

        db = LeaderboardDB()
        result = db.day("beterbabbit", "NA", offset=1)

        print(f"\nDAY (beterbabbit, NA, offset=1):")
        print(f"Result: {result}")
        print("-" * 40)

    def test_day_rank_2_offset_0(self, mock_postgres, mock_time_range_helper):
        """Test day command with rank 2, offset=0"""
        mock_snapshot_data = [
            {
                "player_name": "test_player",
                "rating": 19000,
                "region": "NA",
                "snapshot_time": datetime(2025, 10, 21, 12, 0, 0),
                "player_id": 123,
                "game_mode": "0",
            }
        ]

        mock_daily_stats = [{"rank": 2}]

        mock_postgres.fetchall.return_value = mock_snapshot_data
        mock_postgres.fetchone.return_value = mock_daily_stats[0]

        db = LeaderboardDB()
        result = db.day("2", offset=0)

        print(f"\nDAY (2, offset=0):")
        print(f"Result: {result}")
        print("-" * 40)

    def test_day_rank_2_na_offset_0(self, mock_postgres, mock_time_range_helper):
        """Test day command with rank 2 in NA, offset=0"""
        mock_snapshot_data = [
            {
                "player_name": "test_player",
                "rating": 19000,
                "region": "NA",
                "snapshot_time": datetime(2025, 10, 21, 12, 0, 0),
                "player_id": 123,
                "game_mode": "0",
            }
        ]

        mock_daily_stats = [{"rank": 2}]

        mock_postgres.fetchall.return_value = mock_snapshot_data
        mock_postgres.fetchone.return_value = mock_daily_stats[0]

        db = LeaderboardDB()
        result = db.day("2", "NA", offset=0)

        print(f"\nDAY (2, NA, offset=0):")
        print(f"Result: {result}")
        print("-" * 40)

    def test_day_na_beterbabbit_offset_0(self, mock_postgres, mock_time_range_helper):
        """Test day command with NA, beterbabbit, offset=0"""
        snapshot_path = os.path.join(
            os.path.dirname(__file__),
            "mock_data",
            "beterbabbit_lastweek_snapshots_2025-10-13.csv",
        )
        snapshot_data = load_csv_data(snapshot_path)

        mock_daily_stats = [{"rank": 2}]

        mock_postgres.fetchall.return_value = snapshot_data
        mock_postgres.fetchone.return_value = mock_daily_stats[0]

        db = LeaderboardDB()
        result = db.day("NA", "beterbabbit", offset=0)

        print(f"\nDAY (NA, beterbabbit, offset=0):")
        print(f"Result: {result}")
        print("-" * 40)

    def test_day_na_rank_2_offset_0(self, mock_postgres, mock_time_range_helper):
        """Test day command with NA, rank 2, offset=0"""
        mock_snapshot_data = [
            {
                "player_name": "test_player",
                "rating": 19000,
                "region": "NA",
                "snapshot_time": datetime(2025, 10, 21, 12, 0, 0),
                "player_id": 123,
                "game_mode": "0",
            }
        ]

        mock_daily_stats = [{"rank": 2}]

        mock_postgres.fetchall.return_value = mock_snapshot_data
        mock_postgres.fetchone.return_value = mock_daily_stats[0]

        db = LeaderboardDB()
        result = db.day("NA", "2", offset=0)

        print(f"\nDAY (NA, 2, offset=0):")
        print(f"Result: {result}")
        print("-" * 40)


class TestWeek:
    """Test suite for the week command using CSV mock data"""

    def test_week_beterbabbit_na_offset_0(self, mock_postgres, mock_time_range_helper):
        """Test week command with beterbabbit in NA, offset=0 (this week)"""
        print("\n" + "=" * 60)
        print("TESTING WEEK COMMAND")
        print("=" * 60)

        snapshot_path = os.path.join(
            os.path.dirname(__file__),
            "mock_data",
            "beterbabbit_lastweek_snapshots_2025-10-13.csv",
        )
        snapshot_data = load_csv_data(snapshot_path)

        mock_daily_stats = [{"rank": 2}]

        mock_postgres.fetchall.return_value = snapshot_data
        mock_postgres.fetchone.return_value = mock_daily_stats[0]

        db = LeaderboardDB()
        result = db.week("beterbabbit", "NA", offset=0)

        print(f"\nWEEK (beterbabbit, NA, offset=0):")
        print(f"Result: {result}")
        print("-" * 40)

    def test_week_beterbabbit_na_offset_1(self, mock_postgres, mock_time_range_helper):
        """Test week command with beterbabbit in NA, offset=1 (last week)"""
        snapshot_path = os.path.join(
            os.path.dirname(__file__),
            "mock_data",
            "beterbabbit_lastweek_snapshots_2025-10-13.csv",
        )
        snapshot_data = load_csv_data(snapshot_path)

        mock_daily_stats = [{"rank": 2}]

        mock_postgres.fetchall.return_value = snapshot_data
        mock_postgres.fetchone.return_value = mock_daily_stats[0]

        db = LeaderboardDB()
        result = db.week("beterbabbit", "NA", offset=1)

        print(f"\nWEEK (beterbabbit, NA, offset=1):")
        print(f"Result: {result}")
        print("-" * 40)

    def test_week_rank_2_offset_0(self, mock_postgres, mock_time_range_helper):
        """Test week command with rank 2, offset=0"""
        mock_snapshot_data = [
            {
                "player_name": "test_player",
                "rating": 19000,
                "region": "NA",
                "snapshot_time": datetime(2025, 10, 21, 12, 0, 0),
                "player_id": 123,
                "game_mode": "0",
            }
        ]

        mock_daily_stats = [{"rank": 2}]

        mock_postgres.fetchall.return_value = mock_snapshot_data
        mock_postgres.fetchone.return_value = mock_daily_stats[0]

        db = LeaderboardDB()
        result = db.week("2", offset=0)

        print(f"\nWEEK (2, offset=0):")
        print(f"Result: {result}")
        print("-" * 40)

    def test_week_rank_2_na_offset_0(self, mock_postgres, mock_time_range_helper):
        """Test week command with rank 2 in NA, offset=0"""
        mock_snapshot_data = [
            {
                "player_name": "test_player",
                "rating": 19000,
                "region": "NA",
                "snapshot_time": datetime(2025, 10, 21, 12, 0, 0),
                "player_id": 123,
                "game_mode": "0",
            }
        ]

        mock_daily_stats = [{"rank": 2}]

        mock_postgres.fetchall.return_value = mock_snapshot_data
        mock_postgres.fetchone.return_value = mock_daily_stats[0]

        db = LeaderboardDB()
        result = db.week("2", "NA", offset=0)

        print(f"\nWEEK (2, NA, offset=0):")
        print(f"Result: {result}")
        print("-" * 40)

    def test_week_na_beterbabbit_offset_0(self, mock_postgres, mock_time_range_helper):
        """Test week command with NA, beterbabbit, offset=0"""
        snapshot_path = os.path.join(
            os.path.dirname(__file__),
            "mock_data",
            "beterbabbit_lastweek_snapshots_2025-10-13.csv",
        )
        snapshot_data = load_csv_data(snapshot_path)

        mock_daily_stats = [{"rank": 2}]

        mock_postgres.fetchall.return_value = snapshot_data
        mock_postgres.fetchone.return_value = mock_daily_stats[0]

        db = LeaderboardDB()
        result = db.week("NA", "beterbabbit", offset=0)

        print(f"\nWEEK (NA, beterbabbit, offset=0):")
        print(f"Result: {result}")
        print("-" * 40)

    def test_week_na_rank_2_offset_0(self, mock_postgres, mock_time_range_helper):
        """Test week command with NA, rank 2, offset=0"""
        mock_snapshot_data = [
            {
                "player_name": "test_player",
                "rating": 19000,
                "region": "NA",
                "snapshot_time": datetime(2025, 10, 21, 12, 0, 0),
                "player_id": 123,
                "game_mode": "0",
            }
        ]

        mock_daily_stats = [{"rank": 2}]

        mock_postgres.fetchall.return_value = mock_snapshot_data
        mock_postgres.fetchone.return_value = mock_daily_stats[0]

        db = LeaderboardDB()
        result = db.week("NA", "2", offset=0)

        print(f"\nWEEK (NA, 2, offset=0):")
        print(f"Result: {result}")
        print("-" * 40)


class TestRank:
    """Test suite for the rank command using CSV mock data"""

    def test_rank_beterbabbit_na(self, mock_postgres, mock_time_range_helper):
        """Test rank command with beterbabbit in NA"""
        print("\n" + "=" * 60)
        print("TESTING RANK COMMAND")
        print("=" * 60)

        # Mock current leaderboard data for beterbabbit
        mock_leaderboard_data = [
            {"player_name": "beterbabbit", "rating": 17306, "region": "NA", "rank": 2}
        ]

        mock_postgres.fetchall.return_value = mock_leaderboard_data
        mock_postgres.fetchone.return_value = {"1": 1}

        db = LeaderboardDB()
        result = db.rank("beterbabbit", "NA")

        print(f"\nRANK (beterbabbit, NA):")
        print(f"Result: {result}")
        print("-" * 40)

    def test_rank_rank_2(self, mock_postgres, mock_time_range_helper):
        """Test rank command with rank 2"""
        # Mock daily leaderboard stats for rank 2
        mock_daily_stats = [
            {"player_name": "beterbabbit", "rating": 17306, "region": "NA", "rank": 2}
        ]

        mock_postgres.fetchall.return_value = mock_daily_stats
        mock_postgres.fetchone.return_value = {"1": 1}

        db = LeaderboardDB()
        result = db.rank("2")

        print(f"\nRANK (2):")
        print(f"Result: {result}")
        print("-" * 40)

    def test_rank_rank_2_na(self, mock_postgres, mock_time_range_helper):
        """Test rank command with rank 2 in NA"""
        mock_daily_stats = [
            {"player_name": "beterbabbit", "rating": 17306, "region": "NA", "rank": 2}
        ]

        mock_postgres.fetchall.return_value = mock_daily_stats
        mock_postgres.fetchone.return_value = {"1": 1}

        db = LeaderboardDB()
        result = db.rank("2", "NA")

        print(f"\nRANK (2, NA):")
        print(f"Result: {result}")
        print("-" * 40)

    def test_rank_na_beterbabbit(self, mock_postgres, mock_time_range_helper):
        """Test rank command with NA, beterbabbit"""
        mock_leaderboard_data = [
            {"player_name": "beterbabbit", "rating": 17306, "region": "NA", "rank": 2}
        ]

        mock_postgres.fetchall.return_value = mock_leaderboard_data
        mock_postgres.fetchone.return_value = {"1": 1}

        db = LeaderboardDB()
        result = db.rank("NA", "beterbabbit")

        print(f"\nRANK (NA, beterbabbit):")
        print(f"Result: {result}")
        print("-" * 40)

    def test_rank_na_rank_2(self, mock_postgres, mock_time_range_helper):
        """Test rank command with NA, rank 2"""
        mock_daily_stats = [
            {"player_name": "beterbabbit", "rating": 17306, "region": "NA", "rank": 2}
        ]

        mock_postgres.fetchall.return_value = mock_daily_stats
        mock_postgres.fetchone.return_value = {"1": 1}

        db = LeaderboardDB()
        result = db.rank("NA", "2")

        print(f"\nRANK (NA, 2):")
        print(f"Result: {result}")
        print("-" * 40)
