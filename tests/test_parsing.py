from pathlib import Path

import pytest

import config
import generator
import url_handlers
from get_latest_edition import parse_latest_edition

FIXTURES = Path(__file__).parent / "fixtures"


def fixture(name):
    return (FIXTURES / name).read_text(encoding="utf-8")


@pytest.fixture
def edition_814():
    return generator.parse_html(fixture("edition-814.html"))


# --- archive page ---


def test_latest_edition_from_archive():
    assert parse_latest_edition(fixture("archive.html")) == "814"


def test_latest_edition_missing_list():
    assert parse_latest_edition("<html><body>maintenance</body></html>") is None


# --- edition page ---


def test_categories_and_articles(edition_814):
    articles, categories = generator.get_articles(edition_814)
    assert categories[0] == "#Favorites"
    assert len(categories) == 13
    assert len(articles) == 63
    assert {a.category for a in articles} == set(categories)


def test_article_fields(edition_814):
    articles, _ = generator.get_articles(edition_814)
    art = next(a for a in articles if a.text == "Things to know when you get cancer")
    assert art.mainurl.startswith("https://jjmaxwell4.com/")
    assert art.title == "Votes: 1872 Comments: 447"
    assert art.suburl.startswith("http://news.ycombinator.com/item?id=")


def test_header_quote(edition_814):
    quote, author = generator.parse_header(generator.get_header(edition_814))
    assert quote == "Institutions will try to preserve the problem to which they are the solution."
    assert author == "Clay Shirky"


def test_parse_header_without_author():
    assert generator.parse_header("Just a line") == ("Just a line", "")


def test_clean_category():
    assert generator.clean_category("\n\n    #\n  \n  Sponsor\n") == "#Sponsor"
    assert generator.clean_category("#Ask HN") == "#Ask HN"


def test_empty_sponsor_category_is_dropped():
    # 773 starts with a "Sponsor" heading without article links, it used to render an empty section
    articles, categories = generator.get_articles(generator.parse_html(fixture("edition-773.html")))
    assert categories[0] == "#Favorites"
    assert "#Sponsor" not in categories
    assert all(c == c.strip() and "\n" not in c for c in categories)


def test_get_header_missing():
    assert generator.get_header(generator.parse_html("<html></html>")) == ""


# --- metadata ---


def test_votes_and_comments_from_title():
    meta = url_handlers.get_metadata("Votes: 1872 Comments: 447")
    assert meta == {"votes": 1872, "comments": 447}


def test_get_metadata_has_no_shared_state():
    url_handlers.get_metadata("Votes: 10 Comments: 5")
    assert url_handlers.get_metadata("poppulo.com") == {}


def test_trafilatura_comments_field_is_ignored():
    meta = url_handlers.get_metadata("poppulo.com", {"comments": None, "author": "x"})
    assert meta == {"author": "x"}
    props = []
    url_handlers.add_stats(props, meta, "")
    assert props == []


def test_get_metadata_does_not_modify_input():
    source = {"comments": "abc"}
    url_handlers.get_metadata("Votes: 1 Comments: 2", source)
    assert source == {"comments": "abc"}


# --- helpers ---


@pytest.mark.parametrize(
    "url, video_id",
    [
        ("https://www.youtube.com/watch?v=XiZmM6hwwAU&utm_source=hackernewsletter", "XiZmM6hwwAU"),
        ("https://www.youtube.com/watch?v=XiZmM6hwwAU", "XiZmM6hwwAU"),
        ("https://www.youtube.com/watch?feature=share&v=XiZmM6hwwAU", "XiZmM6hwwAU"),
    ],
)
def test_youtube_video_id(url, video_id):
    assert url_handlers.youtube_video_id(url) == video_id


def test_first_sentence_ignores_version_numbers():
    first, rest = url_handlers.splitFirstSentenceParagraph(
        "Python 3.15.0 Release date: Oct. 9, 2026 This is the stable release of Python 3.15.0 Python 3.15 is new. More text"
    )
    assert first.endswith("Python 3.15 is new.")
    assert rest == " More text"


def test_first_sentence_short_text():
    assert url_handlers.splitFirstSentenceParagraph("Hi.") == (None, "Hi.")


@pytest.mark.parametrize(
    "host, symbol",
    [
        ("github.com", "Github"),
        ("www.github.com", "Github"),
        ("flickr.com", "Flickr"),
        ("example.org", "Globe"),
    ],
)
def test_fa_symbol_per_hostname(host, symbol):
    assert url_handlers.faSymbolPerHostname(host) == symbol


def test_is_github_repo():
    assert url_handlers.is_github_repo("https://github.com/bitfox-git/hackernewspaper")
    assert not url_handlers.is_github_repo("https://github.com/bitfox-git")


def test_prep_body_none():
    assert url_handlers.prep_body(None) == (None, "")


# --- per-article isolation ---


class Art:
    mainurl = "https://example.org/x"
    title = None
    text = "Example"
    suburl = ""
    category = "#Code"


class Boom:
    def test(self, art):
        return True

    def work(self, index, art, browser):
        raise RuntimeError("boom")


def test_failing_handlers_give_minimal_item(monkeypatch):
    monkeypatch.setattr(generator, "handlers", [Boom()])
    monkeypatch.setattr(generator, "DefaultHandler", Boom)
    item = generator.process_article(0, Art(), browser=None)
    assert item == url_handlers.minimal_item(Art())
    assert item["image"] == "notfound.png"


def test_failing_handler_falls_back_to_default(monkeypatch):
    class Default:
        def work(self, index, art, browser):
            return {"title": "from default"}

    monkeypatch.setattr(generator, "handlers", [Boom()])
    monkeypatch.setattr(generator, "DefaultHandler", Default)
    assert generator.process_article(0, Art(), browser=None) == {"title": "from default"}


# --- text cleaning before rendering ---


def test_clean_text_strips_invisible_characters():
    # variation selector, zero width joiner, line separator, private use, skin tone
    assert generator.clean_text("ok️ ❤‍\U0001f525 a b  \U0001f44b\U0001f3fb") == "ok ❤\U0001f525 ab  \U0001f44b"


def test_clean_text_keeps_punctuation_and_scripts():
    text = "– — “hi” … • Αθήνα Москва 中文 \U0001f680"
    assert generator.clean_text(text) == text


def test_clean_text_recurses():
    data = {"a": ["x️", {"b": "y​"}], "n": 3, "none": None}
    assert generator.clean_text(data) == {"a": ["x", {"b": "y"}], "n": 3, "none": None}


def test_titles_have_no_line_breaks():
    # a blank line inside \subsection{} was a TeX error in 773, 774, 804, 811 and 812
    for name in ["edition-773.html", "edition-814.html"]:
        articles, _ = generator.get_articles(generator.parse_html(fixture(name)))
        assert all("\n" not in a.text and a.text == a.text.strip() for a in articles)


# --- phase 3: videos, pdfs, images, tracking parameters ---


@pytest.mark.parametrize(
    "url, video_id",
    [
        ("https://youtu.be/XiZmM6hwwAU?si=abc", "XiZmM6hwwAU"),
        ("https://www.youtube.com/shorts/XiZmM6hwwAU", "XiZmM6hwwAU"),
        ("https://m.youtube.com/watch?v=XiZmM6hwwAU", "XiZmM6hwwAU"),
        ("https://www.youtube.com/live/XiZmM6hwwAU", "XiZmM6hwwAU"),
        ("https://www.youtube.com/@somechannel", None),
        ("https://example.org/watch?v=XiZmM6hwwAU", None),
    ],
)
def test_youtube_video_id_variants(url, video_id):
    assert url_handlers.youtube_video_id(url) == video_id


def test_vimeo_video_id():
    assert url_handlers.vimeo_video_id("https://vimeo.com/76979871") == "76979871"
    assert url_handlers.vimeo_video_id("https://player.vimeo.com/video/76979871") == "76979871"
    assert url_handlers.vimeo_video_id("https://vimeo.com/channels/staffpicks") is None


@pytest.mark.parametrize(
    "iso, text",
    [("PT1H2M3S", "1:02:03"), ("PT4M5S", "4:05"), ("PT45S", "0:45"), ("P1DT1H", "25:00:00"), ("", None), ("P0D", None)],
)
def test_format_iso_duration(iso, text):
    assert url_handlers.format_iso_duration(iso) == text


def test_video_handler_test():
    class Video:
        mainurl = "https://youtu.be/XiZmM6hwwAU"

    assert url_handlers.VideoHandler().test(Video())
    assert not url_handlers.VideoHandler().test(Art())


def test_pdf_handler_test():
    class Pdf:
        mainurl = "https://example.org/paper.PDF"

    class Arxiv:
        mainurl = "https://arxiv.org/pdf/2401.12345"

    assert url_handlers.PDFHandler().test(Pdf())
    assert url_handlers.PDFHandler().test(Arxiv())
    assert not url_handlers.PDFHandler().test(Art())


@pytest.mark.parametrize(
    "url, clean",
    [
        (
            "https://example.org/a?utm_source=hackernewsletter&utm_medium=email&utm_term=fav",
            "https://example.org/a",
        ),
        ("https://www.youtube.com/watch?v=abc&utm_source=hn", "https://www.youtube.com/watch?v=abc"),
        (
            "http://news.ycombinator.com/item?id=50093568&utm_term=comment",
            "http://news.ycombinator.com/item?id=50093568",
        ),
        ("https://example.org/a?b=1#frag", "https://example.org/a?b=1#frag"),
        ("", ""),
    ],
)
def test_strip_tracking(url, clean):
    assert url_handlers.strip_tracking(url) == clean


def test_articles_have_no_tracking_parameters(edition_814):
    articles, _ = generator.get_articles(edition_814)
    assert not any("utm_" in a.mainurl or "utm_" in a.suburl for a in articles)


@pytest.fixture
def asset_dir(tmp_path, monkeypatch):
    monkeypatch.setattr(config, "asset_dir", f"{tmp_path}/")
    return tmp_path


def test_download_image_converts_to_jpeg_on_white(asset_dir, monkeypatch):
    import io

    from PIL import Image

    transparent = Image.new("RGBA", (16, 16), (255, 0, 0, 0))
    buffer = io.BytesIO()
    transparent.save(buffer, "WEBP")
    monkeypatch.setattr(url_handlers, "download_bin", lambda url: buffer.getvalue())

    path = url_handlers.download_image("https://example.org/logo.webp", 7)
    assert path == f"{asset_dir}/7-img.jpg"
    with Image.open(path) as im:
        assert im.format == "JPEG"
        assert im.mode == "RGB"
        assert all(c > 250 for c in im.getpixel((0, 0)))
    assert url_handlers.find_image(7) == path


def test_find_image_order(asset_dir):
    assert url_handlers.find_image(3) == url_handlers.NOT_FOUND
    (asset_dir / "3.jpg").write_bytes(b"x")
    assert url_handlers.find_image(3) == f"{asset_dir}/3.jpg"
    # png cached by older builds
    (asset_dir / "3.png").write_bytes(b"x")
    assert url_handlers.find_image(3) == f"{asset_dir}/3.png"
    (asset_dir / "3-img.jpg").write_bytes(b"x")
    assert url_handlers.find_image(3) == f"{asset_dir}/3-img.jpg"


def test_render_pdf_page(asset_dir):
    from PIL import Image

    pdf = asset_dir / "1.pdf"
    Image.new("RGB", (200, 100), "blue").save(pdf, "PDF")
    assert url_handlers.is_pdf(pdf)
    url_handlers.render_pdf_page(pdf, asset_dir / "1-img.jpg", width=400)
    with Image.open(asset_dir / "1-img.jpg") as im:
        assert im.format == "JPEG"
        assert im.width == 400


def test_configure_sets_asset_dir():
    config.configure(814)
    assert config.ISSUE == "814"
    assert config.asset_dir == "dist/814/"
