import json
from db_utils import get_db_connection


def process_article():
    # Article data
    article = {
        "type": "blog",
        "title": "32.2.2 Teaser",
        "url": "https://twitter.com/PlayHearthstone/status/1781234567890",
        "slug": "32-2-2-teaser",
        "body": """32.2.2 Battlegrounds changes.
 
Buffed: Dinotamer Brann, Gentle Stag, Valiant Tiger, Silithid Burrower, Shadowdancer, Spirited Whimsydrake, Greenskeeper, Bronze Steward, Fire-forged Evoker, Blazing Greasefire, Dancing Barnstormer, Arcane Behemoth, Land Lubber, Ancestral Automaton, Grimscale Elegist, Shoalfin Mystic, Gormling Gourmet, Slumber Sorcerer, Defiant Shipwright, Starry-eyed Explorer, Goldgrubber, Dastardly Drust, Dreaming Thornweaver, Darkgaze Elder, Anubarak, Drustfallen Butcher, Noisul, Seafood Stew, Natural Blessing

Nerfed: Ashen Corruptor, Amplifying Lightspawn, Lokholar Frostforger, Electron, Apprentice of Sefin, Coilskar Sapper, Weary Mage, Corrupted Bristler, Three Lil Quilboar, Tauren Spiritwalker

Reworked: Technical Element, Hackerfin, Catacomb Crasher

Added: Drakkisath, Hunter of Gatherers, Adaptive Ancestor, Darkcrest Strategist, Daggerspine Thrasher, Handless Forsaken, Kangor's Apprentice, Coast Guard. Removed: Low-Flier, Slippery Slider, Arm of the Empire.""",
        "date": "2024-03-19T00:00:00Z",
        "author": "Blizzard Entertainment",
        "thumbnail_url": "https://pbs.twimg.com/media/Gqw42gWXYAE9KIq?format=jpg&name=medium",
    }

    # Format content with image first, then text
    body_html = article["body"].replace("\n\n", "</p><p>")
    formatted_content = f"""
    <p><img src="{article['thumbnail_url']}" alt="32.2.2 Teaser" /></p>
    <p>{body_html}</p>
    """

    # Prepare data for database
    data = {
        "title": article["title"],
        "slug": article["slug"],
        "type": "patch",
        "content": formatted_content,
        "summary": article["title"],
        "image_url": article["thumbnail_url"],
        "author": article["author"],
        "created_at": article["date"],
        "updated_at": "now()",
        "is_published": True,
        "source": article["url"],
        "metadata": {
            "publish_date": article["date"],
        },
        "battlegrounds_relevant": True,
    }

    # Print the formatted data
    print("\nFormatted Article Data:")
    print(json.dumps(data, indent=2))

    # Optional: Insert into database
    try:
        conn = get_db_connection()
        with conn:
            with conn.cursor() as cur:
                cur.execute(
                    """
                    INSERT INTO news_posts (
                        title, slug, type, content, summary, image_url, 
                        author, created_at, updated_at, is_published, source, metadata, battlegrounds_relevant
                    )
                    VALUES (%s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s::jsonb, %s)
                    ON CONFLICT (slug) DO UPDATE SET
                        title = EXCLUDED.title,
                        type = EXCLUDED.type,
                        content = EXCLUDED.content,
                        summary = EXCLUDED.summary,
                        image_url = EXCLUDED.image_url,
                        author = EXCLUDED.author,
                        created_at = EXCLUDED.created_at,
                        updated_at = EXCLUDED.updated_at,
                        is_published = EXCLUDED.is_published,
                        source = EXCLUDED.source,
                        metadata = EXCLUDED.metadata,
                        battlegrounds_relevant = EXCLUDED.battlegrounds_relevant
                    """,
                    (
                        data["title"],
                        data["slug"],
                        data["type"],
                        data["content"],
                        data["summary"],
                        data["image_url"],
                        data["author"],
                        data["created_at"],
                        data["updated_at"],
                        data["is_published"],
                        data["source"],
                        json.dumps(data["metadata"]),
                        data["battlegrounds_relevant"],
                    ),
                )
        print("\nSuccessfully inserted/updated article in database")
    except Exception as e:
        print(f"\nError inserting into database: {e}")


if __name__ == "__main__":
    process_article()
