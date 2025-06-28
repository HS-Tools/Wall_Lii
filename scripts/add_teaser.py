import json
from db_utils import get_db_connection
from datetime import datetime


def create_special_post(title, slug, summary, content, source, image_url):
    # Format content with image first, then text
    formatted_content = f"""
    <p><img src="{image_url}" alt="{content}" /></p>
    <p>{content}</p>
    """

    # Prepare data for database
    data = {
        "title": title,
        "slug": slug,
        "type": "special",
        "content": formatted_content,
        "summary": summary,
        "image_url": image_url,
        "author": "Blizzard Entertainment",
        "created_at": datetime.utcnow().isoformat() + "Z",
        "updated_at": "now()",
        "is_published": True,
        "source": source,
        "metadata": {
            "publish_date": datetime.utcnow().isoformat() + "Z",
        },
        "battlegrounds_relevant": True,
    }

    # Print the formatted data
    print("\nFormatted Special Post Data:")
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
        print("\nSuccessfully inserted/updated special post in database")
    except Exception as e:
        print(f"\nError inserting into database: {e}")


if __name__ == "__main__":
    # Example usage
    create_special_post(
        title="Patch 32.4.2 Teaser",
        slug="32-4-2-teaser",
        summary="Teaser for minions buffed and added.",
        content="Buffed: Silky Shimmermoth, Bream Counter, Shoalfin Mystic, Felemental, Nalaa the Redeemer, and Shifting Tide. Added to minion pool: Moon-Bacon Jazzer.",
        source="https://x.com/PlayHearthstone/status/1932860398023118930",
        image_url="https://pbs.twimg.com/media/GtLmSaoXcAEafwS?format=jpg&name=medium",
    )
