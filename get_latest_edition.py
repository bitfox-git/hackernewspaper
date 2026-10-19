import re
from bs4 import BeautifulSoup
from sys import exit, stderr
from urllib.request import urlopen, Request
from fake_useragent import UserAgent

HACKERNEWSLETTER_URL = "https://buttondown.com/hacker-newsletter/archive/"


def fetch(url):
    header = {"User-Agent": str(UserAgent().random)}

    try:
        with urlopen(Request(url, headers=header)) as response:
            return response.read().decode("utf-8")
    except Exception as e:
        print(f"Unable to fetch {url}: {e}", file=stderr)
        return None


def parse_latest_edition(html):
    """Return the newest edition number on the archive page as a string, or None."""
    soup = BeautifulSoup(html, "html.parser")

    parentElement = soup.find("div", class_="email-list")
    if parentElement is None:
        print("No email-list found on the archive page", file=stderr)
        return None

    for title in parentElement.find_all("div", class_="email-title"):
        # e.g. "Hacker Newsletter #814"
        match = re.search(r"#(\d+)", title.get_text())
        if match:
            return match.group(1)

    print("No edition number found on the archive page", file=stderr)
    return None


if __name__ == "__main__":
    html = fetch(HACKERNEWSLETTER_URL)
    weekly_number = parse_latest_edition(html) if html is not None else None
    if weekly_number is None:
        exit(1)

    # NOTE: Rigging is possible for getting editions that have been missed before, type number here to rig
    print(weekly_number)
