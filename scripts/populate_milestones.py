import boto3
from datetime import datetime, timezone
from decimal import Decimal
import os
import sys

# Add lambda-loader/src to Python path
sys.path.append(os.path.join(os.path.dirname(__file__), '..', 'lambda-loader', 'src'))

from api import getLeaderboardSnapshot
from dbUpdater import check_milestones

def populate_milestones():
    """Populate milestone table with current leaderboard data"""
    print("Fetching leaderboard data...")
    
    # Get current data
    bg_data = getLeaderboardSnapshot(game_type="battlegrounds", max_pages=4)
    duo_data = getLeaderboardSnapshot(game_type="battlegroundsduo", max_pages=4)
    
    # Connect to milestone table
    ddb = boto3.resource(
        'dynamodb',
        region_name='us-east-1'
    )
    
    # Create a mock table object that matches what Lambda expects
    class MockTable:
        def __init__(self, table):
            self.table = table
            self.meta = type('Meta', (), {'client': ddb})
    
    table = MockTable(ddb.Table('MilestoneTracking'))
    
    # Process each game mode
    for game_type, data in [("battlegrounds", bg_data), ("battlegroundsduo", duo_data)]:
        mode_num = "0" if game_type == "battlegrounds" else "1"
        
        for server, server_data in data.items():
            for mode, players in server_data.items():
                # Find rank 1 player
                rank_1_player = None
                highest_rating = 0
                
                for player_name, stats in players.items():
                    if stats['rank'] == 1 and stats['rating'] > highest_rating:
                        rank_1_player = {
                            'name': player_name,
                            'rating': stats['rating']
                        }
                        highest_rating = stats['rating']
                
                if rank_1_player:
                    print(f"\nChecking {server} {game_type}:")
                    print(f"Rank 1: {rank_1_player['name']} ({rank_1_player['rating']})")
                    check_milestones(
                        player_name=rank_1_player['name'],
                        rating=rank_1_player['rating'],
                        game_mode=mode_num,
                        server=server,
                        table=table
                    )

if __name__ == "__main__":
    populate_milestones() 