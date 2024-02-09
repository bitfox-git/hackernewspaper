import os , sys , re
from bs4 import BeautifulSoup
from playwright.sync_api import sync_playwright
from pythumb import Thumbnail
import urllib.request
import urllib.parse
from trafilatura import extract, extract_metadata
from fake_useragent import UserAgent
from config import asset_dir,ISSUE

from url_handlers import DefaultHandler, download_html

os.makedirs(asset_dir, exist_ok=True)

ua = UserAgent()

paperdata = {
    "issue": ISSUE
}

# use BeautifulSoup to parse the html version of the newsletter
def parse_html(html):
    soup = BeautifulSoup(html, 'html.parser')
    return soup


# in the soup find the table with id="header" and look for the first <p> tag
# in the <p> return the innertext
def get_header(soup):
    header = soup.find(id="header")
    if header is None:
        return ""
    return header.p.get_text()

def parse_header(header):
    #header could be sometthing like a quote "The best way to predict the future is to invent it. // Alan Kay"
    #the author is separated by // from the quote
    split = header.split("//")
    if len(split) == 2:
        return split[0], split[1]
    else:
        return header, ""

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
        category = h2element.get_text()
        categories.append(category)
        #print(h2element.get_text())
        for nextSibling in h2element.next_siblings:
            if nextSibling.name == "h2":
                break
            if nextSibling.name == "p":
                
                a = nextSibling.find("a")
                if a is not None:
                    mainurl = a.get("href")
                    title = a.get("title")
                    text = a.get_text()
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
                    print(art)       
    return articles, categories






html = download_html("https://mailchi.mp/hackernewsletter/"+ISSUE)
soup = parse_html(html)
header = get_header(soup)

articles, categories = get_articles(soup)

# parse the content of each link
newsitems = []




handlers = [DefaultHandler()]

with sync_playwright() as p:
    browser = p.chromium.launch()
    for index, art in enumerate(articles):
        for handler in handlers:
            if handler.test(art):
                newsitems.append(handler.work(index, art, browser))
                break
    browser.close()

quoteLine, quoteAuthor = parse_header(header)

# remove any line breaks from quoteLine
quoteLine = quoteLine.replace("\n", "")

paperdata["quoteLine"] = quoteLine
paperdata["quoteAuthor"] = quoteAuthor


DICT_VALS = {
    'data' : paperdata,
    'categories': categories,
    'newsitems': newsitems
    }

# Do the latex stuff
from latexbuild import render_latex_template

PATH_JINJA2 = "."
PATH_TEMPLATE_RELATIVE_TO_PATH_JINJA2 = "template.tex"
PATH_OUTPUT_PDF = "MYOUTPUTFILE.pdf"

# Build Jinja2 template, compile result latex, move compiled file to output path,
# and clean up all intermediate files
#build_pdf(PATH_JINJA2, PATH_TEMPLATE_RELATIVE_TO_PATH_JINJA2, PATH_OUTPUT_PDF, DICT_VALS)

latexresult = render_latex_template(
    PATH_JINJA2,
    PATH_TEMPLATE_RELATIVE_TO_PATH_JINJA2,
    DICT_VALS
    )

# store latexresult in a file using utf8 encoding
with open("output.tex", "w", encoding="utf-8") as f:
    f.write(latexresult)
    
