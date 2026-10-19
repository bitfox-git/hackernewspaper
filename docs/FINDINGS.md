# HackerNewsPaper – Findings (2026-10-19)

## 1. What the repo does

HackerNewsPaper turns each weekly [Hacker Newsletter](https://hackernewsletter.com) edition into a magazine-style PDF and publishes it as a GitHub Release.

```
GitHub Actions (daily 06:00 UTC)
 ├─ get_latest_edition.py   scrape buttondown archive → latest edition number
 ├─ compare with highest git tag → stop if equal
 ├─ generator.py <N>
 │    ├─ download edition HTML (Selenium headless Chrome)
 │    ├─ parse header quote (#header) + categories/articles (#content > h2 / p > a)
 │    ├─ per article, first matching handler (url_handlers.py):
 │    │     YoutubeHandler  → YouTube Data API v3 (snippet) + thumbnail
 │    │     PDFHandler      → download PDF, pypdf text of pages 1–2
 │    │     GithubHandler   → trafilatura text/metadata + og:image
 │    │     DefaultHandler  → Playwright screenshot + trafilatura text/metadata
 │    │   (cached in dist/<N>/<index>.{html,png,jpg,json,pdf})
 │    └─ render template.tex (Jinja via latexbuild) → output.tex
 ├─ tectonic -X compile output.tex -Z continue-on-errors
 └─ release "HackerNewsPaper #N" with HackerNewsPaper-N.pdf, tag N
```

Votes/comments come from the link's `title` attribute (`Votes: 1872 Comments: 447`); the HN discussion URL from the `<span>` link.

## 2. Current status – the pipeline is dead

| Fact | Evidence |
|---|---|
| Last release **#772** (2025-12-02) | `gh release list` |
| Latest newsletter is **#814** (2026-10-16) → **42 editions missing** (#773–#814) | buttondown archive |
| Every scheduled run failed from Dec 2025 to 2026-02-01 | `gh run list` |
| Workflow is now **`disabled_inactivity`** (GitHub disables cron after 60 days without repo activity) | `gh workflow list --all` |
| Old run logs expired (HTTP 410), so the root cause was reproduced locally instead | – |

### Root cause (reproduced)
The archive page at <https://buttondown.com/hacker-newsletter/archive/> gained an `email-image` div as the first child of `div.email`. `get_latest_edition.py:29` does `link.find("div", class_="email").find("div").find("div").get_text()`, which now hits the image placeholder, so it raises `AttributeError: 'NoneType' object has no attribute 'get_text'`. Selecting `div.email-title` returns `814`.

Per-edition pages are now linked as `/archive/<N>/`. The old `/archive/hacker-newsletter-<N>` slug still returns the same page, and the edition parser (`#header`, `#content`, `h2`, `p > a`) **still works**: #814 gives 13 categories and 63 articles.

## 3. Known bugs and risks in the code

### Correctness
| # | Location | Problem |
|---|---|---|
| B1 | `get_latest_edition.py:29` | Breaks on the new archive markup (see above). **Blocker.** |
| B2 | `url_handlers.py:156` | `get_metadata(title, metadatadict={})` uses a **mutable default**: votes/comments from one YouTube/PDF article carry over to later ones that have none. |
| B3 | `url_handlers.py:227` | YouTube fallback regex `v=(.+?)` captures **only one character** when the URL has no `&`. It works today only because every link has `&utm_source…`. |
| B4 | `url_handlers.py:238` | No check for an empty `items` (private or removed video, bad key, quota) → `IndexError` kills the whole build. **Hit in #811, fixed:** falls back to a screenshot. |
| B5 | `url_handlers.py:296-297, 327` | GithubHandler: `metadata` can be `None` (→ `AttributeError`), `extract()` can return `None` (→ `TypeError` on `+`), `metadata.image` can be `None`. **Hit in #778, fixed:** falls back to a screenshot. |
| B6 | `generator.py:94-95` | `download_html` returns `None` on any error → `BeautifulSoup(None)` crash with no useful message. Bare `except:` hides causes everywhere. |
| B7 | `prep_body` / template | ~~No LaTeX escaping~~ **Corrected after a local build:** `latexbuild` escapes `\VAR{}` output (`\#`, `\&`, `\_`), and #814 compiled with 0 TeX errors. Missing glyphs (427 distinct over #773–#814) are **fixed** with fallback fonts (see PLAN Phase 2.1). The real TeX errors in #773/#774/#804/#811/#812 came from blank lines in titles and are fixed by title whitespace normalization. |
| B8 | `template.tex:92` | ~~Favorites layout may never trigger~~ **Corrected:** it does trigger (verified in the #814 PDF). |
| B9 | `generator.py:64` | Category text isn't stripped: #773 yields `'\n\n    #\n  \n  Sponsor\n'`. The README's "sponsor parsing is off" item. |
| B10 | `url_handlers.py:117` | `read()` opens JSON without `encoding="utf-8"` (breaks on Windows). |
| B11 | `YoutubeHandler.test` | Only `https://www.youtube.com/watch?v=` matches; `youtu.be`, `/shorts/`, `m.youtube`, Vimeo fall through to a screenshot. |
| B12 | `PDFHandler` | No thumbnail (open issue [#1 Add PDF support](https://github.com/bitfox-git/hackernewspaper/issues/1)). |
| B13 | `config.py:10` | `environ["YOUTUBE_API_KEY"]` → `KeyError` if unset, so it can't run locally without a key. Default issue `675` plus a hard-coded URL hack. |
| B14 | `add_stats` | trafilatura's metadata has a `comments` key that is `None`, so articles without HN stats (sponsors) show a `None` comments link. |
| B15 | `splitFirstSentenceParagraph` | Splits on any `.` within 200 chars, including version numbers: "Python 3.15.0 … Python 3.15." / "0 is the newest…". |
| B16 | `url_handlers.py` | `python-magic` segfaults on Windows (it clashes with `python-magic-bin`). **Fixed:** GIFs are now detected by magic bytes and the dependency is removed. |

### Robustness and performance
- `download_html` starts a **new Selenium Chrome per article** (~60 per edition), while Playwright is already open. That's slow, and it's two browser stacks.
- `generate_screenshot`: default 30 s timeout, no viewport/wait strategy, **cookie/GDPR banners** in shots (README TODO).
- GIF images are discarded via `python-magic`, which needs `libmagic` (not available on Windows without `python-magic-bin`).
- Tracking params (`utm_*`) are kept in printed/linked URLs.
- `generator.py` runs everything at import time, with no `main()`, logging, or per-article error isolation (README TODO at line 113).

### CI / workflow (`.github/workflows/main.yml`)
- "No new edition" is reported as **`exit 1` → a red run every day**. Real failures (Dec 2025) were indistinguishable from normal days and went unnoticed.
- Only the *latest* edition is built, so a missed week is never recovered (no backfill).
- Daily cron while the newsletter is weekly (Friday). Inactivity auto-disable kills it after 60 quiet days.
- `setup-python` has no `python-version` (uses the runner default). Pinned old action versions.
- The artifact upload `./*.*` grabs the whole repo root.

### Repo hygiene
- `requirements.txt` has 69 pins with many unused (`google-api-python-client`, `pythumb`, `trio`, …). There's no lockfile, Python ≥3.10 is required (`match`, `str | None`) but undeclared, and both Selenium and Playwright are present.
- No tests, and ruff is disabled in `.vscode/settings.json`.
- Template text errors: "derives it's contents directly from the **hackernewspaper**" (should be *hackernewsletter*), `\href{www.hackersnewsletter.com}` is a **wrong domain** and every `\href{www…}` lacks `https://` (relative link in the PDF).
- `faSymbolPerHostname`: duplicate `github.com` case, `flikr` typo, and `www.`-prefixed hostnames never match.
- README still mentions `pythumb`. Stale remote branches `curl`, `debug-711` (Aug 2024, superseded). `develop` == `main`.
- GitHub: 1 open issue (#1 PDF support), 0 open PRs. Secret `YOUTUBE_API_KEY` exists (set 2024-10-09; validity unknown).

## 4. Local end-to-end test (#814, 2026-10-19)
- `generator.py 814`: 63/63 articles in ~10 min (Selenium opens Chrome for every article), 63 screenshots, no YouTube key so the fallback was exercised.
- `tectonic -X compile`: ~3 min, **0 errors**, 27 pages, 13 MB. Warnings: 36 underfull / 6 overfull hboxes, plus missing emoji/Greek glyphs.
- Visible issues: cookie/consent banners in many screenshots (Phase 3), `None` comments on sponsors (B14), sentence split on version numbers (B15).

## 5. Local system (Windows 11)

| Requirement | Status |
|---|---|
| Python ≥ 3.10 | ✅ 3.12.1 (also 3.11) |
| Project venv + packages | ✅ `.venv` (requirements.txt) |
| Playwright Chromium | ✅ installed by `playwright install chromium` |
| Google Chrome (for Selenium) | ✅ Chrome for Testing auto-downloaded by Selenium Manager (removing Selenium removes this need) |
| Tectonic | ✅ 0.17.0 in `%LOCALAPPDATA%\Programs\tectonic` (not on PATH; winget has no package, so I used the GitHub release zip) |
| libmagic | ✅ no longer needed (B16) |
| `YOUTUBE_API_KEY` env var | ❌ not set |
| TeX Gyre Pagella + FontAwesome 4 | fetched automatically by Tectonic |
| git / gh | ✅ 2.40 / 2.89, logged in as `voslucas` with **admin** on `bitfox-git/hackernewspaper` |
| Docker, uv | ❌ not installed (optional) |
