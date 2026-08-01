# scraper

A small, dependency-light Python toolkit for scraping data across the web. It
backs the global `web-scraper` subagent but is fully usable on its own.

It handles the three common target types with one interface:

| Mode      | Target                          | Engine                     |
|-----------|---------------------------------|----------------------------|
| `static`  | Server-rendered HTML            | `requests` + BeautifulSoup |
| `dynamic` | JavaScript-rendered pages       | Playwright (headless)      |
| `api`     | JSON / XML endpoints            | `requests`                 |

## Install

```bash
pip install -r requirements.txt
# For --mode dynamic only (Chromium is pre-installed in CC web envs):
# playwright install chromium
```

## Usage

```bash
# Static page → repeating records → CSV
python -m scraper fetch https://example.com \
    --scope "article.post" \
    --select title="h2 a" url="h2 a@href" date="time@datetime" \
    --format csv --out posts.csv

# JS-rendered page
python -m scraper fetch https://example.com/app \
    --mode dynamic --wait-selector ".results .item" \
    --scope ".results .item" --select name=".name" price=".price"

# API endpoint → nested field
python -m scraper fetch https://api.example.com/v1/items \
    --mode api --json-path "data.items"

# Every table on a page
python -m scraper fetch https://example.com/stats --tables

# All links
python -m scraper fetch https://example.com --links --format json
```

### Selector syntax

- `field="css selector"` reads the element's text.
- `field="css selector@attr"` reads an attribute (e.g. `a@href`, `img@src`).
- `--scope "css"` yields one record per matching element; each `--select`
  selector is resolved *within* that element.

## Library API

```python
from scraper.fetchers import fetch
from scraper import extractors, output

res = fetch("static", "https://example.com")
records = extractors.extract_by_selectors(
    res.content, {"title": "h2 a", "url": "h2 a@href"}, scope="article")
print(output.serialize(records, "json"))
```

## Being a good citizen

- Respect each site's `robots.txt` and Terms of Service.
- The default User-Agent identifies the tool; keep request rates modest.
- Retries use exponential backoff to avoid hammering a struggling server.
