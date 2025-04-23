import requests

# Reddit API endpoint for Announcements flair in r/BobsTavern
url = "https://www.reddit.com/r/BobsTavern/search.json?q=flair%3A%22Announcement%22&restrict_sr=1&sort=new"

headers = {"User-Agent": "wallii-bot/0.1"}

response = requests.get(url, headers=headers)
data = response.json()

results = []

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

# Output the results as HTML
print("<div>")
print("<h2>Table of Contents</h2>")
print("<ul>")
for post in results:
    if post["title"].lower() == "return of the king!!!!":
        break
    title_lower = post["title"].lower()
    if not any(
        keyword in title_lower
        for keyword in [
            "undead",
            "pirates",
            "mechs",
            "dragons",
            "demons",
            "elementals",
            "neutrals",
            "minions",
        ]
    ):
        continue
    anchor = post["title"].replace(" ", "-").lower()
    print(f'<li><a href="#{anchor}">{post["title"]}</a></li>')
print("</ul>")
for post in results:
    if post["title"].lower() == "return of the king!!!!":
        break
    title_lower = post["title"].lower()
    if not any(
        keyword in title_lower
        for keyword in [
            "undead",
            "pirates",
            "mechs",
            "dragons",
            "demons",
            "elementals",
            "neutrals",
            "minions",
        ]
    ):
        continue
    anchor = post["title"].replace(" ", "-").lower()
    print(f'<h2 id="{anchor}">{post["title"]}</h2>')
    print(
        f'<p><a href="{post["permalink"]}" target="_blank" rel="noopener noreferrer">View on Reddit</a></p>'
    )
    for img in post["images"]:
        print(f'<p><img src="{img}" style="width: 300px;" alt="Card reveal"></p>')
print("</div>")
