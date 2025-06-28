import os
import requests
import psycopg2
from bs4 import BeautifulSoup
from dotenv import load_dotenv

load_dotenv()

ignored_cards = ["Avenge_(card)", "Blood Gem"]


def get_db_connection():
    return psycopg2.connect(
        host=os.getenv("DB_HOST"),
        port=os.getenv("DB_PORT", "5432"),
        dbname=os.getenv("DB_NAME"),
        user=os.getenv("DB_USER"),
        password=os.getenv("DB_PASSWORD"),
        sslmode="require",
    )


def scrape_and_insert_from_wiki(url: str, label: str):
    response = requests.get(url)
    response.raise_for_status()
    # Save the full HTML response for debugging
    with open(f"debug_{label}.html", "w", encoding="utf-8") as f:
        f.write(response.text)
    print(f"Fetched URL: {response.url}")

    soup = BeautifulSoup(response.text, "html.parser")
    values = []

    cards = soup.select("div.card-div")
    print(f"Found {len(cards)} .card-div entries")
    if cards:
        for card in cards:
            anchors = card.select(".card-hover-anchor")
            if anchors:
                for anchor in anchors:
                    img_tag = anchor.find("img")
                    link_tag = anchor.find("a", title=True)
                    if img_tag and link_tag:
                        image_url = "https://hearthstone.wiki.gg" + img_tag["src"]
                        name = link_tag["title"].removeprefix("Battlegrounds/")
                        if name not in ignored_cards:
                            values.append((name, image_url))
            else:
                # Fallback: grab any <a><img></a> inside the card-div
                fallback_link = card.find("a", title=True)
                img_tag = card.find("img")
                if fallback_link and img_tag:
                    image_url = "https://hearthstone.wiki.gg" + img_tag["src"]
                    name = fallback_link["title"].removeprefix("Battlegrounds/").strip()
                    if name not in ignored_cards:
                        values.append((name, image_url))
    else:
        # Fallback: find all <a><img></a> elements after the "Tavern minions" heading
        target_header = soup.find("span", {"id": "Tavern_minions"})
        if not target_header:
            print("Could not find Tavern_minions header")
        fallback_count = 0
        if target_header:
            content = target_header.find_parent("h3")
            for sibling in content.find_all_next():
                if sibling.name == "h3":
                    break  # Stop at the next section
                img_links = sibling.select("a > img")
                for img in img_links:
                    parent = img.find_parent("a")
                    if not parent or not parent.has_attr("title"):
                        continue

                    name = parent["title"]
                    image_url = (
                        "https://hearthstone.wiki.gg" + img["src"]
                        if img["src"].startswith("/")
                        else img["src"]
                    )
                    name = name.removeprefix("Battlegrounds/").strip()
                    if name not in ignored_cards:
                        values.append((name, image_url))
                        fallback_count += 1
            print(f"Found {fallback_count} fallback <a><img></a> entries")

    if values:
        conn = get_db_connection()
        cursor = conn.cursor()

        cursor.executemany(
            """
            INSERT INTO bg_entities (entity_name, image_url)
            VALUES (%s, %s)
            ON CONFLICT (entity_name) DO UPDATE SET
                image_url = EXCLUDED.image_url
            """,
            values,
        )

        conn.commit()
        cursor.close()
        conn.close()
        print(f"Inserted {len(values)} entries for {label}")
    else:
        print(f"No entries found for {label}")


if __name__ == "__main__":
    urls = {
        # "minions": "https://hearthstone.wiki.gg/wiki/Battlegrounds/Minion",
        # "tavern_spells": "https://hearthstone.wiki.gg/wiki/Battlegrounds/Tavern_spell",
        # "trinkets": "https://hearthstone.wiki.gg/wiki/Battlegrounds/Trinket",
        # "quests": "https://hearthstone.wiki.gg/wiki/Battlegrounds/Quest",
        # "quest_rewards": "https://hearthstone.wiki.gg/wiki/Battlegrounds/Reward",
        # "buddies": "https://hearthstone.wiki.gg/wiki/Battlegrounds/Buddy",
        # "heroes": "https://hearthstone.wiki.gg/wiki/Battlegrounds/Hero",
        # "spells": "https://hearthstone.wiki.gg/wiki/Battlegrounds/Spell",
        # "removed_cards": "https://hearthstone.wiki.gg/wiki/Battlegrounds/Removed_card",
        "anomalies": "https://hearthstone.wiki.gg/wiki/Battlegrounds/Anomaly",
    }

    for label, url in urls.items():
        scrape_and_insert_from_wiki(url, label)
