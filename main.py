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
# Get listing page
# ------------------------

listing = requests.get(LISTING_URL, headers=headers, timeout=30)
listing.raise_for_status()

soup = BeautifulSoup(listing.text, "lxml")

article = soup.find("article")

if article is None:
    raise Exception("No giveaway found.")

title = article.find("h2").get_text(strip=True)
url = article.find("a", href=True)["href"]

print("Listing found:")
print(title)
print(url)
print()

# ------------------------
# Open giveaway page
# ------------------------

page = requests.get(url, headers=headers, timeout=30)
page.raise_for_status()

detail = BeautifulSoup(page.text, "lxml")

text = detail.get_text("\n", strip=True)

print("=" * 60)
print(text[:5000])
print("=" * 60)
