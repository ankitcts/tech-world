"""Fetch strategies for different kinds of web targets.

Three modes cover the vast majority of scraping needs:

* ``static``  – server-rendered HTML fetched over plain HTTP (fast, cheap).
* ``dynamic`` – JavaScript-rendered pages loaded through a headless browser.
* ``api``     – JSON / XML endpoints returning structured data directly.

Each fetcher returns a :class:`FetchResult` so the rest of the pipeline does
not care how the bytes were obtained.
"""

from __future__ import annotations

import time
from dataclasses import dataclass, field
from typing import Optional

import requests

DEFAULT_UA = (
    "Mozilla/5.0 (X11; Linux x86_64) AppleWebKit/537.36 "
    "(KHTML, like Gecko) Chrome/124.0 Safari/537.36 web-scraper-agent/1.0"
)
DEFAULT_TIMEOUT = 30


@dataclass
class FetchResult:
    """Normalized result returned by every fetcher."""

    url: str
    status: int
    content: str
    content_type: str = ""
    mode: str = "static"
    elapsed: float = 0.0
    headers: dict = field(default_factory=dict)


def fetch_static(
    url: str,
    *,
    headers: Optional[dict] = None,
    timeout: int = DEFAULT_TIMEOUT,
    retries: int = 3,
    backoff: float = 2.0,
) -> FetchResult:
    """Fetch a URL over plain HTTP with retries and exponential backoff."""
    hdrs = {"User-Agent": DEFAULT_UA, "Accept": "*/*"}
    if headers:
        hdrs.update(headers)

    last_exc: Optional[Exception] = None
    start = time.monotonic()
    for attempt in range(retries):
        try:
            resp = requests.get(url, headers=hdrs, timeout=timeout)
            return FetchResult(
                url=resp.url,
                status=resp.status_code,
                content=resp.text,
                content_type=resp.headers.get("Content-Type", ""),
                mode="static",
                elapsed=time.monotonic() - start,
                headers=dict(resp.headers),
            )
        except requests.RequestException as exc:  # network / timeout errors
            last_exc = exc
            if attempt < retries - 1:
                time.sleep(backoff * (2 ** attempt))
    raise RuntimeError(f"static fetch failed for {url}: {last_exc}")


def fetch_api(
    url: str,
    *,
    method: str = "GET",
    headers: Optional[dict] = None,
    params: Optional[dict] = None,
    json_body: Optional[dict] = None,
    timeout: int = DEFAULT_TIMEOUT,
    retries: int = 3,
    backoff: float = 2.0,
) -> FetchResult:
    """Call a JSON/XML API endpoint. Returns the raw response body as text."""
    hdrs = {"User-Agent": DEFAULT_UA, "Accept": "application/json, */*"}
    if headers:
        hdrs.update(headers)

    last_exc: Optional[Exception] = None
    start = time.monotonic()
    for attempt in range(retries):
        try:
            resp = requests.request(
                method.upper(),
                url,
                headers=hdrs,
                params=params,
                json=json_body,
                timeout=timeout,
            )
            return FetchResult(
                url=resp.url,
                status=resp.status_code,
                content=resp.text,
                content_type=resp.headers.get("Content-Type", ""),
                mode="api",
                elapsed=time.monotonic() - start,
                headers=dict(resp.headers),
            )
        except requests.RequestException as exc:
            last_exc = exc
            if attempt < retries - 1:
                time.sleep(backoff * (2 ** attempt))
    raise RuntimeError(f"api fetch failed for {url}: {last_exc}")


def fetch_dynamic(
    url: str,
    *,
    wait_selector: Optional[str] = None,
    wait_ms: int = 0,
    timeout: int = DEFAULT_TIMEOUT,
    headers: Optional[dict] = None,
) -> FetchResult:
    """Render a JS-heavy page with a headless browser and return the DOM HTML.

    Uses Playwright. In this environment Chromium is pre-installed and
    discovered automatically via ``PLAYWRIGHT_BROWSERS_PATH``; no
    ``playwright install`` step is required.
    """
    try:
        from playwright.sync_api import sync_playwright
    except ImportError as exc:  # pragma: no cover - depends on env
        raise RuntimeError(
            "Playwright is not installed. Run `pip install playwright` "
            "(Chromium is already present in this environment)."
        ) from exc

    start = time.monotonic()
    with sync_playwright() as pw:
        browser = pw.chromium.launch(headless=True)
        context = browser.new_context(
            user_agent=(headers or {}).get("User-Agent", DEFAULT_UA),
            extra_http_headers={k: v for k, v in (headers or {}).items()
                                if k.lower() != "user-agent"},
        )
        page = context.new_page()
        response = page.goto(url, timeout=timeout * 1000, wait_until="networkidle")
        if wait_selector:
            page.wait_for_selector(wait_selector, timeout=timeout * 1000)
        if wait_ms:
            page.wait_for_timeout(wait_ms)
        html = page.content()
        status = response.status if response else 0
        ctype = ""
        if response:
            ctype = response.headers.get("content-type", "")
        browser.close()

    return FetchResult(
        url=url,
        status=status,
        content=html,
        content_type=ctype or "text/html",
        mode="dynamic",
        elapsed=time.monotonic() - start,
    )


def fetch(mode: str, url: str, **kwargs) -> FetchResult:
    """Dispatch to the right fetcher by mode name."""
    if mode == "static":
        return fetch_static(url, **kwargs)
    if mode == "dynamic":
        return fetch_dynamic(url, **kwargs)
    if mode == "api":
        return fetch_api(url, **kwargs)
    raise ValueError(f"unknown mode: {mode!r} (expected static|dynamic|api)")
