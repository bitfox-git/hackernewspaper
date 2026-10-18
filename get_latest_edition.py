import re
from bs4 import BeautifulSoup
from sys import exit, stderr
from urllib.request import urlopen, Request
from fake_useragent import UserAgent

HACKERNEWSLETTER_URL = (
    "https://buttondown.com/hacker-newsletter/archive/"
)


def fetch(url):
    header = {"User-Agent": str(UserAgent().random)}

    try:
        with urlopen(Request(url, headers=header)) as response:
            return response.read().decode("utf-8")
    except Exception as e:
        print(f"Unable to fetch {url}: {e}", file=stderr)
        return None


html = fetch(HACKERNEWSLETTER_URL)
if html is None:
    exit(1)

soup = BeautifulSoup(html, "html.parser")

parentElement = soup.find("div", class_="email-list")
if parentElement is None:
    print("No email-list found on the archive page", file=stderr)
    exit(1)

weekly_number = None
for title in parentElement.find_all("div", class_="email-title"):
    # e.g. "Hacker Newsletter #814"
    match = re.search(r"#(\d+)", title.get_text())
    if match:
        weekly_number = match.group(1)
        break

if weekly_number is None:
    print("No edition number found on the archive page", file=stderr)
    exit(1)

# NOTE: Rigging is possible for getting editions that have been missed before, type number here to rig
print(weekly_number)
