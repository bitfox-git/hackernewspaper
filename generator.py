import logging
import os
import re
import sys
from bs4 import BeautifulSoup

import config
from url_handlers import (
    DefaultHandler,
    GithubHandler,
    PDFHandler,
    YoutubeHandler,
    download_html,
    minimal_item,
)

log = logging.getLogger("hackernewspaper")

ARCHIVE_URL = "https://buttondown.com/hacker-newsletter/archive/"

PATH_JINJA2 = "."
PATH_TEMPLATE_RELATIVE_TO_PATH_JINJA2 = "template.tex"
PATH_OUTPUT_TEX = "output.tex"

# a regular desktop Chrome, headless Chromium's own user agent gets blocked by more sites
USER_AGENT = "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/141.0.0.0 Safari/537.36"


# use BeautifulSoup to parse the html version of the newsletter
def parse_html(html):
    soup = BeautifulSoup(html, 'html.parser')
    return soup


# in the soup find the table with id="header" and look for the first <p> tag
# in the <p> return the innertext
def get_header(soup):
    header = soup.find(id="header")
    if header is None or header.p is None:
        return ""
    return header.p.get_text()

def parse_header(header):
    #header could be sometthing like a quote "The best way to predict the future is to invent it. // Alan Kay"
    #the author is separated by // from the quote
    header = " ".join(header.split())
    split = header.split("//")
    if len(split) == 2:
        return split[0].strip(), split[1].strip()
    else:
        return header, ""

# "\n\n    #\n  \n  Sponsor\n" -> "#Sponsor"
def clean_category(text):
    return re.sub(r"^#\s+", "#", " ".join(text.split()))

class article:
    def __init__(self, mainurl, title, text, subtext, suburl, category):
        self.mainurl = mainurl
        self.title = title
        self.text = text
        self.subtext = subtext
        self.suburl = suburl
        self.category = category
    def __str__(self):
        return self.mainurl + "-" + self.title + "-" + self.text + "-" + self.subtext + "-" + self.suburl

def get_articles(soup):
    categories =[]
    articles = []

    content = soup.find(id="content")
    #all content starts with a h2
    for h2element in content.find_all("h2"):
        category = clean_category(h2element.get_text())
        found = 0
        for nextSibling in h2element.next_siblings:
            if nextSibling.name == "h2":
                break
            if nextSibling.name == "p":

                a = nextSibling.find("a")
                if a is not None:
                    mainurl = a.get("href")
                    title = a.get("title")
                    text = " ".join(a.get_text().split())
                    subtext =""
                    suburl = ""
                    span = nextSibling.find("span")
                    if span is not None:
                        subtext = span.text
                        suburla = span.find("a")
                        if suburla is not None:
                            suburl = suburla.get("href")
                    art = article(mainurl, title, text, subtext, suburl, category)
                    articles.append(art)
                    found += 1
        # a category without articles would only render an empty section
        if found > 0:
            categories.append(category)
    return articles, categories


# editions live at /archive/<N>/, the older /archive/hacker-newsletter-<N> slug is kept as a fallback
def download_edition(issue, browser):
    for url in [f"{ARCHIVE_URL}{issue}/", f"{ARCHIVE_URL}hacker-newsletter-{issue}"]:
        html = download_html(url, browser)
        if html is not None:
            soup = parse_html(html)
            if soup.find(id="content") is not None:
                return soup
        log.warning("No edition content found at %s", url)
    return None


handlers = [YoutubeHandler(), PDFHandler(), GithubHandler(), DefaultHandler()]

# one bad link never kills an edition: a failing handler falls back to the
# DefaultHandler, and if that fails too the article is printed with title and link only
def process_article(index, art, browser):
    handler = next(h for h in handlers if h.test(art))
    try:
        return handler.work(index, art, browser)
    except Exception:
        log.exception("%s failed for article %d (%s)", type(handler).__name__, index, art.mainurl)
    if not isinstance(handler, DefaultHandler):
        try:
            return DefaultHandler().work(index, art, browser)
        except Exception:
            log.exception("DefaultHandler failed for article %d (%s)", index, art.mainurl)
    return minimal_item(art)


def build_paper(issue, browser):
    soup = download_edition(issue, browser)
    if soup is None:
        raise RuntimeError(f"Unable to download edition {issue}")

    articles, categories = get_articles(soup)
    log.info("Edition %s: %d categories, %d articles", issue, len(categories), len(articles))

    # parse the content of each link
    newsitems = []
    for index, art in enumerate(articles):
        newsitems.append(process_article(index, art, browser))
        log.info("New article indexed: %s", newsitems[-1]["title"])

    quoteLine, quoteAuthor = parse_header(get_header(soup))

    return {
        'data': {"issue": issue, "quoteLine": quoteLine, "quoteAuthor": quoteAuthor},
        'categories': categories,
        'newsitems': newsitems,
    }


def render(dict_vals, path=PATH_OUTPUT_TEX):
    # Do the latex stuff, latexbuild escapes the template variables
    from latexbuild import render_latex_template

    log.info("PDF template creation started")
    latexresult = render_latex_template(
        PATH_JINJA2,
        PATH_TEMPLATE_RELATIVE_TO_PATH_JINJA2,
        dict_vals
        )

    # store latexresult in a file using utf8 encoding
    with open(path, "w", encoding="utf-8") as f:
        f.write(latexresult)
    log.info("PDF template written to %s", path)


def main(argv):
    logging.basicConfig(level=logging.INFO, format="%(levelname)s %(message)s")
    if len(argv) < 2:
        sys.exit("Usage: python generator.py <issue number>")

    config.configure(argv[1])
    os.makedirs(config.asset_dir, exist_ok=True)

    from playwright.sync_api import sync_playwright

    with sync_playwright() as p:
        browser = p.chromium.launch()
        # one desktop browser context for the whole edition, handlers open their pages in it
        context = browser.new_context(
            user_agent=USER_AGENT,
            viewport={"width": 1280, "height": 800},
        )
        try:
            dict_vals = build_paper(config.ISSUE, context)
        finally:
            browser.close()

    render(dict_vals)


if __name__ == "__main__":
    main(sys.argv)
