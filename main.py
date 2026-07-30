import requests
from bs4 import BeautifulSoup

URL = "https://game.intel.com/us/giveaways/"

headers = {
    "User-Agent": (
        "Mozilla/5.0 (Windows NT 10.0; Win64; x64) "
        "AppleWebKit/537.36 (KHTML, like Gecko) "
        "Chrome/138.0.0.0 Safari/537.36"
    )
}

response = requests.get(URL, headers=headers, timeout=30)
response.raise_for_status()

soup = BeautifulSoup(response.text, "lxml")

article = soup.find("article")

if article is None:
    raise Exception("No giveaway found.")

# ------------------------
# Title
# ------------------------

title = article.find("h2")
title = title.get_text(strip=True) if title else "Unknown"

# ------------------------
# URL
# ------------------------

link = article.find("a", href=True)
url = link["href"] if link else ""

# ------------------------
# Image
# ------------------------

img = article.find("img")
image = img["src"] if img else ""

# ------------------------
# Description
# ------------------------

description = article.find("p")
description = description.get_text(" ", strip=True) if description else ""

print("=" * 60)
print("TITLE:")
print(title)
print()

print("URL:")
print(url)
print()

print("IMAGE:")
print(image)
print()

print("DESCRIPTION:")
print(description)
print("=" * 60)
