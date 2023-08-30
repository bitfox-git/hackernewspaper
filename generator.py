import os , sys , re
from bs4 import BeautifulSoup
from playwright.sync_api import sync_playwright
from pythumb import Thumbnail
import urllib.request
from trafilatura import extract, extract_metadata
from fake_useragent import UserAgent

#read the first argument from the command line and use it as the issue number

if len(sys.argv) > 1:
    ISSUE = sys.argv[1]
else:
    ISSUE = "665_9" 

paperdata = {
    "issue": ISSUE
}

ua = UserAgent()

# download the html from a given url 
def download_html(url):
    header = {'User-Agent':str(ua.random)}
    try:
        with urllib.request.urlopen(urllib.request.Request(url, headers=header)) as response:
        # check if the request was successful
            html = response.read()
            #convert to string
            html = html.decode("utf-8")
    except urllib.error.HTTPError as e:
        html = "Could not download this url.."
    return html


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
                    art = article(mainurl, title, text, subtext, suburl,category)    
                    articles.append(art)
                    print(art)       
    return articles, categories

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


html = download_html("https://mailchi.mp/hackernewsletter/"+ISSUE)
soup = parse_html(html)
header = get_header(soup)

articles, categories = get_articles(soup)

with sync_playwright() as p:
    browser = p.chromium.launch()
    for index, art in enumerate(articles):
        
        #if file exists skip
        if os.path.isfile(f'{index}.png') or os.path.isfile(f'{index}.jpg'):
            continue

        if (is_youtube_url(art.mainurl)):    
            # youtube stores it as JPG  
            t = Thumbnail(art.mainurl)
            t.fetch()
            t.save(dir=".", filename=f'{index}', overwrite=True)
        else:
            try:
                generate_screenshot(index, art.mainurl, browser)
            except:
                #TODO : create a timeout/404 default jpg.
                storeAFakeUrlLater=True
    browser.close()

# parse the content of each link

newsitems = []

# load or download art.mainurl contents
def loadordownload(index, art):
    fname = f'{index}.html'
    if os.path.isfile(fname):
        with open(fname, encoding="utf-8") as f:
            sitecontent = f.read()
    else:
        sitecontent = download_html(art.mainurl)
        with open(fname, "w", encoding="utf-8") as f:
            f.write(sitecontent)
    return sitecontent

def splitFirstSentenceParagraph(data):
    # find the indexes of all occurences of a dot, question mark or exclamation mark
    dots = [i for i, ltr in enumerate(data) if ltr in [".", "?", "!"] and i<200]
    # find the highest index that is smaller than 200 and make sure the max is not taken over an empty set
    #dots2 = [i for i in dots if i < 200]
    if (len(dots) > 0):
        firstdot = max(dots)
        if firstdot > 10:
            return data[:firstdot+1], data[firstdot+1:]
    return None, data

def removeEmptyLines(data):
    # remove empty lines
    lines = data.split("\n")
    lines = [line for line in lines if line.strip() != ""]
    return "\n".join(lines)

# map the site to a fontawesome symbol
def faSymbolPerHostname(hostname):
    match hostname:
        case "youtube.com": return "Youtube"
        case "flikr.com": return "Flikr"
        case "github.com": return "Github"
        case "medium.com": return "Medium"
        case _ : return "Globe"

def isValidDictItem(item, dict):
    return item in dict and dict[item] is not None and dict[item] != ""


for index, art in enumerate(articles):
    sitecontent= loadordownload(index, art)
    data  = extract(sitecontent)

    if data is None:
        data = ""
    # remove empty lines
    data = removeEmptyLines(data)
    # temp remove all emoji stuff, until found decent solutions in latex
    # solved : no longer necessary with Tectonic Typesetting.
    # data = removeUnicode(data)
    # data can contain a lot of characters, we only want the first 1500
    data = data[0:min(1500, len(data))]
    # santize the data by removing % and / 
    data = data.replace("%", "")
    data = data.replace("\\", "")
    firstSentence, data = splitFirstSentenceParagraph(data)

    # the string art.title might contain text and numbers  of the format "Votes: 521 Comments: 83"
    # we want to extract the numbers
    votes= 0
    comments = 0
    if (art.title is not None):
        numbers = re.findall(r'\d+', art.title) 
        if (len(numbers) ==2):
            votes = int(numbers[0])
            comments = int(numbers[1])

    metadata = extract_metadata(sitecontent)
    if metadata is None:
        metadatadict   = {}
    else:
        metadatadict = metadata.as_dict()
    
    # we extend the metadata with the votes and comments counts if they are > 0
    if (votes > 0):
        metadatadict["votes"] = votes
    if (comments > 0):
        metadatadict["comments"] = comments

    #image url can be either a png or a jpg
    if os.path.isfile(f'{index}.png'):
        image = f'{index}.png'
    
    if os.path.isfile(f'{index}.jpg'):
        image = f'{index}.jpg'

    # fall back 
    image = "notfound.png"

    #potential interested metadata fields are: author, date, image, sitename
    #not used , but for future reference : 
    # pagetype [object, article, website ]
    # description
    # categories and tags

    newsproperties = []
    
    if (isValidDictItem("author", metadatadict)): 
        newsproperties.append({ "symbol": "User", "value" : metadatadict["author"], "url": None})
    if (isValidDictItem("date", metadatadict)):
        newsproperties.append({ "symbol": "Calendar", "value" : metadatadict["date"], "url": None})
    if (isValidDictItem("hostname", metadatadict)):
        newsproperties.append({ "symbol": faSymbolPerHostname(metadatadict["hostname"]), "value" : metadatadict["hostname"], "url": None})
    if ("votes" in metadatadict):
        newsproperties.append({ "symbol": "ThumbsOUp", "value" : metadatadict["votes"], "url": art.suburl})
    if ("comments" in metadatadict):
        newsproperties.append({ "symbol": "Comments", "value" : metadatadict["comments"], "url": art.suburl})

    if (is_youtube_url(art.mainurl)): 
        #determine the length of the video as a properties
        #first read is that you would need a youtube api key to get this information
        skipthisForNow = True
    

    newsitems.append({"title": art.text, 
                      "url" : art.mainurl,
                      "image": image, 
                      "category" : art.category,
                      "firstline": firstSentence,
                      "content": data, 
                      "properties": newsproperties })

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
from latexbuild import build_pdf, build_html, build_docx, render_latex_template

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
    
