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


def save_no_active_giveaway():
    data = {
        "source": "Intel Gaming Access",
        "status": "inactive",
        "title": None,
        "url": None,
        "image": None,
        "description": None,
        "type": "Sweepstakes",
        "ends_at": None,
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

    articles = soup.find_all("article")

    if not articles:
        print("No giveaway articles found.")
        return None

    print(f"Found {len(articles)} article(s).")

    for article in articles:

        # ---------------------------------------------------------
        # TITLE
        # ---------------------------------------------------------

        title_tag = article.find("h2")

        if not title_tag:
            continue

        title = title_tag.get_text(
            " ",
            strip=True
        )

        # ---------------------------------------------------------
        # CHECK IF EXPIRED
        # ---------------------------------------------------------

        article_text = article.get_text(
            " ",
            strip=True
        )

        if re.search(
            r"\bexpired\b",
            article_text,
            re.IGNORECASE
        ):
            print(
                f"⏭️ Skipping expired giveaway: {title}"
            )
            continue

        # ---------------------------------------------------------
        # FIND LINK
        # ---------------------------------------------------------

        link = article.find(
            "a",
            href=True
        )

        if not link:
            print(
                f"⚠️ Skipping '{title}': "
                "no link found."
            )
            continue

        url = link.get("href")

        if not url:
            continue

        # Convert relative URL to absolute URL
        if url.startswith("/"):
            url = "https://game.intel.com" + url

        # ---------------------------------------------------------
        # IMAGE
        # ---------------------------------------------------------

        image_tag = article.find("img")

        image = None

        if image_tag:
            image = (
                image_tag.get("src")
                or image_tag.get("data-src")
                or image_tag.get("data-lazy-src")
            )

        if image and image.startswith("/"):
            image = "https://game.intel.com" + image

        # ---------------------------------------------------------
        # DESCRIPTION
        # ---------------------------------------------------------

        description_tag = article.find("p")

        if description_tag:
            description = description_tag.get_text(
                " ",
                strip=True
            )
        else:
            description = ""

        # ---------------------------------------------------------
        # SLUG
        # ---------------------------------------------------------

        slug = url.rstrip("/").split("/")[-1]

        print()
        print("ACTIVE GIVEAWAY FOUND!")
        print(f"Title: {title}")
        print(f"URL: {url}")

        return {
            "slug": slug,
            "title": title,
            "url": url,
            "image": image,
            "description": description,
        }

    # No active giveaway
    print()
    print("No active Intel giveaways found.")
    return None


def get_end_date(url):
    print(f"Fetching giveaway page: {url}")

    response = requests.get(
        url,
        headers=HEADERS,
        timeout=30
    )

    response.raise_for_status()

    soup = BeautifulSoup(
        response.text,
        "lxml"
    )

    text = soup.get_text(
        " ",
        strip=True
    )

    # Example:
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
        giveaway["end_date"]
        .replace(tzinfo=timezone.utc)
        .timestamp()
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

    # Add image only if available
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

    # ---------------------------------------------------------
    # NO ACTIVE GIVEAWAY
    # ---------------------------------------------------------

    if giveaway is None:
        print("Intel currently has no active giveaway.")
        save_no_active_giveaway()
        print("intel.json updated.")
        return

    # ---------------------------------------------------------
    # GET END DATE
    # ---------------------------------------------------------

    giveaway["end_date"] = get_end_date(
        giveaway["url"]
    )

    # ---------------------------------------------------------
    # UPDATE WEBSITE DATA
    # ---------------------------------------------------------

    save_site_data(giveaway)

    print("intel.json updated.")

    # ---------------------------------------------------------
    # CHECK POSTED GIVEAWAYS
    # ---------------------------------------------------------

    data = load_posted()

    seen = set(
        data.get("seen", [])
    )

    if giveaway["slug"] in seen:
        print("Already posted.")
        return

    # ---------------------------------------------------------
    # NEW GIVEAWAY
    # ---------------------------------------------------------

    print()
    print("================================")
    print("NEW GIVEAWAY FOUND!")
    print(giveaway["title"])
    print(giveaway["url"])
    print("================================")
    print()

    # ---------------------------------------------------------
    # SEND DISCORD
    # ---------------------------------------------------------

    send_discord(giveaway)

    # ---------------------------------------------------------
    # MARK AS POSTED
    # ---------------------------------------------------------

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
