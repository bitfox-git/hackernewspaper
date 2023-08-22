from bs4 import BeautifulSoup
from playwright.sync_api import sync_playwright
from pythumb import Thumbnail
import urllib.request
from trafilatura import extract, extract_metadata


import re

# download the html from a given url 
def download_html(url):
    with urllib.request.urlopen(url) as response:
        html = response.read()
    return html


# use BeautifulSoup to parse the html
def parse_html(html):
    soup = BeautifulSoup(html, 'html.parser')
    return soup


# in the soup find the table with id="header" and look for the first <p> tag
# int that <p> return the innertext
def get_header(soup):
    header = soup.find(id="header")
    return header.p.get_text()

class article:
    def __init__(self, mainurl, title, text, subtext, suburl): 
        self.mainurl = mainurl
        self.title = title
        self.text = text
        self.subtext = subtext
        self.suburl = suburl
    def __str__(self):
        return self.mainurl + "-" + self.title + "-" + self.text + "-" + self.subtext + "-" + self.suburl

def get_articles(soup):

    articles = []
    content = soup.find(id="content")
    #all content starts with a h2
    for h2element in content.find_all("h2"):
        print(h2element.get_text())
        for nextSibling in h2element.next_siblings:
            if nextSibling.name == "h2":
                break
            if nextSibling.name == "p":
                
                a = nextSibling.find("a")
                mainurl = a.get("href")
                title = a.get("title")
                text = a.get_text()
                
                span = nextSibling.find("span") 
                if span is not None:
                    subtext = span.text
                    suburla = span.find("a") 
                    if suburla is not None: 
                        suburl = suburla.get("href")
                art = article(mainurl, title, text, subtext, suburl)    
                articles.append(art)
                #print(art)       
    return articles

#check if url is a youtube url using the regex ^(http(s)?:\/\/)?((w){3}.)?youtu(be|.be)?(\.com)?\/.+
def is_youtube_url(url):
    regex = "^(http(s)?:\/\/)?((w){3}.)?youtu(be|.be)?(\.com)?\/.+"
    if re.match(regex, url):
        return True
    else:
        return False


#generate screenshot of the url using playwright
def generate_screenshot(index, url, browser):
    page = browser.new_page()
    page.goto(url)
    #TODO Solve the cookie accept problem 
    page.screenshot(path=f'{index}.png')

html = download_html("https://mailchi.mp/hackernewsletter/665")

soup = parse_html(html)

header = get_header(soup)
print(header)

articles = get_articles(soup)

with sync_playwright() as p:
    browser = p.chromium.launch()
    for index, art in enumerate(articles):
        #generate_screenshot(index, art.mainurl, browser=browser)
        if (is_youtube_url(art.mainurl)):
          
            t = Thumbnail(art.mainurl)
            t.fetch()
            t.save(dir=".", filename=f'{index}', overwrite=True)
        else:
            print("not a youtube url")
    browser.close()

# parse the content of each link

for index, art in enumerate(articles):
    sitecontent= download_html(art.mainurl)
    data  = extract(sitecontent)
    metadata = extract_metadata(sitecontent)
    x =42 

