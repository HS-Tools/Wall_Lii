import requests
import re
import html2text
import json
from db_utils import get_db_connection
from gpt_call import summarize_and_format_patch, check_battlegrounds_relevance

BASE_FORUM_URL = "https://us.forums.blizzard.com/en/hearthstone"
BLOG_APIS = (
    "https://hearthstone.blizzard.com/en-us/api/blog/articleList/?page=1&pageSize=1",
)

TRACKER_APIS = (
    "https://us.forums.blizzard.com/en/hearthstone/groups/blizzard-tracker/posts.json",
)


def get_recent_urls(limit=10):
    conn = get_db_connection()
    with conn:
        with conn.cursor() as cur:
            cur.execute(
                "SELECT source FROM news_posts ORDER BY created_at DESC LIMIT %s",
                (limit,),
            )
            return [row[0] for row in cur.fetchall()]


def get_blog_patch_notes():
    try:
        all_articles = []
        for api in BLOG_APIS:
            response = requests.get(api)
            response.raise_for_status()
            articles = response.json()
            all_articles.extend(articles)
        articles = response.json()
        relevant = []

        for article in articles:
            content = article.get("content", "")
            if "battlegrounds" in content.lower():
                relevant.append(
                    {
                        "type": "blog",
                        "title": article.get("title"),
                        "url": article.get("defaultUrl"),
                        "slug": article.get("slug"),
                        "body": html2text.html2text(content).strip(),
                        "date": article.get("publish_details", {}).get("time"),
                        "author": article.get("author", "Blizzard Entertainment"),
                        "summary": article.get("summary", ""),
                        "thumbnail_url": article.get("thumbnail", {}).get("url"),
                        "header_url": article.get("header", {}).get("url"),
                        "publish_details": article.get("publish_details", {}),
                    }
                )

        return relevant

    except Exception as e:
        print(f"Error fetching blog posts: {e}")
        return []


def get_forum_post_body(url):
    topic_id_match = re.search(r"/t/[^/]+/(\d+)", url)
    if not topic_id_match:
        return None, None, None

    topic_id = topic_id_match.group(1)
    topic_json_url = f"{BASE_FORUM_URL}/t/{topic_id}.json"
    res = requests.get(topic_json_url)
    res.raise_for_status()
    data = res.json()

    first_post = data["post_stream"]["posts"][0]
    # Remove any emoji-style codes like :fire:, :sparkles:, etc.
    title = re.sub(r":.*?:", "", data["title"]).strip()
    created_at = first_post["created_at"]
    html_body = first_post["cooked"]
    markdown = html2text.html2text(html_body)

    return title, created_at, markdown.strip()


def get_forum_patch_notes():
    all_posts = []
    for api in TRACKER_APIS:
        res = requests.get(api)
        res.raise_for_status()
        posts = res.json().get("post_stream", {}).get("posts") or res.json()["posts"]
        all_posts.extend(posts)

    relevant = []

    for post in all_posts:
        excerpt = post.get("excerpt", "")
        url_path = post.get("url")
        if not url_path.endswith("/1"):  # only original post
            continue

        if "View Full Article" in post.get("excerpt", ""):
            continue

        full_url = f"{BASE_FORUM_URL}{url_path}"

        try:
            title, date, body = get_forum_post_body(full_url)
            if "battlegrounds" in body.lower():
                relevant.append(
                    {
                        "type": "forum",
                        "title": title,
                        "url": full_url,
                        "slug": post.get("topic", {}).get("slug", ""),
                        "body": body,
                        "date": date,
                        "author": post.get("username", "Blizzard Entertainment"),
                        "summary": excerpt,
                        "thumbnail_url": None,  # Forum posts don't have thumbnails
                        "header_url": None,  # Forum posts don't have headers
                        "publish_details": {"time": date},
                    }
                )
        except Exception as e:
            print(f"Failed to process forum post: {full_url} - {e}")

    return relevant


def insert_patch_to_supabase(post, relevant, table_name="news_posts"):
    # Generate slug (normalize topic_slug)
    slug = post["slug"].lower().replace("–", "-").replace(" ", "-")

    # Get GPT summary and formatted content
    summary, formatted_content = summarize_and_format_patch(post.get("body", ""))
    formatted_content = inject_entity_images(formatted_content)

    data = {
        "title": post["title"],
        "slug": slug,
        "type": "patch",
        "content": formatted_content,
        "summary": summary,
        "image_url": post.get("thumbnail_url"),
        "author": post["author"],
        "created_at": post["date"],
        "updated_at": "now()",
        "is_published": True,
        "source": post["url"],
        "metadata": {
            "header_image": post.get("header_url"),
            "publish_date": post.get("publish_details", {}).get("time"),
        },
        "battlegrounds_relevant": relevant,
    }

    conn = get_db_connection()
    with conn:
        with conn.cursor() as cur:
            # First, try to delete any existing record with the same slug to avoid conflicts
            cur.execute("DELETE FROM news_posts WHERE slug = %s", (data["slug"],))

            # Then insert the new record
            cur.execute(
                """
                INSERT INTO news_posts (
                    title, slug, type, content, summary, image_url, 
                    author, created_at, updated_at, is_published, source, metadata, battlegrounds_relevant
                )
                VALUES (%s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s::jsonb, %s)
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


# Helper to inject entity images after section headers if missing
def inject_entity_images(formatted_html):
    import re

    # Example entity image map (replace with your own source logic or import)
    entity_images = {
        "Ironforge Anvil": "https://example.com/images/ironforge-anvil.png",
        "Bronze Timepiece": "https://example.com/images/bronze-timepiece.png",
        "Czarina Portrait": "https://example.com/images/czarina-portrait.png",
        # ... add more mappings
    }

    def has_image_nearby(section_html):
        return bool(re.search(r"<img[^>]+>", section_html))

    def insert_images_after_match(match):
        title = match.group(1)
        if title not in entity_images:
            return match.group(0)  # no change
        image_html = f"""
        <div class="card-grid">
          <div class="card-grid-item">
            <img class="card-grid-img" src="{entity_images[title]}" alt="{title}">
            <p class="card-grid-text">{title}</p>
          </div>
        </div>
        """
        post_section = formatted_html[match.end() : match.end() + 300]
        if has_image_nearby(post_section):
            return match.group(0)  # skip if existing images nearby
        return f"{match.group(0)}\n{image_html}"

    # Match headers like <h3>Entity Name</h3>
    return re.sub(r"<h3>([^<]+)</h3>", insert_images_after_match, formatted_html)


def strip_html(html):
    return re.sub("<[^<]+?>", "", html)


def extract_first_image(html):
    match = re.search(r'href="(https[^"]+\.(jpg|png|jpeg|gif))"', html)
    return match.group(1) if match else None


def lambda_handler(event, context):
    recent_urls = get_recent_urls()
    blog_posts = get_blog_patch_notes()
    forum_posts = get_forum_patch_notes()

    for blog_post in blog_posts:
        if blog_post["url"] in recent_urls:
            continue
        if "battlegrounds" not in blog_post.get("body", "").lower():
            continue
        relevant = check_battlegrounds_relevance(blog_post.get("body", ""))
        insert_patch_to_supabase(blog_post, relevant)

    for forum_post in forum_posts:
        if forum_post["url"] in recent_urls:
            continue
        if "battlegrounds" not in forum_post.get("body", "").lower():
            continue
        relevant = check_battlegrounds_relevance(forum_post.get("body", ""))
        insert_patch_to_supabase(forum_post, relevant)

    return {"statusCode": 200, "body": json.dumps("Patch processing complete")}


# For local testing
if __name__ == "__main__":
    print(lambda_handler({}, None))


# Test function and invocation for inserting a patch note
def test_insert_patch(use_blog=False):
    """
    Test generating and inserting a patch note to Supabase.
    By default uses the tracker API; set use_blog=True to use blog API.
    """
    # Fetch the most recent patch note
    post = None
    if use_blog:
        posts = get_blog_patch_notes()
    else:
        posts = get_forum_patch_notes()
    if not posts:
        print("No posts available for testing.")
        return
    latest = posts[0]
    # Override fields for testing
    latest["title"] = "test"
    latest["slug"] = "test-patch"
    latest["is_published"] = False  # override publish flag
    latest["date"] = "2025-05-09T00:00:00Z"  # override created_at
    # Remove any existing test post to ensure upsert/replace
    conn = get_db_connection()
    with conn:
        with conn.cursor() as cur:
            cur.execute(
                "DELETE FROM news_posts WHERE slug = %s",
                (latest["slug"],),
            )
    # Summarize and format
    relevant = check_battlegrounds_relevance(latest["body"])
    # Insert into Supabase
    insert_patch_to_supabase(latest, relevant, table_name="news_posts")
    print("Test insert completed for slug:", latest["slug"])


# When running directly, run the test
if __name__ == "__main__":
    # Existing invocation
    print(lambda_handler({}, None))
    # Run test
    print("Running test insert_patch with tracker API")
    test_insert_patch(use_blog=False)
