import asyncio
import requests
import csv
import time
from datetime import datetime
from typing import List, Dict
import aiohttp

REGIONS = ["US", "EU", "AP"]
MODES = ["battlegrounds", "battlegroundsduo"]
PAGES = 80
REGION_MAPPING = {"US": "NA", "EU": "EU", "AP": "AP"}

# Base URL and parameters template
BASE_URL = "https://hearthstone.blizzard.com/en-us/api/community/leaderboardsData"
PARAMS_TEMPLATE = {
    "leaderboardId": None,
    "seasonId": "14",
    "region": None,
    "page": None
}

def make_names_unique(players: List[Dict]) -> List[Dict]:
    """
    Process player data to ensure unique names within each server and mode combination
    by appending #2, #3, etc. to duplicate names
    """
    # Create a dictionary to track name occurrences
    name_counts = {}
    
    # Create a new list for processed players
    processed_players = []
    
    for player in players:
        # Create a key for the server-mode-name combination
        key = f"{player['server']}#{player['mode']}#{player['playername']}"
        
        # Get current count for this name
        count = name_counts.get(key, 0) + 1
        name_counts[key] = count
        
        # Create a new player dict with potentially modified name
        new_player = player.copy()
        if count > 1:
            new_player['playername'] = f"{player['playername']}#{count}"
            
        processed_players.append(new_player)
    
    return processed_players

async def fetch_concurrent():
    """Concurrent fetching with true parallelism and rate limiting"""
    players = []
    sem = asyncio.Semaphore(15)  # Rate limiting
    
    async with aiohttp.ClientSession(connector=aiohttp.TCPConnector(limit=50)) as session:
        # Create all tasks with context
        tasks = []
        for mode in MODES:
            for api_region in REGIONS:
                normalized_region = REGION_MAPPING[api_region]
                for page in range(1, PAGES + 1):
                    params = {
                        "region": api_region,
                        "leaderboardId": mode,
                        "seasonId": "14",
                        "page": page
                    }
                    # Store context with each task
                    tasks.append((
                        normalized_region,
                        mode,
                        fetch_page(session, params, sem)
                    ))

        # Process all results concurrently
        results = await asyncio.gather(*[t[2] for t in tasks])
        
        # Match results with their context
        for (server, mode, _), result in zip(tasks, results):
            if result and 'leaderboard' in result:
                for row in result['leaderboard'].get('rows', []):
                    if row and row.get('accountid'):
                        players.append({
                            "server": server,
                            "mode": mode,
                            "playername": row['accountid'].lower(),
                            "rank": row['rank'],
                            "rating": row['rating'],
                            "timestamp": time.time()
                        })
    
    # Process players to make names unique
    players = make_names_unique(players)
    return players

# Modified fetch_page with semaphore
async def fetch_page(session: aiohttp.ClientSession, params: dict, sem: asyncio.Semaphore, retries=3):
    """Fetch a single page with rate limiting"""
    backoff = 1
    async with sem:  # Rate limiting
        for attempt in range(retries):
            try:
                async with session.get(BASE_URL, params=params) as response:
                    if response.status == 200:
                        return await response.json()
                    print(f"Failed {params}: Status {response.status}")
            except Exception as e:
                print(f"Error {params}: {str(e)}")
            
            if attempt < retries - 1:
                await asyncio.sleep(backoff)
                backoff *= 2
        return None

def save_to_csv(data: List[Dict], filename: str):
    """Save player data to CSV"""
    with open(filename, 'w', newline='') as f:
        writer = csv.DictWriter(f, fieldnames=["server", "mode", "playername", "rank", "rating", "timestamp"])
        writer.writeheader()
        writer.writerows(data)

async def run():
    """Run both methods and compare"""
    # Concurrent benchmark
    start_conc = time.time()
    conc_data = await fetch_concurrent()
    conc_time = time.time() - start_conc
    save_to_csv(conc_data, "concurrent_results.csv")

    print(f"Concurrent time: {conc_time:.2f}")
    print(f"Concurrent records: {len(conc_data)}")

if __name__ == "__main__":
    asyncio.run(run())