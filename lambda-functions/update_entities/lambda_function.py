import requests
from bs4 import BeautifulSoup
from db_utils import get_db_connection
from logger import setup_logger

# Setup logger
logger = setup_logger("UpdateEntities")

ignored_cards = ["Avenge_(card)", "Blood Gem", ""]


def check_recent_news_posts():
    """
    Check if there are any news posts created within the last 4 hours
    Returns True if recent posts exist, False otherwise
    """
    conn = get_db_connection()
    try:
        with conn.cursor() as cur:
            # Check for posts created within the last 4 hours
            cur.execute(
                """
                SELECT COUNT(*) 
                FROM news_posts 
                WHERE created_at >= NOW() - INTERVAL '4 hours'
                AND is_published = true
                """
            )
            count = cur.fetchone()[0]
            logger.info(f"Found {count} news posts within the last 4 hours")
            return count > 0
    except Exception as e:
        logger.error(f"Error checking recent news posts: {e}")
        return False
    finally:
        conn.close()


def scrape_and_insert_from_wiki(url: str, label: str):
    """
    Scrape entities from wiki and insert into database
    Adapted from scripts/get_entities.py
    """
    try:
        response = requests.get(url, timeout=30)
        response.raise_for_status()
        logger.info(f"Fetched URL: {response.url}")

        soup = BeautifulSoup(response.text, "html.parser")
        values = []

        cards = soup.select("div.card-div")
        logger.info(f"Found {len(cards)} .card-div entries for {label}")

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
                        name = (
                            fallback_link["title"]
                            .removeprefix("Battlegrounds/")
                            .strip()
                        )
                        if name not in ignored_cards:
                            values.append((name, image_url))
        else:
            # Fallback: find all <a><img></a> elements after the "Tavern minions" heading
            target_header = soup.find("span", {"id": "Tavern_minions"})
            if not target_header:
                logger.warning("Could not find Tavern_minions header")
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
                logger.info(
                    f"Found {fallback_count} fallback <a><img></a> entries for {label}"
                )

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
            logger.info(f"Inserted {len(values)} entries for {label}")
            return len(values)
        else:
            logger.warning(f"No entries found for {label}")
            return 0

    except Exception as e:
        logger.error(f"Error scraping {label} from {url}: {e}")
        return 0


def update_entities():
    """
    Update all entity data from wiki sources
    """
    urls = {
        "minions": "https://hearthstone.wiki.gg/wiki/Battlegrounds/Minion",
        "tavern_spells": "https://hearthstone.wiki.gg/wiki/Battlegrounds/Tavern_spell",
        "trinkets": "https://hearthstone.wiki.gg/wiki/Battlegrounds/Trinket",
        "quests": "https://hearthstone.wiki.gg/wiki/Battlegrounds/Quest",
        "quest_rewards": "https://hearthstone.wiki.gg/wiki/Battlegrounds/Reward",
        "buddies": "https://hearthstone.wiki.gg/wiki/Battlegrounds/Buddy",
        "heroes": "https://hearthstone.wiki.gg/wiki/Battlegrounds/Hero",
        "spells": "https://hearthstone.wiki.gg/wiki/Battlegrounds/Spell",
        "removed_cards": "https://hearthstone.wiki.gg/wiki/Battlegrounds/Removed_card",
        "anomalies": "https://hearthstone.wiki.gg/wiki/Battlegrounds/Anomaly",
    }

    total_updated = 0
    for label, url in urls.items():
        try:
            count = scrape_and_insert_from_wiki(url, label)
            total_updated += count
        except Exception as e:
            logger.error(f"Failed to update {label}: {e}")

    return total_updated


def lambda_handler(event, context):
    """
    Lambda handler that checks for recent news posts and updates entities if needed
    """
    try:
        logger.info("Starting entity update check")

        # Check if there are recent news posts
        has_recent_posts = check_recent_news_posts()

        if not has_recent_posts:
            logger.info("No recent news posts found, skipping entity update")
            return {
                "statusCode": 200,
                "body": "No recent news posts found, entity update skipped",
            }

        logger.info("Recent news posts found, updating entities")

        # Update entities from wiki sources
        total_updated = update_entities()

        logger.info(f"Entity update completed. Total entries updated: {total_updated}")

        return {
            "statusCode": 200,
            "body": f"Entity update completed. Total entries updated: {total_updated}",
        }

    except Exception as e:
        logger.error(f"Error in lambda handler: {e}")
        return {"statusCode": 500, "body": f"Error updating entities: {str(e)}"}


# For local testing
if __name__ == "__main__":
    result = lambda_handler({}, None)
    print(result)
