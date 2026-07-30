import re
from datetime import datetime

import requests
from bs4 import BeautifulSoup

LISTING_URL = "https://game.intel.com/us/giveaways/"

HEADERS = {
    "User-Agent": (
        "Mozilla/5.0 (Windows NT 10.0; Win64; x64) "
        "AppleWebKit/537.36 (KHTML, like Gecko) "
        "Chrome/138.0.0.0 Safari/537.36"
    )
}


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

    match = re.search(
        r"Offer ends ([A-Za-z]+ \d{1,2}, \d{4})",
        text,
    )

    if not match:
        raise Exception("End date not found.")

    end_date = match.group(1)

    end_dt = datetime.strptime(end_date, "%B %d, %Y")

    return end_dt


def main():
    giveaway = get_listing()

    end_date = get_end_date(giveaway["url"])

    print("=" * 60)
    print(giveaway["title"])
    print()
    print(giveaway["slug"])
    print()
    print(giveaway["url"])
    print()
    print(giveaway["image"])
    print()
    print(giveaway["description"])
    print()
    print(end_date)
    print("=" * 60)


if __name__ == "__main__":
    main()
