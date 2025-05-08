import os
import requests
import psycopg2
from dotenv import load_dotenv

load_dotenv()

SUPABASE_URL = os.getenv("SUPABASE_URL")
SUPABASE_SERVICE_ROLE_KEY = os.getenv("SUPABASE_SERVICE_ROLE_KEY")
HEARTHSTONE_JSON_URL = "https://api.hearthstonejson.com/v1/latest/enUS/cards.json"


def get_image_url(card_id):
    return f"https://cards.hearthpwn.com/enUS/bgs/{card_id}_bg.png"


def get_entity_type(card):
    if card.get("battlegrounds", {}).get("hero"):
        return "hero"
    if card.get("isBattlegroundsBuddy"):
        return "buddy"
    if card.get("isBattlegroundsPoolMinion"):
        return "minion"
    if card.get("type") == "BATTLEGROUND_SPELL":
        return "spell"
    if card.get("type") == "BATTLEGROUND_TRINKET":
        return "trinket"
    if card.get("type") == "ENCHANTMENT" and "anomaly" in card.get("id", "").lower():
        return "anomaly"
    return None


def slugify(name):
    import re

    return re.sub(r"[^a-z0-9]", "", name.lower())


def get_db_connection():
    return psycopg2.connect(
        host=os.getenv("DB_HOST"),
        port=os.getenv("DB_PORT", "5432"),
        dbname=os.getenv("DB_NAME"),
        user=os.getenv("DB_USER"),
        password=os.getenv("DB_PASSWORD"),
        sslmode="require",
    )


def fetch_and_upsert_entities():
    response = requests.get(HEARTHSTONE_JSON_URL)
    all_cards = response.json()

    entities = []
    for card in all_cards:
        entity_type = get_entity_type(card)
        if not entity_type:
            continue

        name = card.get("name")
        entity_id = card.get("id")
        if not name or not entity_id:
            continue
        if entity_type == "buddy" and entity_id.endswith("_G"):
            continue

        entity = {
            "entity_name": name,
            "entity_id": entity_id,
            "entity_type": entity_type,
            "image_url": get_image_url(entity_id),
            "entity_slug": slugify(name),
        }
        entities.append(entity)

    conn = get_db_connection()
    cursor = conn.cursor()

    for entity in entities:
        cursor.execute(
            """
            INSERT INTO bg_entities (entity_id, entity_name, entity_type, image_url)
            VALUES (%s, %s, %s, %s)
            ON CONFLICT (entity_id) DO UPDATE SET
                entity_name = EXCLUDED.entity_name,
                entity_type = EXCLUDED.entity_type,
                image_url = EXCLUDED.image_url
            """,
            (
                entity["entity_id"],
                entity["entity_name"],
                entity["entity_type"],
                entity["image_url"],
            ),
        )

    conn.commit()
    cursor.close()
    conn.close()

    print(f"Upserted {len(entities)} BG entities.")


if __name__ == "__main__":
    fetch_and_upsert_entities()
