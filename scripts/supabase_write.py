import os
import asyncio
import aiohttp
from datetime import datetime, timezone
from dotenv import load_dotenv
import psycopg2
from psycopg2.extras import execute_values

# Load environment
load_dotenv()

# Configs
REGIONS = ["US", "EU", "AP"]
MODES = [("battlegrounds", 0), ("battlegroundsduo", 1)]
REGION_MAPPING = {"US": "NA", "EU": "EU", "AP": "AP"}
BASE_URL = "https://hearthstone.blizzard.com/en-us/api/community/leaderboardsData"

# Database connection
def get_db_connection():
    return psycopg2.connect(
        host=os.getenv("DB_HOST"),
        port=os.getenv("DB_PORT", "5432"),
        dbname=os.getenv("DB_NAME"),
        user=os.getenv("DB_USER"),
        password=os.getenv("DB_PASSWORD"),
        sslmode="require"
    )

async def fetch_page(session, params, sem, retries=3):
    backoff = 1
    async with sem:
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

async def fetch_leaderboards(max_pages: int = 1):
    players = []
    sem = asyncio.Semaphore(10)
    async with aiohttp.ClientSession() as session:
        tasks = []
        for mode_api, mode_short in MODES:
            for api_region in REGIONS:
                for page in range(1, max_pages + 1):
                    params = {
                        "region": api_region,
                        "leaderboardId": mode_api,
                        "seasonId": "14",
                        "page": page
                    }
                    tasks.append((REGION_MAPPING[api_region], mode_short, fetch_page(session, params, sem)))

        results = await asyncio.gather(*[t[2] for t in tasks])
        for (region, mode, _), result in zip(tasks, results):
            if result and 'leaderboard' in result:
                for row in result['leaderboard'].get('rows', []):
                    if row and row.get('accountid'):
                        players.append({
                            "player_name": row['accountid'].lower(),
                            "game_mode": mode,
                            "region": region,
                            "rank": row['rank'],
                            "rating": row['rating'],
                            "snapshot_time": datetime.now(timezone.utc).isoformat()
                        })

    return _make_names_unique(players)

def _make_names_unique(players):
    seen = {}
    final = []
    for p in players:
        key = f"{p['region']}#{p['game_mode']}#{p['player_name']}"
        count = seen.get(key, 0) + 1
        seen[key] = count
        p = p.copy()
        if count > 1:
            p['player_name'] = f"{p['player_name']}#{count}"
        final.append(p)
    return final

def write_to_postgres(players):
    insert_query = """
        INSERT INTO leaderboard_snapshots (player_name, game_mode, region, rank, rating, snapshot_time)
        VALUES %s
    """
    values = [
        (
            p["player_name"],
            p["game_mode"],
            p["region"],
            p["rank"],
            p["rating"],
            p["snapshot_time"]
        )
        for p in players
    ]

    try:
        conn = get_db_connection()
        with conn:
            with conn.cursor() as cur:
                execute_values(cur, insert_query, values, page_size=100)
                print(f"Inserted {len(players)} players.")
    except Exception as e:
        print("Error inserting into DB:", str(e))
    finally:
        if conn:
            conn.close()

async def main():
    print("Fetching leaderboard data...")
    players = await fetch_leaderboards(max_pages=40)
    print(f"Fetched {len(players)} players.")
    write_to_postgres(players)

async def loop_every_5_minutes():
    while True:
        try:
            await main()
        except Exception as e:
            print("Error during execution:", e)
        print("Sleeping for 5 minutes...")
        await asyncio.sleep(300)  # 300 seconds = 5 minutes

if __name__ == "__main__":
    asyncio.run(loop_every_5_minutes())