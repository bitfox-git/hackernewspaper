# HackerNewsPaper – Plan (2026-10-19)

**Goal:** revive the pipeline, backfill #773–#814, make it robust enough that it can't silently die again, then improve quality with better screenshots and LLM summaries.
See [FINDINGS.md](FINDINGS.md) for the evidence behind each item (B-numbers refer to it).

Work happens on `develop` → PR to `main` (the workflow runs from `main`).

---

## Phase 0 – Revive (small PR, do first)
1. **Fix edition detection** (B1): select `div.email-title` in `get_latest_edition.py`, parse the number with a regex `#(\d+)`, and use `https://buttondown.com/hacker-newsletter/archive/` as the source.
2. Use the new per-edition URL `…/archive/<N>/` in `generator.py` (keep the old slug as a fallback). Drop the `675` hack in `config.py`.
3. Make `YOUTUBE_API_KEY` optional (`environ.get`), with YouTube falling back to a screenshot (B13).
4. Workflow: "no new edition" exits **0** with a notice instead of `exit 1`. Only real errors are red.
5. Re-enable the workflow (`gh workflow enable main.yml`) after merge; do a `workflow_dispatch` run for #814.
6. Check that the `YOUTUBE_API_KEY` secret still works (first run will show it).

**Done when:** a manual run publishes Release #814 and a second run is green with "nothing to do".

## Phase 1 – Backfill #773–#813 ✅ (2026-10-19)
1. ✅ A `workflow_dispatch` input `edition` builds one specific edition.
2. ✅ A `detect` job lists every edition from `BACKFILL_FROM` (773) up to the latest one that has **no release tag**, capped at `MAX_EDITIONS` (50). A matrix `build` job then builds them (max 4 parallel, fail-fast off), so future misses self-heal. Older historic gaps (666, 677, 692, 698, 700, 728) are left alone because of the floor.
3. ✅ `makeLatest` is `true` only for the newest edition and `false` for backfilled ones. Lesson learned: #814 had been created with the action's default `legacy` mode, so it was never *explicitly* Latest, and GitHub moved Latest to #812 during the backfill. I fixed it by PATCHing #814 with `make_latest=true`. From now on every newest edition is explicitly Latest, so this can't recur. Backfilled releases still appear above #814 in the release list, because GitHub sorts by creation date.
4. ✅ Scheduled runs call the workflow `enable` API, which resets GitHub's 60-day inactivity timer. I kept the daily cron: no-op days are green now, and a missed Friday is picked up the next morning.
5. ✅ Backfill results: 38/40 built in the first run. #778 (B5, GithubHandler without metadata) and #811 (B4, YouTube video without items) failed, were fixed with a fallback to the screenshot handler, and the next run without input picked up exactly those two (self-heal verified).

To rebuild an edition, delete its release **and its tag** (detection is tag-based), or dispatch with `edition=<N>`.

## Phase 2 – Robustness and tests ✅ (2026-10-20)
1. ✅ **TeX warnings and errors** (B7), done 2026-10-20:
   - The CI logs of #773–#814 had 427 distinct characters missing from TeX Gyre Pagella, plus real TeX errors in 5 editions (#773, #774, #804, #811, #812), all from blank lines inside a `\subsection{}` title. The whitespace normalization of titles in this phase fixes those.
   - The template now has **fallback fonts through XeTeX interchar classes**: FreeSerif (Greek, Cyrillic, Thai, IPA, symbols, dingbats, box drawing, math letters), FandolSong (CJK, kana), UnBatang (Hangul) and Noto Emoji, the monochrome one (emoji). Those are the fonts available in Tectonic's bundle; color emoji and Noto CJK aren't in it.
   - Invisible characters (variation selectors, zero-width and bidi controls, private use, skin-tone modifiers) are stripped before rendering (`generator.clean_text`).
   - Result: 372 of the 427 characters render. The remaining 55 are emoji newer than the bundled Noto Emoji, which show as a box, and some Japanese-only kanji.
   - `-Z continue-on-errors` is dropped from `main.yml`. Before that, every title, category and quote of all 42 editions compiled without it.
2. ✅ Fixed B2 (mutable default), B3 (`parse_qs` for the video id), B4/B5 (fall back to a screenshot), B6 (fetch errors are logged, a missing edition raises with a message), B9 (category text is cleaned, empty sections like *Sponsor* are dropped), B10 (utf-8), B14 (trafilatura's `comments` field is ignored), B15 (no sentence split inside version numbers). Failed YouTube API responses are no longer cached.
3. ✅ **Per-article isolation:** a failing handler falls back to `DefaultHandler`, and if that fails too, to a title + link item. One bad link never kills an edition.
4. ✅ **One browser stack:** Selenium is gone. Playwright fetches all HTML, and one page visit gives both the screenshot and the HTML. A slow page is still captured after a 30 s timeout. Every article uses one desktop context (1280×800, regular Chrome user agent).
5. ✅ `generator.py` is split into functions with `main()`, and uses `logging`. Nothing runs at import time; `config.configure(issue)` replaces the `sys.argv` parsing in `config.py`.
6. ✅ **Tests:** `tests/test_parsing.py` (27 tests) on saved fixtures for the archive page, #773 and #814. `.github/workflows/test.yml` runs them on every PR and on pushes to main/develop.
7. ✅ `requirements.txt` went from 67 to 32 pins (Selenium, the Google API client and `pythumb` stacks removed). Added `requirements-dev.txt` (pytest) and a minimal `pyproject.toml` (`requires-python >=3.11`, pytest config). ✅ Ruff is enabled (`ruff check` + `ruff format`, line length 120) and runs in `test.yml`.
8. ✅ Housekeeping: fixed the template text and links, `faSymbolPerHostname` (strips `www.`, `flickr`, no duplicate case) and the README. ⏳ Deleting the stale `curl` / `debug-711` branches still needs your OK.

## Phase 3 – Better screenshots (mostly ✅, 2026-10-20)
Measured on the 63 links of #814 (baseline → now): consent banners visible in 7 → **0** screenshots; blank or unfinished pages 4 → 0; PDF 12.9 MB → **6.6 MB**; build time 3 → 4 min (because of the network-idle wait).
1. ✅ **Cookie/GDPR banners** (`consent.py`), the in-house approach:
   - Click a known consent-manager button (OneTrust, Cookiebot, Didomi, Funding Choices, Quantcast, Sourcepoint), else a button with a consent-like text inside a cookie/consent/privacy container. **Reject / necessary-only is preferred**, accept is the fallback.
   - Searches the page, its iframes and open shadow roots (WPConsent renders in one).
   - Remaining fixed/sticky consent overlays are hidden with CSS, and scroll locks are undone.
   - On #814, 13 pages had a banner handled: 11 rejected or declined, 2 (Anthropic, ProjectionLab) accepted because they only offer accept.
2. ✅ JPEG screenshots (quality 80) and a 5 s network-idle wait after `load` (fixes lazily rendered pages). Fixed viewport 1280×800 and a regular Chrome user agent were done in Phase 2. ⏳ Not done: `reduced_motion` / color scheme (no visible problem seen).
3. ✅ **PDF links** (issue #1, B12): the first page is rendered with `pypdfium2`, and the properties show the page count and host. arXiv `/pdf/` links (no extension) are included. A download that isn't a PDF falls back to a web page.
4. ✅ **Video links** (B11): `VideoHandler` handles `youtu.be`, `/shorts/`, `/live/`, `/embed/`, `m.youtube` and Vimeo.
   - YouTube uses the Data API (channel, date, **duration**, description) with a key, and oEmbed (channel, thumbnail) without one. The thumbnail is the 1280×720 one, falling back to 320×180.
   - Vimeo uses oEmbed (author, date, duration, description, thumbnail).
   - A removed or private video falls back to a screenshot. Errors aren't cached.
5. ⏳ Other non-HTML links (MP4, images) are not handled yet; they still go through the screenshot path.
6. ⏳ Concurrent screenshots (async Playwright) are not done; a 4-minute build is fine for a weekly job.
7. ✅ `utm_*` parameters are stripped from article and HN comment links (`strip_tracking`).
8. Also: downloaded pictures (social image, video thumbnail, PDF page) are stored as `<index>-img.jpg` (baseline RGB JPEG, transparency on white). Older `<index>.png` caches are still used. The "…" after an article is only printed when it has text.
9. ⏳ Still visible in #814: bot walls (Access Denied / "Checking your browser" / "temporarily restricted" on 3–4 sites). Options: detect them and use the site's social image instead of the screenshot.

## Phase 4 – LLM summaries
1. New optional step `summarize.py`: for each article, send the trafilatura text (truncated to ~6–8k tokens) plus the title to Claude and get back **structured JSON**: `{ "lede": str (≤1 sentence), "summary": str (60–120 words), "tags": [str], "read_minutes": int }`.
2. Model: `claude-haiku-5-5` by default (cheap and fast for ~60 articles/week), with a config switch to `claude-sonnet-5-5` for Favorites. Use prompt caching for the shared system prompt and batch requests (Message Batches API) since latency doesn't matter.
3. Cache results in `dist/<N>/<index>.summary.json` (same pattern as existing caches) so reruns cost nothing.
4. Fallback: no `ANTHROPIC_API_KEY` or an API error → the current `prep_body` text. The build never fails on summaries.
5. Template: show `lede` in bold + `summary` instead of the raw text and `\dots`. This fixes the README's "better text formatting" item and the column overflow TODO.
6. Optional extras: an edition-level "This week in 5 bullets" on the cover page, and HN comment-thread highlights (from the HN Algolia API) for Favorites.
7. Rough cost to verify before launch: ~60 articles × ~5k input tokens/week, a few cents per edition on Haiku with batching.

## Order and size
| Phase | Size | Depends on |
|---|---|---|
| 0 Revive | ~½ day | – |
| 1 Backfill | ~½ day + CI time | 0 |
| 2 Robustness/tests | 2–3 days | 0 (ideally before the bulk backfill, so backfilled PDFs get escaping fixes) |
| 3 Screenshots | 1–2 days | 2.4 (single browser) |
| 4 LLM summaries | 1–2 days | 2.5 (restructured generator) |

Suggested sequencing: **0 → 2.1–2.4 → 1 → 2 (rest) → 3 → 4.** Ship #814 immediately, but run the bulk backfill after escaping and handler isolation land, so the 41 backfilled PDFs are clean.

## Local dev setup (to do when implementation starts)
```bash
py -3.12 -m venv .venv
.venv/Scripts/python -m pip install -r requirements.txt
.venv/Scripts/playwright install chromium
# Tectonic: download tectonic-*-x86_64-pc-windows-msvc.zip from github.com/tectonic-typesetting/tectonic/releases
```
Set `YOUTUBE_API_KEY` (and later `ANTHROPIC_API_KEY`) as user environment variables, then run `python generator.py 814` and `tectonic -X compile output.tex`.

## Open questions
- Who owns the Google Cloud project behind `YOUTUBE_API_KEY`? (The key itself still works: #813 built 4 YouTube items in CI.)
- Who pays for and owns the `ANTHROPIC_API_KEY` for summaries (Bitfox org secret)?
- OK to delete the stale `curl` and `debug-711` branches?
