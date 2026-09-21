import json
import re
from datetime import datetime, timezone
from pathlib import Path

import requests
from bs4 import BeautifulSoup

from config import WEBHOOK_URL, ROLE_ID


LISTING_URL = "https://game.intel.com/us/giveaways/"
POSTED_FILE = Path("posted.json")
DATA_FILE = Path("intel.json")


HEADERS = {
    "User-Agent": (
        "Mozilla/5.0 (Windows NT 10.0; Win64; x64) "
        "AppleWebKit/537.36 (KHTML, like Gecko) "
        "Chrome/138.0.0.0 Safari/537.36"
    )
}


def load_posted():
    if not POSTED_FILE.exists():
        return {"seen": []}

    with POSTED_FILE.open("r", encoding="utf-8") as f:
        return json.load(f)


def save_posted(data):
    with POSTED_FILE.open("w", encoding="utf-8") as f:
        json.dump(data, f, indent=2)


def save_site_data(giveaway):
    data = {
        "source": "Intel Gaming Access",
        "status": "active",
        "title": giveaway["title"],
        "url": giveaway["url"],
        "image": giveaway["image"],
        "description": giveaway["description"],
        "type": "Sweepstakes",
        "ends_at": giveaway["end_date"].replace(
            tzinfo=timezone.utc
        ).isoformat(),
        "updated_at": datetime.now(
            timezone.utc
        ).isoformat(),
    }

    with DATA_FILE.open("w", encoding="utf-8") as f:
        json.dump(data, f, indent=2)


def get_listing():
    print("Fetching Intel giveaway listing...")

    response = requests.get(
        LISTING_URL,
        headers=HEADERS,
        timeout=30
    )

    response.raise_for_status()

    soup = BeautifulSoup(response.text, "lxml")

    # Find giveaway articles
    articles = soup.find_all("article")

    if not articles:
        raise Exception("No giveaway articles found.")

    print(f"Found {len(articles)} article(s).")

    for article in articles:

        # Find title
        title_tag = article.find("h2")

        if not title_tag:
            print("⚠️ Skipping article: no title found.")
            continue

        title = title_tag.get_text(strip=True)

        # Find link safely
        link = article.find("a", href=True)

        if not link:
            print(f"\n========== ARTICLE HTML: {title} ==========")
            print(article.prettify())
            print("========== END ARTICLE HTML ==========\n")
            continue

        url = link.get("href")

        if not url:
            print(f"⚠️ Skipping '{title}': empty URL.")
            continue

        # Convert relative URL to absolute URL
        if url.startswith("/"):
            url = "https://game.intel.com" + url

        # Find image safely
        image_tag = article.find("img")

        if image_tag:
            image = (
                image_tag.get("src")
                or image_tag.get("data-src")
                or image_tag.get("data-lazy-src")
            )
        else:
            image = None

        if not image:
            print(f"⚠️ No image found for '{title}'.")

        # Convert relative image URL to absolute URL
        if image and image.startswith("/"):
            image = "https://game.intel.com" + image

        # Find description safely
        description_tag = article.find("p")

        if description_tag:
            description = description_tag.get_text(
                " ",
                strip=True
            )
        else:
            description = ""

        # Generate slug
        slug = url.rstrip("/").split("/")[-1]

        print(f"Found giveaway: {title}")
        print(f"URL: {url}")

        return {
            "slug": slug,
            "title": title,
            "url": url,
            "image": image,
            "description": description,
        }

    raise Exception("No valid Intel giveaway found.")


def get_end_date(url):
    print(f"Fetching giveaway page: {url}")

    response = requests.get(
        url,
        headers=HEADERS,
        timeout=30
    )

    response.raise_for_status()

    soup = BeautifulSoup(response.text, "lxml")

    text = soup.get_text(
        " ",
        strip=True
    )

    # Intel format:
    # Offer ends September 30, 2026
    match = re.search(
        r"Offer ends ([A-Za-z]+ \d{1,2}, \d{4})",
        text,
        re.IGNORECASE
    )

    if not match:
        raise Exception(
            "End date not found on giveaway page."
        )

    date_string = match.group(1)

    print(f"End date found: {date_string}")

    return datetime.strptime(
        date_string,
        "%B %d, %Y"
    )


def send_discord(giveaway):
    timestamp = int(
        giveaway["end_date"].replace(
            tzinfo=timezone.utc
        ).timestamp()
    )

    embed = {
        "author": {
            "name": "Intel Gaming Access",
            "url": LISTING_URL,
            "icon_url": (
                "https://file.garden/afbSsuts32dZ5wSl/"
                "Intel-logo-2022.png"
            ),
        },

        "title": giveaway["title"],

        "url": giveaway["url"],

        "color": 0x0071C5,

        "fields": [
            {
                "name": "Ends",
                "value": (
                    f"<t:{timestamp}:F>\n"
                    f"<t:{timestamp}:R>"
                ),
                "inline": True,
            },
            {
                "name": "Type",
                "value": "Sweepstakes 🎟",
                "inline": True,
            },
        ],

        "footer": {
            "text": "Subho's Intel Gaming Informer",
            "icon_url": (
                "https://files.catbox.moe/qttqpy.png"
            ),
        },
    }

    # Only add image if one exists
    if giveaway.get("image"):
        embed["image"] = {
            "url": giveaway["image"]
        }

    payload = {
        "content": (
            f"<@&{ROLE_ID}>"
            if ROLE_ID
            else ""
        ),
        "embeds": [embed],
    }

    print("Sending Discord notification...")

    response = requests.post(
        WEBHOOK_URL,
        json=payload,
        timeout=30
    )

    response.raise_for_status()

    print("Discord notification sent.")


def main():
    print("=== Intel Giveaway Notifier ===")

    giveaway = get_listing()

    giveaway["end_date"] = get_end_date(
        giveaway["url"]
    )

    # Update website data every run
    save_site_data(giveaway)

    print("intel.json updated.")

    # Load already posted giveaways
    data = load_posted()

    seen = set(
        data.get("seen", [])
    )

    # Check if already posted
    if giveaway["slug"] in seen:
        print("Already posted.")
        return

    # New giveaway
    print()
    print("NEW GIVEAWAY FOUND!")
    print(giveaway["title"])
    print(giveaway["url"])

    # Send Discord notification
    send_discord(giveaway)

    # Mark as posted
    seen.add(giveaway["slug"])

    save_posted(
        {
            "seen": sorted(seen)
        }
    )

    print("posted.json updated.")
    print("Done!")


if __name__ == "__main__":
    main()
