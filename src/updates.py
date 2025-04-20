import requests
import re
import html2text

BASE_FORUM_URL = "https://us.forums.blizzard.com/en/hearthstone"
BLOG_API = (
    "https://hearthstone.blizzard.com/en-us/api/blog/articleList/?page=1&pageSize=8"
)
TRACKER_APIS = [
    # "https://us.forums.blizzard.com/en/hearthstone/groups/blizzard-tracker/posts.json",
    "https://us.forums.blizzard.com/en/hearthstone/groups/blizzard-tracker/posts.json?before=2025-03-25T22%3A14%3A04.003Z",
    # "https://us.forums.blizzard.com/en/hearthstone/groups/blizzard-tracker/posts.json?before=2025-02-25T22%3A14%3A04.003Z",
]


def get_blog_patch_notes():
    try:
        response = requests.get(BLOG_API)
        response.raise_for_status()
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
                        "body": html2text.html2text(content).strip(),
                        "date": article.get("publishDate", "N/A"),
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

        full_url = f"{BASE_FORUM_URL}{url_path}"

        try:
            title, date, body = get_forum_post_body(full_url)
            if "battlegrounds" in body.lower():
                relevant.append(
                    {
                        "type": "forum",
                        "title": title,
                        "url": full_url,
                        "body": body,
                        "date": date,
                    }
                )
        except Exception as e:
            print(f"Failed to process forum post: {full_url} - {e}")

    return relevant


# Unified printer
def print_results(posts):
    for post in posts:
        print(f"\n[{post['type'].upper()}] {post['url']}")
        print(f"\n📌 {post['title']}\n🗓️  {post['date']}\n\n{post['body']}")


# Run both
if __name__ == "__main__":
    blog_posts = get_blog_patch_notes()
    forum_posts = get_forum_patch_notes()
    print_results(blog_posts + forum_posts)
