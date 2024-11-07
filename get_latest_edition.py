from bs4 import BeautifulSoup
from sys import exit
from urllib.request import urlopen, Request
from fake_useragent import UserAgent

HACKERNEWSLETTER_URL = (
    "https://buttondown.com/hacker-newsletter/archive"
)


def fetch(url):
    header = {"User-Agent": str(UserAgent().random)}

    try:
        with urlopen(Request(url, headers=header)) as response:
            return response.read().decode("utf-8")
    except:
        return None


soup = BeautifulSoup(fetch(HACKERNEWSLETTER_URL), "html.parser")

newsletter_links = soup.find_all("li", class_="campaign")

weekly_number = None
for link in newsletter_links:
    newsletter_text = link.a.get_text()
    if "#" in newsletter_text:
        weekly_number = newsletter_text.split("#")[-1]
        break

if weekly_number == None:
    exit(1)

# NOTE: Rigging is possible for getting editions that have been missed before, type number here to rig
print(weekly_number)