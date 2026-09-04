import argparse
import json
import re
from html import unescape
from urllib.request import urlopen


BASE_FORUM_URL = "https://us.forums.blizzard.com/en/hearthstone"
DEFAULT_POST_URL = (
    "https://us.forums.blizzard.com/en/hearthstone/t/3521-hotfix-patch/159931/1"
)
DEFAULT_SOURCE_URL = (
    "https://us.forums.blizzard.com/en/hearthstone/groups/cs-support-sse/posts.json"
    "?before=2026-04-22T21%3A52%3A40.226Z"
)


def fetch_json(url):
    with urlopen(url, timeout=30) as response:
        return json.loads(response.read().decode("utf-8"))


def extract_topic_id(url):
    match = re.search(r"/t/[^/]+/(\d+)(?:/(\d+))?", url)
    if not match:
        raise ValueError(f"Could not parse topic id from URL: {url}")
    return match.group(1), match.group(2)


def normalize_forum_path(url_or_path):
    if url_or_path.startswith(BASE_FORUM_URL):
        return url_or_path.removeprefix(BASE_FORUM_URL)
    return url_or_path


def strip_html(html):
    text = re.sub(r"<a [^>]*></a>", "", html)
    text = re.sub(r"</(h1|h2|h3|h4|summary|p|li)>", "\n", text)
    text = re.sub(r"<br\s*/?>", "\n", text)
    text = re.sub(r"<[^>]+>", "", text)
    lines = [line.strip() for line in unescape(text).splitlines()]
    return "\n".join(line for line in lines if line)


def find_source_post(source_url, target_url):
    data = fetch_json(source_url)
    posts = data.get("post_stream", {}).get("posts") or data.get("posts", [])
    target_path = normalize_forum_path(target_url)

    for index, post in enumerate(posts):
        if post.get("url") == target_path:
            return {
                "source_url": source_url,
                "source_index": index,
                "source_post": post,
            }

    return {
        "source_url": source_url,
        "source_index": None,
        "source_post": None,
        "available_urls": [post.get("url") for post in posts],
    }


def build_payload(post_url, source_url):
    topic_id, requested_post_number = extract_topic_id(post_url)
    topic_json_url = f"{BASE_FORUM_URL}/t/{topic_id}.json"
    topic_data = fetch_json(topic_json_url)
    source_match = find_source_post(source_url, post_url)

    posts = topic_data.get("post_stream", {}).get("posts", [])
    target_post = None
    if requested_post_number:
        for post in posts:
            if str(post.get("post_number")) == requested_post_number:
                target_post = post
                break
    if target_post is None and posts:
        target_post = posts[0]

    cooked = target_post.get("cooked", "") if target_post else ""
    metadata = {
        "requested_url": post_url,
        "topic_json_url": topic_json_url,
        "topic": {
            key: topic_data.get(key)
            for key in (
                "id",
                "title",
                "fancy_title",
                "unicode_title",
                "slug",
                "created_at",
                "last_posted_at",
                "posts_count",
                "highest_post_number",
                "tags",
                "category_id",
                "word_count",
                "visible",
                "closed",
                "archived",
                "featured_link",
                "image_url",
                "first_tracked_post",
                "tracked_posts",
            )
        },
        "post": {
            key: target_post.get(key)
            for key in (
                "id",
                "post_number",
                "username",
                "created_at",
                "updated_at",
                "last_version_at",
                "version",
                "topic_id",
                "topic_slug",
                "reads",
                "readers_count",
                "score",
                "moderator",
                "admin",
                "staff",
                "user_id",
            )
        }
        if target_post
        else None,
        "source_match": source_match,
    }

    forum_payload = {
        "title": re.sub(r":.*?:", "", topic_data.get("title", "")).strip(),
        "url": post_url,
        "slug": topic_data.get("slug"),
        "author": target_post.get("username") if target_post else None,
        "created_at": target_post.get("created_at") if target_post else None,
        "updated_at": target_post.get("updated_at") if target_post else None,
        "cooked_html": cooked,
        "plain_text_body": strip_html(cooked),
    }

    return {
        "metadata": metadata,
        "forum_payload": forum_payload,
    }


def main():
    parser = argparse.ArgumentParser(
        description="Fetch metadata and body payload for a Blizzard forum post."
    )
    parser.add_argument("--post-url", default=DEFAULT_POST_URL)
    parser.add_argument("--source-url", default=DEFAULT_SOURCE_URL)
    args = parser.parse_args()

    print(json.dumps(build_payload(args.post_url, args.source_url), indent=2))


if __name__ == "__main__":
    main()
