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

if not article:
    print("No giveaway found.")
    exit()

link = article.find("a", href=True)

title = article.find("h2")
if title:
    title = title.get_text(strip=True)
else:
    title = "Unknown"

url = link["href"] if link else "No URL"

print("=" * 50)
print("Title:", title)
print("URL:", url)
print("=" * 50)
