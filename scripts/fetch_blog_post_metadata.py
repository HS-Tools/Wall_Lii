import argparse
import json
import re
from html import unescape
from urllib.parse import urlparse
from urllib.request import urlopen


DEFAULT_POST_URL = (
    "https://hearthstone.blizzard.com/en-us/news/24252014/35-2-2-patch-notes"
)
DEFAULT_API_URL = (
    "https://hearthstone.blizzard.com/en-us/api/blog/articleList/?page=1&pageSize=20"
)


def fetch_json(url):
    with urlopen(url, timeout=30) as response:
        return json.loads(response.read().decode("utf-8"))


def article_id_from_url(url):
    match = re.search(r"/(?:news|blog)/(\d+)", url)
    return match.group(1) if match else None


def normalize_blog_url(url):
    parsed = urlparse(url)
    match = re.search(r"/(?:news|blog)/(\d+)", parsed.path)
    return match.group(1) if match else url.rstrip("/")


def strip_html(html):
    text = re.sub(r"</(h1|h2|h3|h4|summary|p|li)>", "\n", html)
    text = re.sub(r"<br\s*/?>", "\n", text)
    text = re.sub(r"<[^>]+>", "", text)
    lines = [line.strip() for line in unescape(text).splitlines()]
    return "\n".join(line for line in lines if line)


def get_articles(api_url):
    data = fetch_json(api_url)
    if isinstance(data, list):
        return data, data
    articles = data.get("articles", data.get("data", data.get("items", [])))
    return data, articles


def find_article(api_url, post_url):
    raw_api_payload, articles = get_articles(api_url)
    target_id = article_id_from_url(post_url)
    target_url_key = normalize_blog_url(post_url)

    for index, article in enumerate(articles):
        article_urls = [
            article.get("defaultUrl"),
            article.get("url"),
            article.get("share_url"),
        ]
        article_id = str(article.get("id") or article.get("content_id") or "")
        normalized_urls = [normalize_blog_url(url) for url in article_urls if url]

        if target_id and (target_id == article_id or target_id in normalized_urls):
            return raw_api_payload, index, article
        if target_url_key in normalized_urls:
            return raw_api_payload, index, article

    return raw_api_payload, None, None


def build_payload(post_url, api_url):
    raw_api_payload, source_index, article = find_article(api_url, post_url)
    if article is None:
        raise ValueError(f"Could not find article for URL in API response: {post_url}")

    content_html = article.get("content", "")
    metadata = {
        "requested_url": post_url,
        "api_url": api_url,
        "source_index": source_index,
        "article": {
            key: article.get(key)
            for key in (
                "id",
                "content_id",
                "title",
                "slug",
                "defaultUrl",
                "url",
                "author",
                "summary",
                "publish_details",
                "thumbnail",
                "header",
                "tags",
                "category",
                "locale",
            )
        },
        "api_payload_keys": sorted(raw_api_payload.keys())
        if isinstance(raw_api_payload, dict)
        else None,
    }

    blog_payload = {
        "title": article.get("title"),
        "url": article.get("defaultUrl") or post_url,
        "requested_url": post_url,
        "slug": article.get("slug"),
        "author": article.get("author", "Blizzard Entertainment"),
        "summary": article.get("summary", ""),
        "published_at": article.get("publish_details", {}).get("time"),
        "thumbnail_url": article.get("thumbnail", {}).get("url")
        if isinstance(article.get("thumbnail"), dict)
        else None,
        "header_url": article.get("header", {}).get("url")
        if isinstance(article.get("header"), dict)
        else None,
        "content_html": content_html,
        "plain_text_body": strip_html(content_html),
    }

    return {
        "metadata": metadata,
        "blog_payload": blog_payload,
    }


def main():
    parser = argparse.ArgumentParser(
        description="Fetch metadata and body payload for a Hearthstone blog post."
    )
    parser.add_argument("--post-url", default=DEFAULT_POST_URL)
    parser.add_argument("--api-url", default=DEFAULT_API_URL)
    args = parser.parse_args()

    print(json.dumps(build_payload(args.post_url, args.api_url), indent=2))


if __name__ == "__main__":
    main()
