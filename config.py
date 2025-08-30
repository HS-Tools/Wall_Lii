# config.py
import os

SEASON = int(os.environ.get("CURRENT_SEASON", "16"))
TABLE_SUFFIX = f"_season{SEASON}"

TABLES = {
    "current_leaderboard": f"current_leaderboard{TABLE_SUFFIX}",
    "leaderboard_snapshots": f"leaderboard_snapshots{TABLE_SUFFIX}",
    "milestone_tracking": f"milestone_tracking{TABLE_SUFFIX}",
}

# New normalized table structure (test versions)
TEST_TABLES = {
    "daily_leaderboard_stats": "daily_leaderboard_stats_test",
    "leaderboard_snapshots": "leaderboard_snapshots_test",
    "players": "players",
    "milestone_tracking": "milestone_tracking",  # unchanged
}
