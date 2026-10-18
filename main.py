
import html
import json
import re
from datetime import datetime, time, timedelta, timezone
from pathlib import Path
from urllib.parse import urlparse

import requests
from bs4 import BeautifulSoup

from config import WEBHOOK_URL, ROLE_ID


API_URL = (
    "https://game.intel.com/us/wp-json/wp/v2/giveaways"
    "?per_page=100"
)
LISTING_URL = "https://game.intel.com/us/giveaways/"

POSTED_FILE = Path("posted.json")
DATA_FILE = Path("intel.json")

HEADERS = {
    "User-Agent": (
        "Mozilla/5.0 (Windows NT 10.0; Win64; x64) "
        "AppleWebKit/537.36 (KHTML, like Gecko) "
        "Chrome/138.0.0.0 Safari/537.36"
    ),
    "Accept": "application/json, text/html",
}


def get_session():
    session = requests.Session()
    session.headers.update(HEADERS)
    return session


def load_posted():
    if not POSTED_FILE.exists():
        return {"seen": []}

    try:
        with POSTED_FILE.open("r", encoding="utf-8") as f:
            data = json.load(f)

        if isinstance(data, dict) and isinstance(
            data.get("seen"), list
        ):
            return data

        raise ValueError("Unexpected posted.json format")

    except (OSError, json.JSONDecodeError, ValueError) as exc:
        # Do not silently reset history and repost old giveaways.
        raise RuntimeError(
            f"Could not safely load posted.json: {exc}"
        ) from exc


def save_posted(data):
    with POSTED_FILE.open("w", encoding="utf-8") as f:
        json.dump(data, f, indent=2, ensure_ascii=False)


def save_site_data(giveaway):
    data = {
        "source": "Intel Gaming Access",
        "status": "active",
        "title": giveaway["title"],
        "url": giveaway["url"],
        "image": giveaway["image"],
        "description": giveaway["description"],
        "type": "Sweepstakes",
        "ends_at": giveaway["end_date"].isoformat(),
        "updated_at": datetime.now(timezone.utc).isoformat(),
    }

    with DATA_FILE.open("w", encoding="utf-8") as f:
        json.dump(data, f, indent=2, ensure_ascii=False)


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
        "updated_at": datetime.now(timezone.utc).isoformat(),
    }

    with DATA_FILE.open("w", encoding="utf-8") as f:
        json.dump(data, f, indent=2, ensure_ascii=False)


def clean_html(value):
    if not value:
        return ""

    return BeautifulSoup(
        html.unescape(value),
        "lxml",
    ).get_text(" ", strip=True)


def fetch_api_giveaways(session):
    print("[Intel] Fetching giveaways from new API...")

    response = session.get(API_URL, timeout=30)
    response.raise_for_status()

    records = response.json()

    if not isinstance(records, list):
        raise RuntimeError("Intel API returned an unexpected response.")

    if not records:
        raise RuntimeError(
            "Intel API returned zero records; refusing to assume "
            "that no giveaways exist."
        )

    print(f"[Intel] API returned {len(records)} record(s).")

    return records


def parse_end_date(page_text):
    # Keep the original pattern and support common sweepstakes wording.
    patterns = [
        r"\bOffer\s+ends?\s*:?\s*"
        r"([A-Za-z]+\s+\d{1,2},?\s+\d{4})",

        r"\bSweepstakes\s+(?:ends?|closes?)\s*:?\s*"
        r"([A-Za-z]+\s+\d{1,2},?\s+\d{4})",

        r"\bGiveaway\s+(?:ends?|closes?)\s*:?\s*"
        r"([A-Za-z]+\s+\d{1,2},?\s+\d{4})",

        r"\b(?:Entry|Entries|Entry period)\s+"
        r"(?:ends?|close|closes)\s*:?\s*"
        r"([A-Za-z]+\s+\d{1,2},?\s+\d{4})",

        r"\bEnds?\s+(?:on\s+)?"
        r"([A-Za-z]+\s+\d{1,2},?\s+\d{4})",
    ]

    for pattern in patterns:
        match = re.search(pattern, page_text, re.IGNORECASE)

        if not match:
            continue

        date_string = re.sub(
            r"\s+",
            " ",
            match.group(1).replace(",", ","),
        ).strip()

        for fmt in ("%B %d, %Y", "%B %d %Y"):
            try:
                parsed = datetime.strptime(date_string, fmt)
                # A date without a time is treated as ending at
                # 23:59:59 UTC on that date.
                return datetime.combine(
                    parsed.date(),
                    time(23, 59, 59),
                    tzinfo=timezone.utc,
                )
            except ValueError:
                continue

    return None


def get_page_details(session, record):
    title = clean_html(record.get("title", {}).get("rendered", ""))

    url = record.get("link", "")

    if not title or not url:
        print("[Intel] Skipping record without title or URL.")
        return None, "unknown"

    # Only fetch pages hosted on the expected Intel website.
    parsed_url = urlparse(url)

    if (
        parsed_url.scheme != "https"
        or parsed_url.hostname != "game.intel.com"
    ):
        print(f"[Intel] Skipping unexpected URL: {url}")
        return None, "unknown"

    print(f"[Intel] Checking: {title}")

    response = session.get(url, timeout=30)
    response.raise_for_status()

    soup = BeautifulSoup(response.text, "lxml")

    # Prefer the main page content to unrelated navigation/footer text.
    main_content = (
        soup.find("main")
        or soup.find("article")
        or soup.body
        or soup
    )

    page_text = main_content.get_text(" ", strip=True)

    # Explicit indicators only; do not infer expiry from publication date.
    expired_patterns = [
        r"\bthis giveaway has ended\b",
        r"\bthis sweepstakes has ended\b",
        r"\bgiveaway is expired\b",
        r"\bsweepstakes is expired\b",
        r"\bentries are closed\b",
        r"\bentry period has ended\b",
    ]

    if any(
        re.search(pattern, page_text, re.IGNORECASE)
        for pattern in expired_patterns
    ):
        print(f"[Intel] Skipping ended giveaway: {title}")
        return None, "expired"

    end_date = parse_end_date(page_text)

    if end_date is None:
        print(
            f"[Intel] Cannot verify end date for '{title}'. "
            "Skipping this record."
        )
        return None, "unknown"

    now = datetime.now(timezone.utc)

    if end_date <= now:
        print(f"[Intel] Giveaway has ended: {title}")
        return None, "expired"

    yoast = record.get("yoast_head_json") or {}
    images = yoast.get("og_image") or []

    image = None

    if images and isinstance(images[0], dict):
        image = images[0].get("url")

    if not image:
        featured = soup.find("meta", property="og:image")
        if featured:
            image = featured.get("content")

    description = clean_html(
        record.get("excerpt", {}).get("rendered", "")
    )

    if not description:
        description = clean_html(
            record.get("content", {}).get("rendered", "")
        )

    giveaway = {
        "id": str(record.get("id", "")),
        "slug": record.get("slug", ""),
        "title": title,
        "url": url,
        "image": image,
        "description": description,
        "end_date": end_date,
    }

    print(f"[Intel] Verified active: {title}")
    print(f"[Intel] Ends: {end_date.isoformat()}")

    return giveaway, "active"


def get_listing(session):
    records = fetch_api_giveaways(session)

    unknown_count = 0
    expired_count = 0

    # WordPress API returns newest records first by default.
    for record in records:
        title = clean_html(
            record.get("title", {}).get("rendered", "")
        )

        # Ignore obvious non-sweepstakes promotional articles.
        if not re.search(
            r"\b(sweepstakes|giveaway)\b",
            title,
            re.IGNORECASE,
        ):
            print(f"[Intel] Skipping non-sweepstakes: {title}")
            continue

        giveaway, status = get_page_details(session, record)

        if status == "active":
            return giveaway

        if status == "expired":
            expired_count += 1
        else:
            unknown_count += 1

    if unknown_count:
        # We cannot claim there are no active giveaways if some
        # pages could not be verified.
        raise RuntimeError(
            f"Could not verify {unknown_count} giveaway page(s). "
            "Keeping intel.json unchanged to avoid a false inactive status."
        )

    print(
        f"[Intel] No verified active giveaways. "
        f"Ended records checked: {expired_count}"
    )

    return None


def send_discord(giveaway):
    if not WEBHOOK_URL:
        raise RuntimeError("WEBHOOK_URL is not configured.")

    if not ROLE_ID:
        print("[Intel] ROLE_ID is empty; no role will be mentioned.")

    timestamp = int(giveaway["end_date"].timestamp())

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
            "icon_url": "https://files.catbox.moe/qttqpy.png",
        },
    }

    if giveaway.get("image"):
        embed["image"] = {"url": giveaway["image"]}

    payload = {
        "content": f"<@&{ROLE_ID}>" if ROLE_ID else "",
        "embeds": [embed],
    }

    print("[Intel] Sending Discord notification...")

    response = requests.post(
        WEBHOOK_URL,
        json=payload,
        timeout=30,
    )
    response.raise_for_status()

    print("[Intel] Discord notification sent.")


def main():
    print("=== Intel Giveaway Notifier ===")

    session = get_session()
    posted_data = load_posted()
    seen = set(str(item) for item in posted_data.get("seen", []))

    # Fetch and verify before changing intel.json.
    giveaway = get_listing(session)

    if giveaway is None:
        save_no_active_giveaway()
        print("[Intel] intel.json updated: inactive.")
        return

    save_site_data(giveaway)
    print("[Intel] intel.json updated.")

    # Use the slug for compatibility with your existing history.
    identifier = giveaway["slug"]

    if not identifier:
        identifier = giveaway["id"]

    if identifier in seen:
        print("[Intel] Already posted; no duplicate notification.")
        return

    print()
    print("================================")
    print("NEW GIVEAWAY FOUND!")
    print(giveaway["title"])
    print(giveaway["url"])
    print("================================")
    print()

    send_discord(giveaway)

    seen.add(identifier)

    save_posted({"seen": sorted(seen)})

    print("[Intel] posted.json updated.")
    print("[Intel] Done!")


if __name__ == "__main__":
    main()
