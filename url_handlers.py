import logging
import os
import re
import urllib.request
import urllib.parse
import urllib3
from trafilatura import extract, extract_metadata
from fake_useragent import UserAgent
import config
import json
from pypdf import PdfReader
from PIL import Image

log = logging.getLogger("hackernewspaper")

ua = UserAgent()

PAGE_TIMEOUT_MS = 30000


# visit url in a new page of the (Playwright) browser, optionally take a screenshot,
# and return the html. A slow page is still captured after the timeout.
def visit(url, browser, screenshot=None):
    page = browser.new_page()
    try:
        try:
            page.goto(url, timeout=PAGE_TIMEOUT_MS, wait_until="load")
        except Exception as e:
            log.warning("Loading %s did not finish: %s", url, e)
        if screenshot is not None:
            try:
                # TODO Solve the cookie accept problem
                page.screenshot(path=screenshot, timeout=PAGE_TIMEOUT_MS)
            except Exception as e:
                log.warning("Screenshot of %s failed: %s", url, e)
        return page.content()
    finally:
        page.close()


# download the html from a given url
def download_html(url, browser):
    try:
        return visit(url, browser)
    except Exception as e:
        log.warning("Downloading %s failed: %s", url, e)
        return None


def write_html(index, sitecontent):
    with open(f"{config.asset_dir}{index}.html", "w", encoding="utf-8") as f:
        f.write(sitecontent)


# load or download art.mainurl contents
def loadordownload(index, art, browser):
    fname = f"{config.asset_dir}{index}.html"
    if os.path.isfile(fname):
        with open(fname, encoding="utf-8") as f:
            sitecontent = f.read()
    else:
        sitecontent = download_html(art.mainurl, browser)
        if sitecontent is None:
            sitecontent = ""
        write_html(index, sitecontent)
    return sitecontent


def splitFirstSentenceParagraph(data):
    # find the indexes of all occurences of a dot, question mark or exclamation mark,
    # a dot between two digits (3.15.0) does not end a sentence
    dots = [
        i
        for i, ltr in enumerate(data)
        if ltr in [".", "?", "!"]
        and i < 200
        and not (ltr == "." and 0 < i < len(data) - 1 and data[i - 1].isdigit() and data[i + 1].isdigit())
    ]
    # find the highest index that is smaller than 200 and make sure the max is not taken over an empty set
    if len(dots) > 0:
        firstdot = max(dots)
        if firstdot > 10:
            return data[: firstdot + 1], data[firstdot + 1 :]
    return None, data


def removeEmptyLines(data):
    # remove empty lines
    lines = data.split("\n")
    lines = [line for line in lines if line.strip() != ""]
    return "\n".join(lines)


# last resort when every handler failed: title and link only
def minimal_item(art):
    return {
        "title": art.text,
        "url": art.mainurl,
        "image": "notfound.png",
        "category": art.category,
        "firstline": None,
        "content": "",
        "properties": [],
    }


class UrlHandler:
    def test(self, art) -> bool:
        return False

    def work(self, index, art):
        pass


def isValidDictItem(item, dict):
    return item in dict and dict[item] is not None and dict[item] != ""


# map the site to a fontawesome symbol
# https://www.comet.com/standardizing-experiment/eda-hackernews-data/reports/standardizing-the-experiment-exploring-the-hackernews-dataset
FA_SYMBOLS = {
    "flickr.com": "Flickr",
    "medium.com": "Medium",
    "twitter.com": "Twitter",
    "wikipedia.org": "WikipediaW",
    "reddit.com": "Reddit",
    "ycombinator.com": "YCombinator",
    # Youtube
    "youtube.com": "Youtube",
    "youtu.be": "Youtube",
    # Github
    "github.com": "Github",
    "github.io": "Github",
    "github.blog": "Github",
    # News Papers
    "nytimes.com": "NewspaperO",
    "theguardian.com": "NewspaperO",
    "dev.to": "NewspaperO",
    "techcrunch.com": "NewspaperO",
    "wsj.com": "NewspaperO",
    "arstechnica.com": "NewspaperO",
    "theverge.com": "NewspaperO",
    "bbc.com": "NewspaperO",
    "bloomberg.com": "NewspaperO",
    "reuters.com": "NewspaperO",
}


def faSymbolPerHostname(hostname: str):
    # Globe for others
    return FA_SYMBOLS.get(hostname.removeprefix("www."), "Globe")


def write(index: int, data):
    with open(f"{config.asset_dir}{index}.json", "w", encoding="utf-8") as f:
        json.dump(data, f, ensure_ascii=False, indent=4)


def read(index: int):
    try:
        with open(f"{config.asset_dir}{index}.json", encoding="utf-8") as data_file:
            return json.load(data_file)
    except (OSError, ValueError):
        return None


def download_bin(url):
    header = {"User-Agent": str(ua.random)}
    try:
        with urllib.request.urlopen(urllib.request.Request(url, headers=header)) as response:
            return response.read()
    except Exception as e:
        log.warning("Downloading %s failed: %s", url, e)
        return None


def cached_download(url: str, index: int, ext: str):
    fname = f"{config.asset_dir}{index}.{ext}"
    if os.path.isfile(fname):
        return True
    else:
        sitecontent = download_bin(url)
        if sitecontent is None:
            return False
        with open(fname, "wb") as f:
            f.write(sitecontent)
        # GIF magic bytes, tectonic cannot include GIFs
        if sitecontent[:6] in (b"GIF87a", b"GIF89a"):
            os.remove(fname)
            return False
        if os.path.isfile(fname):
            return True
    return False


def get_url_extension(url):
    parsed_url = urllib.parse.urlparse(url)
    path = parsed_url.path
    return os.path.splitext(path)[1]


# votes and comments come from the newsletter link title, e.g. "Votes: 1872 Comments: 447"
def get_metadata(title: str, metadatadict: dict | None = None) -> dict:
    metadatadict = dict(metadatadict or {})
    # trafilatura has its own (unrelated) comments field, only the HN numbers are used
    metadatadict.pop("comments", None)
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

    text = text.replace("%", "").replace("\u001b", "").replace("\u000f", "").replace("\\", "")

    # remove empty lines
    text = removeEmptyLines(text)
    firstSentence, text = splitFirstSentenceParagraph(text)

    return firstSentence, text


def youtube_video_id(url):
    return urllib.parse.parse_qs(urllib.parse.urlparse(url).query)["v"][0]


class YoutubeHandler:
    def test(self, art):
        # without an API key fall through to the DefaultHandler (screenshot)
        return config.YOUTUBE_API_KEY != "" and art.mainurl.startswith("https://www.youtube.com/watch?v=")

    def work(self, index, art, browser):
        video_info = read(index)
        if video_info is None:
            video_id = youtube_video_id(art.mainurl)
            with urllib3.PoolManager() as http:
                response = http.request(
                    "GET",
                    f"https://www.googleapis.com/youtube/v3/videos?part=id%2C+snippet&id={video_id}&key={config.YOUTUBE_API_KEY}",
                )
                video_info = json.loads(response.data)
            # do not cache errors (quota, key) so a rerun tries again
            if video_info.get("items"):
                write(index, video_info)

        metadatadict = get_metadata(art.title)

        newsproperties = []

        if not video_info.get("items"):
            # video removed/private or an API error (quota, key), fall back to a screenshot
            return DefaultHandler().work(index, art, browser)

        metadata_list = video_info["items"][0]["snippet"]

        firstSentence, data = prep_body(metadata_list["description"])

        image = "notfound.png"
        if cached_download(metadata_list["thumbnails"]["medium"]["url"], index, "jpg"):
            image = f"{config.asset_dir}{index}.jpg"
            # tectonic was being funny with the standard youtube jpg thumbnails so we convert them to PNG and it doesnt complain anymore :)
            im = Image.open(image)
            image = f"{config.asset_dir}{index}.png"
            im.save(image)

        newsproperties.append({"symbol": "User", "value": metadata_list["channelTitle"], "url": None})

        upload = metadata_list["publishedAt"]

        newsproperties.append(
            {
                "symbol": "Calendar",
                "value": f"{upload[:4]}-{upload[5:7]}-{upload[8:10]}",
                "url": None,
            }
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
            # TODO: Find a way to parse this content, currently some links cause an overflow outside of the designated colum
            "content": data,
            "properties": newsproperties,
        }


class GithubHandler:
    def test(self, art):
        return is_github_repo(art.mainurl)

    def work(self, index, art, browser):
        # TODO clean this up

        sitecontent = loadordownload(index, art, browser)
        metadata = extract_metadata(sitecontent)
        if metadata is None:
            # page could not be downloaded or parsed, fall back to a screenshot
            return DefaultHandler().work(index, art, browser)
        data = (metadata.description or "") + " " + (extract(sitecontent) or "")

        firstSentence, data = prep_body(data)

        metadatadict = get_metadata(art.title, metadata.as_dict() if metadata is not None else {})

        newsproperties = []

        if isValidDictItem("author", metadatadict):
            newsproperties.append({"symbol": "User", "value": metadatadict["author"], "url": None})
        if isValidDictItem("date", metadatadict):
            newsproperties.append({"symbol": "Calendar", "value": metadatadict["date"], "url": None})
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
        png = f"{config.asset_dir}{index}.png"
        if metadata.image and cached_download(metadata.image, index, "png"):
            image = png
        else:
            # no (downloadable) social image, e.g. rate limited, use a screenshot of the repo
            visit(art.mainurl, browser, screenshot=png)
            if os.path.isfile(png):
                image = png

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
            pdf = f"{config.asset_dir}{index}.pdf"
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

        if os.path.isfile(f"{config.asset_dir}{index}.png"):
            image = f"{config.asset_dir}{index}.png"

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
        # one page visit gives both the screenshot and the html, both are cached
        png = f"{config.asset_dir}{index}.png"
        if not os.path.isfile(png) and not os.path.isfile(f"{config.asset_dir}{index}.jpg"):
            sitecontent = visit(art.mainurl, browser, screenshot=png)
            write_html(index, sitecontent)
        else:
            sitecontent = loadordownload(index, art, browser)
        data = extract(sitecontent)

        firstSentence, data = prep_body(data)

        metadata = extract_metadata(sitecontent)

        metadatadict = get_metadata(art.title, metadata.as_dict() if metadata is not None else {})

        # fall back
        image = "notfound.png"
        # image url can be either a png or a jpg
        if os.path.isfile(f"{config.asset_dir}{index}.png"):
            image = f"{config.asset_dir}{index}.png"

        # potential interested metadata fields are: author, date, image, sitename
        # not used , but for future reference :
        # pagetype [object, article, website ]
        # description
        # categories and tags

        newsproperties = []

        if isValidDictItem("author", metadatadict):
            newsproperties.append({"symbol": "User", "value": metadatadict["author"], "url": None})
        if isValidDictItem("date", metadatadict):
            newsproperties.append({"symbol": "Calendar", "value": metadatadict["date"], "url": None})
        if isValidDictItem("hostname", metadatadict):
            newsproperties.append(
                {
                    "symbol": faSymbolPerHostname(metadatadict["hostname"]),
                    "value": metadatadict["hostname"],
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
