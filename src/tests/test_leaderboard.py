import sys
import os

sys.path.insert(
    0, os.path.abspath(os.path.join(os.path.dirname(__file__), "../../src"))
)

import pytest
from unittest.mock import patch, MagicMock
from leaderboard import LeaderboardDB
from mock_data.top10_mock import top10_mock_data


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


def test_top10_with_mock_data(mock_postgres):
    mock_postgres.fetchall.return_value = top10_mock_data
    db = LeaderboardDB()
    result = db.top10("NA")
    assert "jeef" in result


def test_rank_with_valid_and_invalid_players(mock_postgres):
    mock_postgres.fetchall.return_value = top10_mock_data
    db = LeaderboardDB()
    valid_result = db.rank("jeef", "na")
    invalid_result = db.rank("fakeExample", "na")
    assert "jeef" in valid_result
    assert "fakeExample" not in invalid_result


def test_rank_with_alias(mock_postgres):
    mock_postgres.fetchall.return_value = top10_mock_data
    db = LeaderboardDB()
    alias_result = db.rank("jeefhs", "na")
    assert "jeef" in alias_result


def test_rank_returns_not_found_when_no_player_matches(mock_postgres, mocker):
    mock_postgres.fetchall.return_value = []  # simulate empty result

    db = LeaderboardDB()
    db.aliases = {}

    mocker.patch(
        "leaderboard.parse_rank_or_player_args",
        return_value=("WHERE player_name = %s", ["nonexistent"], None, "NA"),
    )

    result = db.rank("nonexistent", "NA")
    assert "can't be found" in result


def test_rank_handles_database_error_gracefully(mock_postgres, mocker):
    mock_postgres.execute.side_effect = Exception("DB failure")

    db = LeaderboardDB()
    db.aliases = {}

    mocker.patch(
        "leaderboard.parse_rank_or_player_args",
        return_value=("WHERE player_name = %s", ["lii"], None, "NA"),
    )

    result = db.rank("lii", "NA")
    assert "Error fetching rank" in result
