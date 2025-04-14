import os
import asyncio
import aiohttp
from datetime import datetime, timezone
from dotenv import load_dotenv
import psycopg2
from psycopg2.extras import execute_values

# Load environment
load_dotenv()

REGIONS = ["US", "EU", "AP"]
MODES = [("battlegrounds", 0), ("battlegroundsduo", 1)]
REGION_MAPPING = {"US": "NA", "EU": "EU", "AP": "AP"}
BASE_URL = "https://hearthstone.blizzard.com/en-us/api/community/leaderboardsData"
CURRENT_SEASON = 14

def get_db_connection():
    return psycopg2.connect(
        host=os.getenv("DB_HOST"),
        port=os.getenv("DB_PORT", "5432"),
        dbname=os.getenv("DB_NAME"),
        user=os.getenv("DB_USER"),
        password=os.getenv("DB_PASSWORD"),
        sslmode="require"
    )

async def fetch_all_pages(session, region, mode_api, mode_short, sem):
    players = []
    page = 1
    while True:
        params = {
            "region": region,
            "leaderboardId": mode_api,
            "seasonId": str(CURRENT_SEASON),
            "page": page
        }
        async with sem:
            try:
                async with session.get(BASE_URL, params=params) as response:
                    if response.status == 403 or response.status == 429:
                      print(f"Rate limited for {params}. Backing off.")
                      await asyncio.sleep(60)  # wait 1 minute
                      continue  # retry same request
                    data = await response.json()
                    rows = data.get('leaderboard', {}).get('rows', [])
                    if not rows:
                        break
                    for row in rows:
                        if row.get('accountid'):
                            players.append({
                                "player_name": row['accountid'].lower(),
                                "game_mode": mode_short,
                                "region": REGION_MAPPING[region],
                                "rank": row['rank'],
                                "rating": row['rating']
                            })
                    page += 1
            except Exception as e:
                print(f"Error fetching {params}: {e}")
                break
    return players

async def fetch_current_leaderboards():
    sem = asyncio.Semaphore(10)
    async with aiohttp.ClientSession() as session:
        tasks = []
        for mode_api, mode_short in MODES:
            for region in REGIONS:
                tasks.append(fetch_all_pages(session, region, mode_api, mode_short, sem))

        results = await asyncio.gather(*tasks)
        players = [p for sublist in results for p in sublist]
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

def update_current_leaderboard(players):
    conn = None
    try:
        conn = get_db_connection()
        with conn:
            with conn.cursor() as cur:
                cur.execute("TRUNCATE TABLE current_leaderboard;")
                insert_query = """
                    INSERT INTO current_leaderboard (player_name, game_mode, region, rank, rating)
                    VALUES %s
                """
                values = [
                    (
                        p["player_name"],
                        p["game_mode"],
                        p["region"],
                        p["rank"],
                        p["rating"]
                    )
                    for p in players
                ]
                execute_values(cur, insert_query, values, page_size=100)
                print(f"Inserted {len(players)} players into current_leaderboard.")
    except Exception as e:
        print("Error updating current_leaderboard:", str(e))
    finally:
        if conn:
            conn.close()

async def main():
    print("Fetching current leaderboard data...")
    players = await fetch_current_leaderboards()
    print(f"Fetched {len(players)} players.")
    update_current_leaderboard(players)

if __name__ == "__main__":
    asyncio.run(main())