import os , re
import urllib.request
import urllib.parse
from trafilatura import extract, extract_metadata
from fake_useragent import UserAgent
from config import asset_dir
import yt_dlp
import json
from pypdf import PdfReader
from PIL import Image
from selenium import webdriver

ua = UserAgent()

# download the html from a given url 
def download_html(url):
    options = webdriver.ChromeOptions()
    options.add_argument('--headless')
    browser = webdriver.Chrome(options=options)
    browser.get(url)
    html = browser.page_source
    browser.close()
    return html

#check if url is a youtube url using the regex ^(http(s)?:\/\/)?((w){3}.)?youtu(be|.be)?(\.com)?\/.+
def is_youtube_url(url):
    regex = "^(http(s)?:\/\/)?((w){3}.)?youtu(be|.be)?(\.com)?\/.+"
    return re.match(regex, url)

# load or download art.mainurl contents
def loadordownload(index, art):
    fname = f'{asset_dir}{index}.html'
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

#generate screenshot of the url using playwright
def generate_screenshot(index, url, browser):
    page = browser.new_page()
    page.goto(url)
    #TODO Solve the cookie accept problem 
    page.screenshot(path=f'{asset_dir}{index}.png')
    page.close()

class UrlHandler(): 
    def test(self, art) -> bool:
        return False;
    def work(self, index, art):
        pass

def isValidDictItem(item, dict):
    return item in dict and dict[item] is not None and dict[item] != ""

# map the site to a fontawesome symbol
# https://www.comet.com/standardizing-experiment/eda-hackernews-data/reports/standardizing-the-experiment-exploring-the-hackernews-dataset
def faSymbolPerHostname(hostname: str):
    match hostname:
        case "flikr.com": return "Flikr"
        case "github.com": return "Github"
        case "medium.com": return "Medium"
        case "twitter.com": return "Twitter"
        case "nytimes.com": return "NewspaperO"
        case "wikipedia.org": return "WikipediaW"
        case "reddit.com": return "Reddit"
        case "ycombinator.com": return "YCombinator"
        # Youtube
        case "youtube.com": return "Youtube"
        case "youtu.be": return "Youtube"
        # Github
        case "github.io": return "Github"
        case "github.com": return "Github"
        case "github.blog": return "Github"
        # News Papers
        case "theguardian.com": return "NewspaperO"
        case "dev.to": return "NewspaperO"
        case "techcrunch.com": return "NewspaperO"
        case "wsj.com": return "NewspaperO"
        case "arstechnica.com": return "NewspaperO"
        case "theverge.com": return "NewspaperO"
        case "bbc.com": return "NewspaperO"
        case "bloomberg.com": return "NewspaperO"
        case "reuters.com": return "NewspaperO"
        # Globe for others
        case _ : return "Globe"

def write(index:int, data):
    with open(f'{asset_dir}{index}.json', 'w', encoding='utf-8') as f:
        json.dump(data, f, ensure_ascii=False, indent=4)
def read(index:int):
    try:
        with open(f'{asset_dir}{index}.json') as data_file:
            return json.load(data_file)
    except:
        return None

def download_bin(url):
    header = {'User-Agent':str(ua.random)}
    try:
        with urllib.request.urlopen(urllib.request.Request(url, headers=header)) as response:
            return response.read()
    except:
        return None

def cached_download(url:str, index:int, ext:str):
    fname = f'{asset_dir}{index}.{ext}'
    if os.path.isfile(fname):
        return True
    else:
        sitecontent = download_bin(url)
        if sitecontent is None:
            return False
        with open(fname, "wb") as f:
            f.write(sitecontent)
        if os.path.isfile(fname):
            return True
    return False


def get_url_extension(url):
    parsed_url = urllib.parse.urlparse(url)
    path = parsed_url.path
    return os.path.splitext(path)[1]


def get_metadata(title: str, metadatadict: dict = {}) -> dict:
    votes = 0
    comments = 0
    if title is not None:
        numbers = re.findall(r"\d+", title)
        if len(numbers) == 2:
            votes = int(numbers[0])
            comments = int(numbers[1])

    if votes > 0:
        metadatadict["votes"] = votes
    if comments > 0:
        metadatadict["comments"] = comments
    return metadatadict


def add_stats(props: list[dict], metadatadict: dict, link: str):
    if "votes" in metadatadict:
        props.append(
            {
                "symbol": "ThumbsOUp",
                "value": metadatadict["votes"],
                "url": link,
            }
        )
    if "comments" in metadatadict:
        props.append(
            {
                "symbol": "Comments",
                "value": metadatadict["comments"],
                "url": link,
            }
        )



def is_github_repo(url):
    pattern = r"^https?://github\.com/[\w.-]+/[\w.-]+(?:\?.*)?$"
    return bool(re.match(pattern, url))


def prep_body(text: str | None):
    if text is None:
        text = ""

    text = text[0 : min(1100, len(text))]

    text = (
        text.replace("%", "")
        .replace("\u001b", "")
        .replace("\u000F", "")
        .replace("\\", "")
    )

    # remove empty lines
    text = removeEmptyLines(text)
    firstSentence, text = splitFirstSentenceParagraph(text)

    return firstSentence, text


# TODO: Fix YoutubeDL problems, the github actions bot fails continuously as it gets flagged by youtube as a bot
class YoutubeHandler():
    def test(self, art):
        return art.mainurl.startswith("https://www.youtube.com/watch?v=")

    def work(self, index, art, browser):
        ydl = yt_dlp.YoutubeDL()
        youtube_dl_working = True

        video_info = read(index)
        if video_info is None:
            try:
                # TODO: Explore other options for extracting metadata, currently seems very hard (but in what way should this work, in earlier editions there is a very limited amount of actual information (for example description is not accurate as is author))
                video_info = ydl.extract_info(art.mainurl, download=False)
                write(index, video_info)
            except:
                print("YoutubeDL failed")
                youtube_dl_working = False

        metadatadict = get_metadata(art.title)

        newsproperties = []

        # Steps if youtube dl works
        if youtube_dl_working:
            firstSentence, data = prep_body(video_info["description"])

            # TODO: Explore other options for extracting thumbnails than youtubedl (its disabled as it downloads full videos(against youtubes guidelines), we dont need that, we only get the thumbnail, upload date and description)
            # There are multiple easily accessible ways to get the thumbnail (Youtube shares the links itself or via NoEmbed) however see if we can bundle it with other video information
            image = "notfound.png"
            if cached_download(video_info["thumbnail"], index, "jpg"):
                image = f"{asset_dir}{index}.jpg"
                # tectonic was being funny with the standard youtube jpg thumbnails so we convert them to PNG and it doesnt complain anymore :)
                im = Image.open(image)
                image = f"{asset_dir}{index}.png"
                im.save(image)


            newsproperties.append(
                {"symbol": "User", "value": video_info["channel"], "url": None}
            )
            upload = video_info["upload_date"]

            newsproperties.append(
                {
                    "symbol": "Calendar",
                    "value": f"{upload[:4]}-{upload[4:6]}-{upload[6:]}",
                    "url": None,
                }
            )

        # Steps if youtube dl fails
        else:
            header = {'User-Agent':str(ua.random)}
            metadata_url = f"https://youtube.com/oembed?url={art.mainurl}&format=json"
            request = urllib.request.Request(metadata_url, headers=header)
            with urllib.request.urlopen(request).read() as metadata:
                metadata_json = metadata.json()
            author = metadata_json["author_name"]
            author_url = metadata_json["author_url"]
            if author and author_url is not None:
                newsproperties.append(
                    {"symbol": "User", "value": author, "url": author_url}
                )
            
            thumbnail_url = metadata_json["thumbnail_url"]
            if thumbnail_url is not None:
                if cached_download(thumbnail_url, index, "jpg"):
                    thumbnail_url = f"{asset_dir}{index}.jpg"
                    im = Image.open(thumbnail_url)
                    thumbnail_url = f"{asset_dir}{index}.png"
                    im.save(thumbnail_url)
                    newsproperties.append(
                        {"symbol": "Thumbnail", "value": thumbnail_url, "url": art.mainurl}
                    )

        newsproperties.append(
            {
                "symbol": faSymbolPerHostname("youtube.com"),
                "value": "youtube.com",
                "url": None,
            }
        )

        add_stats(newsproperties, metadatadict, art.suburl)

        return {
            "title": art.text,
            "url": art.mainurl,
            "image": image,
            "category": art.category,
            "firstline": firstSentence,
            "content": data,
            "properties": newsproperties,
        }




class GithubHandler:
    def test(self, art):
        return is_github_repo(art.mainurl)

    def work(self, index, art, browser):
        # TODO clean this up

        sitecontent = loadordownload(index, art)
        metadata = extract_metadata(sitecontent)
        data = metadata.description + " " + extract(sitecontent)

        firstSentence, data = prep_body(data)

        metadatadict = get_metadata(
            art.title, metadata.as_dict() if metadata is not None else {}
        )

        newsproperties = []

        if isValidDictItem("author", metadatadict):
            newsproperties.append(
                {"symbol": "User", "value": metadatadict["author"], "url": None}
            )
        if isValidDictItem("date", metadatadict):
            newsproperties.append(
                {"symbol": "Calendar", "value": metadatadict["date"], "url": None}
            )
        if isValidDictItem("hostname", metadatadict):
            newsproperties.append(
                {
                    "symbol": faSymbolPerHostname(metadatadict["hostname"]),
                    "value": metadatadict["hostname"],
                    "url": None,
                }
            )

        add_stats(newsproperties, metadatadict, art.suburl)

        image = "notfound.png"

        if cached_download(metadata.image, index, "png"):
            image = f"{asset_dir}{index}.png"

        return {
            "title": art.text,
            "url": art.mainurl,
            "image": image,
            "category": art.category,
            "firstline": firstSentence,
            "content": data,
            "properties": newsproperties,
        }


class PDFHandler:
    def test(self, art):
        # Ofcourse this check isnt perfect but shoulod catch 99% of all pdf's
        return get_url_extension(art.mainurl) == ".pdf"

    def work(self, index, art, browser):
        # TODO: fix screenshots for pdf's they currently do not work!

        metadatadict = get_metadata(art.title)

        data = ""

        if cached_download(art.mainurl, index, "pdf"):
            pdf = f"{asset_dir}{index}.pdf"
            reader = PdfReader(pdf)
            number_of_pages = len(reader.pages)
            page = reader.pages[0]
            text = page.extract_text()
            if number_of_pages != 1:
                text += " " + reader.pages[1].extract_text()
            data = text
        # temp remove all emoji stuff, until found decent solutions in latex
        # solved : no longer necessary with Tectonic Typesetting.
        # data = removeUnicode(data)
        # data can contain a lot of characters, we only want the first 1500
        # santize the data by removing % and /

        firstSentence, data = prep_body(data)

        image = "notfound.png"

        if os.path.isfile(f"{asset_dir}{index}.png"):
            image = f"{asset_dir}{index}.png"

        newsproperties = []

        add_stats(newsproperties, metadatadict, art.suburl)

        return {
            "title": art.text,
            "url": art.mainurl,
            "image": image,
            "category": art.category,
            "firstline": firstSentence,
            "content": data,
            "properties": newsproperties,
        }


class DefaultHandler(UrlHandler):
    def test(self, art):
        return True
    def work(self, index, art, browser):
        # TODO clean this up

        #if file exists skip
        if not os.path.isfile(f"{asset_dir}{index}.png") and not os.path.isfile(
            f"{asset_dir}{index}.jpg"
        ):
            try:
                generate_screenshot(index, art.mainurl, browser)
            except:  # noqa: E722
                # TODO : create a timeout/404 default jpg.
                pass

        sitecontent = loadordownload(index, art)
        data  = extract(sitecontent)

        firstSentence, data = prep_body(data)

        metadata = extract_metadata(sitecontent)

        metadatadict = get_metadata(
            art.title, metadata.as_dict() if metadata is not None else {}
        )

        # fall back 
        image = "notfound.png"
        #image url can be either a png or a jpg
        if os.path.isfile(f'{asset_dir}{index}.png'):
            image = f"{asset_dir}{index}.png"

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

        add_stats(newsproperties, metadatadict, art.suburl)

        return {
                "title": art.text, 
                "url" : art.mainurl,
                "image": image, 
                "category" : art.category,
                "firstline": firstSentence,
                "content": data, 
                "properties": newsproperties 
            }