import requests
import re
import html2text
import json
from db_utils import get_db_connection
from gpt_call import summarize_and_format_patch

BASE_FORUM_URL = "https://us.forums.blizzard.com/en/hearthstone"
BLOG_APIS = (
    "https://hearthstone.blizzard.com/en-us/api/blog/articleList/?page=1&pageSize=1",
)
TRACKER_APIS = [
    "https://us.forums.blizzard.com/en/hearthstone/groups/blizzard-tracker/posts.json",
    # "https://us.forums.blizzard.com/en/hearthstone/groups/blizzard-tracker/posts.json?before=2025-04-01T22%3A14%3A04.003Z",
    # "https://us.forums.blizzard.com/en/hearthstone/groups/blizzard-tracker/posts.json?before=2025-03-22T22%3A14%3A04.003Z",
]


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
    title = data["title"]
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


def insert_patch_to_supabase(post, table_name="news_posts"):
    # Generate slug (normalize topic_slug)
    slug = post["slug"].lower().replace("–", "-").replace(" ", "-")

    # Get GPT summary and formatted content
    summary, formatted_content = summarize_and_format_patch(post.get("body", ""))

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
        "metadata": {
            "source": post["url"],
            "header_image": post.get("header_url"),
            "publish_date": post.get("publish_details", {}).get("time"),
        },
    }

    conn = get_db_connection()
    with conn:
        with conn.cursor() as cur:
            cur.execute(
                """
                INSERT INTO news_posts (
                    title, slug, type, content, summary, image_url, 
                    author, created_at, updated_at, is_published, metadata
                )
                VALUES (%s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s::jsonb)
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
                    metadata = EXCLUDED.metadata
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
                    json.dumps(data["metadata"]),
                ),
            )


def strip_html(html):
    return re.sub("<[^<]+?>", "", html)


def extract_first_image(html):
    match = re.search(r'href="(https[^"]+\.(jpg|png|jpeg|gif))"', html)
    return match.group(1) if match else None


# Run both
if __name__ == "__main__":
    blog_posts = get_blog_patch_notes()
    forum_posts = get_forum_patch_notes()
    for blog_post in blog_posts:
        insert_patch_to_supabase(blog_post)

    # for forum_post in forum_posts:
    #     insert_patch_to_supabase(forum_post)
