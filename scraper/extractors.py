"""Turn fetched content into structured records.

Extraction is deliberately simple and composable:

* :func:`extract_by_selectors` – map field names to CSS selectors.
* :func:`extract_tables`       – pull every HTML ``<table>`` as rows.
* :func:`extract_links`        – all anchors with absolute URLs.
* :func:`extract_json_path`    – dotted-path lookup into API JSON.
"""

from __future__ import annotations

import json
from typing import Any, Optional
from urllib.parse import urljoin

from bs4 import BeautifulSoup


def _soup(html: str) -> BeautifulSoup:
    # lxml is fast; fall back to the stdlib parser if it is unavailable.
    try:
        return BeautifulSoup(html, "lxml")
    except Exception:
        return BeautifulSoup(html, "html.parser")


def _node_value(node, attr: Optional[str]) -> str:
    if attr:
        return (node.get(attr) or "").strip()
    return node.get_text(strip=True)


def extract_by_selectors(
    html: str,
    selectors: dict[str, str],
    *,
    scope: Optional[str] = None,
) -> list[dict[str, str]]:
    """Extract records using a ``{field: selector}`` mapping.

    A selector may carry an ``@attr`` suffix to read an attribute instead of
    text, e.g. ``"a.title@href"``.

    When ``scope`` is given, one record is produced per element matching
    ``scope`` and each field selector is resolved *within* that element.
    Otherwise a single record is produced from the whole document.
    """
    soup = _soup(html)

    def parse_selector(sel: str) -> tuple[str, Optional[str]]:
        if "@" in sel:
            css, attr = sel.rsplit("@", 1)
            return css.strip(), attr.strip()
        return sel.strip(), None

    parsed = {field: parse_selector(sel) for field, sel in selectors.items()}

    if scope:
        records: list[dict[str, str]] = []
        for container in soup.select(scope):
            record: dict[str, str] = {}
            for field, (css, attr) in parsed.items():
                node = container.select_one(css) if css else container
                record[field] = _node_value(node, attr) if node else ""
            records.append(record)
        return records

    record = {}
    for field, (css, attr) in parsed.items():
        node = soup.select_one(css)
        record[field] = _node_value(node, attr) if node else ""
    return [record]


def extract_tables(html: str) -> list[list[dict[str, str]]]:
    """Return each HTML table as a list of row dicts keyed by header cells."""
    soup = _soup(html)
    tables: list[list[dict[str, str]]] = []
    for table in soup.find_all("table"):
        rows = table.find_all("tr")
        if not rows:
            continue
        header_cells = rows[0].find_all(["th", "td"])
        headers = [c.get_text(strip=True) or f"col_{i}"
                   for i, c in enumerate(header_cells)]
        body: list[dict[str, str]] = []
        for tr in rows[1:]:
            cells = tr.find_all(["td", "th"])
            if not cells:
                continue
            values = [c.get_text(strip=True) for c in cells]
            body.append({headers[i] if i < len(headers) else f"col_{i}": v
                         for i, v in enumerate(values)})
        if body:
            tables.append(body)
    return tables


def extract_links(html: str, base_url: str = "") -> list[dict[str, str]]:
    """Return all anchors as ``{"text": ..., "url": <absolute>}`` records."""
    soup = _soup(html)
    links: list[dict[str, str]] = []
    for a in soup.find_all("a", href=True):
        href = a["href"].strip()
        if not href or href.startswith(("#", "javascript:", "mailto:")):
            continue
        links.append({
            "text": a.get_text(strip=True),
            "url": urljoin(base_url, href) if base_url else href,
        })
    return links


def extract_json_path(payload: str, path: str) -> Any:
    """Read a dotted path out of a JSON string.

    Supports object keys and numeric list indices, e.g.
    ``"data.items.0.name"``. Returns ``None`` if the path does not resolve.
    """
    try:
        data: Any = json.loads(payload)
    except json.JSONDecodeError:
        return None
    if not path:
        return data
    for part in path.split("."):
        if isinstance(data, list):
            try:
                data = data[int(part)]
            except (ValueError, IndexError):
                return None
        elif isinstance(data, dict):
            if part not in data:
                return None
            data = data[part]
        else:
            return None
    return data
