import requests

# Reddit API endpoints for Announcements flair and top posts in r/BobsTavern
urls = [
    "https://www.reddit.com/user/dantedrackis/submitted.json?sort=top&t=week&limit=15",
    # "https://www.reddit.com/r/BobsTavern/new.json?limit=30&sort=new",
    # "https://www.reddit.com/r/BobsTavern/top.json?t=day&sort=new",
    # "https://www.reddit.com/r/BobsTavern/search.json?q=flair%3A%22Announcement%22&restrict_sr=1&limit=10&sort=new",
]

headers = {"User-Agent": "wallii-bot/0.1"}

all_data = []
for url in urls:
    after = None
    for _ in range(2):  # Fetch two pages (adjust as needed)
        paginated_url = f"{url}&after={after}" if after else url
        resp = requests.get(paginated_url, headers=headers)
        data = resp.json()
        all_data.append(data)
        after = data.get("data", {}).get("after")
        if not after:
            break

results = []
for data in all_data:
    for child in data.get("data", {}).get("children", []):
        post_data = child.get("data", {})
        title = post_data.get("title")
        permalink = f"https://www.reddit.com{post_data.get('permalink')}"
        images = []

        # Extract gallery images (if available)
        if post_data.get("is_gallery"):
            media_metadata = post_data.get("media_metadata", {})
            gallery_items = post_data.get("gallery_data", {}).get("items", [])
            for item in gallery_items:
                media_id = item.get("media_id")
                if media_id and media_metadata.get(media_id):
                    img_url = media_metadata[media_id]["s"]["u"].replace("&amp;", "&")
                    images.append(img_url)

        results.append({"title": title, "permalink": permalink, "images": images})

print("<div>")
print("<h2>Table of Contents</h2>")
print("<ul>")
for post in results:
    title_lower = post["title"].lower()
    if "all the new minions" in title_lower:
        continue
    if "new" not in title_lower and "returning" not in title_lower:
        continue
    if not any(
        keyword in title_lower
        for keyword in [
            "undead",
            "pirates",
            "mechs",
            "dragons",
            "demons",
            "elementals",
            "neutral",
            "minions",
            "naga",
            "quillboar",
            "beast",
            "murloc",
            "trinket",
        ]
    ):
        continue
    anchor = post["title"].replace(" ", "-").lower()
    print(f'<li><a href="#{anchor}">{post["title"]}</a></li>')
print("</ul>")
for post in results:
    title_lower = post["title"].lower()
    if "all the new minions" in title_lower:
        continue
    if "new" not in title_lower and "returning" not in title_lower:
        continue
    if not any(
        keyword in title_lower
        for keyword in [
            "undead",
            "pirates",
            "mechs",
            "dragons",
            "demons",
            "elementals",
            "neutral",
            "minions",
            "naga",
            "quillboar",
            "beast",
            "murloc",
            "trinket",
        ]
    ):
        continue
    anchor = post["title"].replace(" ", "-").lower()
    print(f'<h2 id="{anchor}">{post["title"]}</h2>')
    print(
        f'<p><a href="{post["permalink"]}" target="_blank" rel="noopener noreferrer">View on Reddit</a></p>'
    )
    for img in post["images"]:
        print(f'<span><img src="{img}" alt="Card reveal" /></span>')
print("</div>")
