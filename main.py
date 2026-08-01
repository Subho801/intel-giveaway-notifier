import json
import re
from datetime import datetime
from pathlib import Path
from datetime import timezone

import requests
from bs4 import BeautifulSoup

from config import WEBHOOK_URL, ROLE_ID

LISTING_URL = "https://game.intel.com/us/giveaways/"
POSTED_FILE = Path("posted.json")

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
DATA_FILE = Path("intel.json")


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
        ).isoformat()
    }

    with DATA_FILE.open("w", encoding="utf-8") as f:
        json.dump(data, f, indent=2)

def get_listing():
    response = requests.get(LISTING_URL, headers=HEADERS, timeout=30)
    response.raise_for_status()

    soup = BeautifulSoup(response.text, "lxml")

    article = soup.find("article")

    if article is None:
        raise Exception("No giveaway found.")

    title = article.find("h2").get_text(strip=True)
    url = article.find("a", href=True)["href"]
    image = article.find("img")["src"]
    description = article.find("p").get_text(" ", strip=True)

    slug = url.rstrip("/").split("/")[-1]

    return {
        "slug": slug,
        "title": title,
        "url": url,
        "image": image,
        "description": description,
    }


def get_end_date(url):
    response = requests.get(url, headers=HEADERS, timeout=30)
    response.raise_for_status()

    soup = BeautifulSoup(response.text, "lxml")

    text = soup.get_text(" ", strip=True)

    match = re.search(r"Offer ends ([A-Za-z]+ \d{1,2}, \d{4})", text)

    if not match:
        raise Exception("End date not found.")

    return datetime.strptime(match.group(1), "%B %d, %Y")


def send_discord(giveaway):
    timestamp = int(giveaway["end_date"].timestamp())

    embed = {
        "author": {
            "name": "Intel Gaming Access",
            "url": LISTING_URL,
            "icon_url": "https://file.garden/afbSsuts32dZ5wSl/Intel-logo-2022.png"
        },
        "title": giveaway["title"],
        "url": giveaway["url"],
        "color": 0x0071C5,
        "image": {
            "url": giveaway["image"]
        },
        "fields": [
            {
                "name": "Ends",
                "value": f"<t:{timestamp}:F>\n<t:{timestamp}:R>",
                "inline": True
            },
            {
                "name": "Type",
                "value": "Sweepstakes 🎟",
                "inline": True
            }
        ],
        "footer": {
            "text": "Subho's Intel Gaming Informer",
            "icon_url": "https://files.catbox.moe/qttqpy.png"
        }
    }

    payload = {
        "content": f"<@&{ROLE_ID}>" if ROLE_ID else "",
        "embeds": [embed]
    }

    response = requests.post(
        WEBHOOK_URL,
        json=payload,
        timeout=30
    )

    response.raise_for_status()

    print("Discord notification sent.")


def main():
    giveaway = get_listing()
    giveaway["end_date"] = get_end_date(giveaway["url"])

    save_site_data(giveaway)

    data = load_posted()
    seen = set(data["seen"])

    if giveaway["slug"] in seen:
        print("Already posted.")
        return

    print("NEW GIVEAWAY FOUND!")
    print(giveaway["title"])

    send_discord(giveaway)

    seen.add(giveaway["slug"])

    save_posted({
        "seen": sorted(seen)
    })

    print("posted.json updated.")


if __name__ == "__main__":
    main()
