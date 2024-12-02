import json
import time

from api import getLeaderboardSnapshot

from logger import setup_logger

logger = setup_logger("test_api")


def test_parallel_fetch():
    # Time both operations
    start_time = time.time()

    # Test battlegrounds
    logger.info("Testing battlegrounds fetch")
    bg_start = time.time()
    bg_data = getLeaderboardSnapshot(game_type="battlegrounds")
    bg_time = time.time() - bg_start

    # Test battlegrounds duo
    logger.info("Testing battlegrounds duo fetch")
    duo_start = time.time()
    duo_data = getLeaderboardSnapshot(game_type="battlegroundsduo")
    duo_time = time.time() - duo_start

    total_time = time.time() - start_time

    # Calculate player counts correctly
    bg_players = sum(len(region["battlegrounds"]) for region in bg_data.values())
    duo_players = sum(len(region["battlegroundsduo"]) for region in duo_data.values())

    # Add detailed player counts
    bg_players_by_region = {
        region: len(data["battlegrounds"]) for region, data in bg_data.items()
    }
    duo_players_by_region = {
        region: len(data["battlegroundsduo"]) for region, data in duo_data.items()
    }

    stats = {
        "bg_fetch_time": bg_time,
        "duo_fetch_time": duo_time,
        "total_time": total_time,
        "bg_players": bg_players,
        "bg_by_region": bg_players_by_region,
        "duo_players": duo_players,
        "duo_by_region": duo_players_by_region,
        "avg_time_per_player": total_time / (bg_players + duo_players),
    }

    # Log each stat separately for better visibility
    for key, value in stats.items():
        if isinstance(value, float):
            logger.info(f"{key}: {value:.2f}")
        else:
            logger.info(f"{key}: {value}")


if __name__ == "__main__":
    test_parallel_fetch()
