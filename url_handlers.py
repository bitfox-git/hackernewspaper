import logging
import io
import os
import re
import urllib.request
import urllib.parse
from trafilatura import extract, extract_metadata
from fake_useragent import UserAgent
import config
import consent
import json
from pypdf import PdfReader
from PIL import Image

log = logging.getLogger("hackernewspaper")

ua = UserAgent()

PAGE_TIMEOUT_MS = 30000
# after "load", give lazy content (images, client side rendering) a moment to settle
IDLE_TIMEOUT_MS = 5000
JPEG_QUALITY = 80


# visit url in a new page of the (Playwright) browser, optionally take a screenshot,
# and return the html. A slow page is still captured after the timeout.
# Screenshots are JPEG (a fraction of the size of PNG in the PDF), cookie banners are
# dismissed first.
def visit(url, browser, screenshot=None):
    page = browser.new_page()
    try:
        try:
            page.goto(url, timeout=PAGE_TIMEOUT_MS, wait_until="load")
        except Exception as e:
            log.warning("Loading %s did not finish: %s", url, e)
        if screenshot is not None:
            try:
                page.wait_for_load_state("networkidle", timeout=IDLE_TIMEOUT_MS)
            except Exception:
                pass
            consent.dismiss(page, url)
            try:
                page.screenshot(path=screenshot, type="jpeg", quality=JPEG_QUALITY, timeout=PAGE_TIMEOUT_MS)
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
    "vimeo.com": "Vimeo",
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


NOT_FOUND = "notfound.png"


# the picture of an article is a screenshot (<index>.jpg) or an image (<index>-img.jpg:
# social image, video thumbnail, first pdf page). Both are baseline RGB JPEGs, which
# tectonic always accepts and which keep the PDF small.
def screenshot_path(index):
    return f"{config.asset_dir}{index}.jpg"


def image_path(index):
    return f"{config.asset_dir}{index}-img.jpg"


# the cached picture of an article (<index>.png is what older builds cached)
def find_image(index):
    for path in (image_path(index), f"{config.asset_dir}{index}.png", screenshot_path(index)):
        if os.path.isfile(path):
            return path
    return NOT_FOUND


def save_jpeg(im, path):
    im.seek(0)  # first frame of an animation
    rgba = im.convert("RGBA")
    # transparent logos on white instead of black
    flat = Image.new("RGB", rgba.size, "white")
    flat.paste(rgba, mask=rgba.getchannel("A"))
    flat.save(path, "JPEG", quality=85)


# download an image (jpeg, png, webp, gif, ...) and store it as a jpeg
def download_image(url, index):
    path = image_path(index)
    if os.path.isfile(path):
        return path
    if not url:
        return None
    data = download_bin(url)
    if data is None:
        return None
    try:
        with Image.open(io.BytesIO(data)) as im:
            save_jpeg(im, path)
    except Exception as e:
        log.warning("Image %s could not be converted: %s", url, e)
        return None
    return path


# drop utm_* tracking parameters, the rest of the url is left as is
def strip_tracking(url):
    if not url or "utm_" not in url:
        return url
    parts = urllib.parse.urlsplit(url)
    query = [
        (k, v)
        for k, v in urllib.parse.parse_qsl(parts.query, keep_blank_values=True)
        if not k.lower().startswith("utm_")
    ]
    return urllib.parse.urlunsplit(parts._replace(query=urllib.parse.urlencode(query)))


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


YOUTUBE_URL = re.compile(
    r"^https?://(?:www\.|m\.)?(?:youtube\.com/(?:watch\?(?:.*&)?v=|shorts/|live/|embed/)|youtu\.be/)([\w-]{11})"
)
VIMEO_URL = re.compile(r"^https?://(?:www\.|player\.)?vimeo\.com/(?:video/)?(\d+)")


def youtube_video_id(url):
    match = YOUTUBE_URL.match(url)
    return match.group(1) if match else None


def vimeo_video_id(url):
    match = VIMEO_URL.match(url)
    return match.group(1) if match else None


def get_json(url):
    data = download_bin(url)
    if data is None:
        return None
    try:
        return json.loads(data)
    except ValueError:
        return None


# "PT1H2M3S" -> "1:02:03", "PT4M5S" -> "4:05"
def format_iso_duration(duration):
    match = re.fullmatch(r"P(?:(\d+)D)?T?(?:(\d+)H)?(?:(\d+)M)?(?:(\d+)S)?", duration or "")
    if not match or not any(match.groups()):
        return None
    days, hours, minutes, seconds = (int(g or 0) for g in match.groups())
    return format_seconds(((days * 24 + hours) * 60 + minutes) * 60 + seconds)


def format_seconds(total):
    if not total:
        return None
    hours, rest = divmod(int(total), 3600)
    minutes, seconds = divmod(rest, 60)
    return f"{hours}:{minutes:02d}:{seconds:02d}" if hours else f"{minutes}:{seconds:02d}"


def youtube_info(video_id):
    """Video metadata from the YouTube Data API (with a key) or oEmbed (without), None if unavailable."""
    if config.YOUTUBE_API_KEY:
        api = get_json(
            "https://www.googleapis.com/youtube/v3/videos?part=snippet%2CcontentDetails"
            f"&id={video_id}&key={config.YOUTUBE_API_KEY}"
        )
        if api and api.get("items"):
            item = api["items"][0]
            snippet = item["snippet"]
            return {
                "author": snippet.get("channelTitle"),
                "date": (snippet.get("publishedAt") or "")[:10] or None,
                "duration": format_iso_duration(item.get("contentDetails", {}).get("duration")),
                "description": snippet.get("description"),
            }
        log.warning("YouTube API has no data for %s, trying oEmbed", video_id)
    # oEmbed needs no key, but has no date, duration or description
    oembed = get_json(f"https://www.youtube.com/oembed?url=https://www.youtube.com/watch?v={video_id}&format=json")
    if oembed and oembed.get("title"):
        return {"author": oembed.get("author_name"), "date": None, "duration": None, "description": None}
    return None


def vimeo_info(url):
    oembed = get_json("https://vimeo.com/api/oembed.json?url=" + urllib.parse.quote(url, safe=""))
    if not oembed or not oembed.get("title"):
        return None
    return {
        "author": oembed.get("author_name"),
        "date": (oembed.get("upload_date") or "")[:10] or None,
        "duration": format_seconds(oembed.get("duration")),
        "description": oembed.get("description"),
        "thumbnail": oembed.get("thumbnail_url"),
    }


class VideoHandler:
    """YouTube and Vimeo links: the video thumbnail instead of a screenshot of the player,
    plus channel, date, duration and description. Falls back to a screenshot."""

    def test(self, art):
        return youtube_video_id(art.mainurl) is not None or vimeo_video_id(art.mainurl) is not None

    def work(self, index, art, browser):
        info = read(index)
        if info is None or "video" not in info:
            youtube_id = youtube_video_id(art.mainurl)
            if youtube_id:
                video = youtube_info(youtube_id)
                if video:
                    # maxresdefault (1280x720) does not exist for every video, mqdefault (320x180) does
                    video["thumbnails"] = [
                        f"https://i.ytimg.com/vi/{youtube_id}/maxresdefault.jpg",
                        f"https://i.ytimg.com/vi/{youtube_id}/mqdefault.jpg",
                    ]
                    video["host"] = "youtube.com"
            else:
                video = vimeo_info(art.mainurl)
                if video:
                    video["thumbnails"] = [video.pop("thumbnail")] if video.get("thumbnail") else []
                    video["host"] = "vimeo.com"
            if video is None:
                # video removed/private or no API answer, fall back to a screenshot
                return DefaultHandler().work(index, art, browser)
            info = {"video": video}
            write(index, info)
        video = info["video"]

        image = None
        for thumbnail in video.get("thumbnails", []):
            image = download_image(thumbnail, index)
            if image:
                break

        newsproperties = []
        if video.get("author"):
            newsproperties.append({"symbol": "User", "value": video["author"], "url": None})
        if video.get("date"):
            newsproperties.append({"symbol": "Calendar", "value": video["date"], "url": None})
        if video.get("duration"):
            newsproperties.append({"symbol": "ClockO", "value": video["duration"], "url": None})
        newsproperties.append({"symbol": faSymbolPerHostname(video["host"]), "value": video["host"], "url": None})
        add_stats(newsproperties, get_metadata(art.title), art.suburl)

        firstSentence, data = prep_body(video.get("description"))

        return {
            "title": art.text,
            "url": art.mainurl,
            "image": image or find_image(index),
            "category": art.category,
            "firstline": firstSentence,
            "content": data,
            "properties": newsproperties,
        }


class GithubHandler:
    def test(self, art):
        return is_github_repo(art.mainurl)

    def work(self, index, art, browser):
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

        # the social image of the repo, or (e.g. rate limited) a screenshot of the repo
        if not download_image(metadata.image, index) and find_image(index) == NOT_FOUND:
            visit(art.mainurl, browser, screenshot=screenshot_path(index))

        return {
            "title": art.text,
            "url": art.mainurl,
            "image": find_image(index),
            "category": art.category,
            "firstline": firstSentence,
            "content": data,
            "properties": newsproperties,
        }


ARXIV_PDF = re.compile(r"^https?://(?:www\.)?arxiv\.org/pdf/")


class PDFHandler:
    def test(self, art):
        # .pdf links and arxiv papers, which have no extension
        return get_url_extension(art.mainurl).lower() == ".pdf" or bool(ARXIV_PDF.match(art.mainurl))

    def work(self, index, art, browser):
        pdf = f"{config.asset_dir}{index}.pdf"
        if not cached_download(art.mainurl, index, "pdf") or not is_pdf(pdf):
            # not (or no longer) a pdf, e.g. a landing page: treat it as a web page
            if os.path.isfile(pdf):
                os.remove(pdf)
            return DefaultHandler().work(index, art, browser)

        reader = PdfReader(pdf)
        number_of_pages = len(reader.pages)
        text = " ".join((page.extract_text() or "") for page in reader.pages[:2])

        firstSentence, data = prep_body(text)

        # first page as the picture of the article
        render_pdf_page(pdf, image_path(index))

        newsproperties = [
            {
                "symbol": "FilePdfO",
                "value": f"{number_of_pages} pages" if number_of_pages != 1 else "1 page",
                "url": None,
            }
        ]
        hostname = urllib.parse.urlparse(art.mainurl).hostname or ""
        if hostname:
            newsproperties.append(
                {"symbol": faSymbolPerHostname(hostname), "value": hostname.removeprefix("www."), "url": None}
            )

        add_stats(newsproperties, get_metadata(art.title), art.suburl)

        return {
            "title": art.text,
            "url": art.mainurl,
            "image": find_image(index),
            "category": art.category,
            "firstline": firstSentence,
            "content": data,
            "properties": newsproperties,
        }


def is_pdf(path):
    with open(path, "rb") as f:
        return f.read(5) == b"%PDF-"


def render_pdf_page(pdf, path, width=1000):
    if os.path.isfile(path):
        return
    try:
        import pypdfium2

        document = pypdfium2.PdfDocument(pdf)
        try:
            page = document[0]
            save_jpeg(page.render(scale=width / page.get_width()).to_pil(), path)
        finally:
            document.close()
    except Exception as e:
        log.warning("Rendering the first page of %s failed: %s", pdf, e)


class DefaultHandler(UrlHandler):
    def test(self, art):
        return True

    def work(self, index, art, browser):
        # one page visit gives both the screenshot and the html, both are cached
        if find_image(index) == NOT_FOUND:
            sitecontent = visit(art.mainurl, browser, screenshot=screenshot_path(index))
            write_html(index, sitecontent)
        else:
            sitecontent = loadordownload(index, art, browser)
        data = extract(sitecontent)

        firstSentence, data = prep_body(data)

        metadata = extract_metadata(sitecontent)

        metadatadict = get_metadata(art.title, metadata.as_dict() if metadata is not None else {})

        image = find_image(index)

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
