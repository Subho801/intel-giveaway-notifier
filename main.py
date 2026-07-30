import re
from datetime import datetime

import requests
from bs4 import BeautifulSoup

LISTING_URL = "https://game.intel.com/us/giveaways/"

headers = {
    "User-Agent": (
        "Mozilla/5.0 (Windows NT 10.0; Win64; x64) "
        "AppleWebKit/537.36 (KHTML, like Gecko) "
        "Chrome/138.0.0.0 Safari/537.36"
    )
}

# ------------------------
# Listing page
# ------------------------

listing = requests.get(LISTING_URL, headers=headers, timeout=30)
listing.raise_for_status()

soup = BeautifulSoup(listing.text, "lxml")

article = soup.find("article")

if article is None:
    raise Exception("No giveaway found.")

title = article.find("h2").get_text(strip=True)
url = article.find("a", href=True)["href"]
image = article.find("img")["src"]
description = article.find("p").get_text(" ", strip=True)

# ------------------------
# Giveaway page
# ------------------------

page = requests.get(url, headers=headers, timeout=30)
page.raise_for_status()

detail = BeautifulSoup(page.text, "lxml")

text = detail.get_text(" ", strip=True)

match = re.search(
    r"Offer ends ([A-Za-z]+ \d{1,2}, \d{4})",
    text
)

if not match:
    raise Exception("End date not found.")

end_date = match.group(1)

end_dt = datetime.strptime(end_date, "%B %d, %Y")

print("=" * 60)
print("TITLE:")
print(title)
print()

print("END DATE:")
print(end_date)
print()

print("DATETIME:")
print(end_dt)

print("=" * 60)
