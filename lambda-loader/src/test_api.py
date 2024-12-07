import json
import time

from api import getLeaderboardSnapshot

from logger import setup_logger

logger = setup_logger("test_api")


def test_us_fetch():
    logger.info("Testing US region fetch")
    bg_data = getLeaderboardSnapshot(region="US", game_type="battlegrounds")
    
    # Check if we got data for US
    if "US" in bg_data and "battlegrounds" in bg_data["US"]:
        players = bg_data["US"]["battlegrounds"]
        logger.info(f"Total US players: {len(players)}")
        
        # Check lii's data
        if "lii" in players:
            logger.info(f"lii's data: MMR={players['lii']['rating']}, Rank={players['lii']['rank']}")
        
        # Check for any duplicate names
        names = [name.lower() for name in players.keys()]
        duplicates = set([name for name in names if names.count(name) > 1])
        if duplicates:
            logger.warning(f"Found duplicate players: {duplicates}")
        else:
            logger.info("No duplicate players found")

if __name__ == "__main__":
    test_us_fetch()
