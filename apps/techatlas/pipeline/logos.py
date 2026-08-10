"""Company logo resolution via Wikidata (Stage 1.5).

Authenticity first, same rule as the rest of the pipeline: a logo is only
attached when it can be tied to the company *entity*, never guessed from the
ticker string alone by some image CDN. We resolve each company on Wikidata by
its **stock ticker** (property ``P249``) and take that entity's **official
logo** (property ``P154``, a file hosted on Wikimedia Commons). The ticker is a
strong entity key on the major exchanges, so a P249→P154 hit is the real
company's own mark — accurate and licensing-clean (Commons).

Design mirrors ``edgar.py``: the network lives in a thin
:class:`WikidataClient`; everything that turns a SPARQL response into facts is a
pure function (:func:`build_logo_query`, :func:`parse_logo_results`,
:func:`commons_thumb`) so it is unit-testable **offline** (this sandbox blocks
``query.wikidata.org``).
"""

from __future__ import annotations

import os
import time
from urllib.parse import quote

WIKIDATA_SPARQL_URL = "https://query.wikidata.org/sparql"

# Wikidata properties.
P_TICKER = "P249"     # stock exchange ticker symbol
P_LOGO = "P154"       # logo image (file on Wikimedia Commons)
P_EXCHANGE = "P414"   # stock exchange (ticker is usually a pq:P249 qualifier here)

DEFAULT_THUMB_WIDTH = 240


# =============================================================================
# Pure helpers (no network — unit-tested offline)
# =============================================================================

def _escape_sparql_literal(value: str) -> str:
    """Escape a string for safe inclusion inside a SPARQL double-quoted literal."""
    return (
        (value or "")
        .replace("\\", "\\\\")
        .replace('"', '\\"')
        .replace("\n", "")
        .replace("\r", "")
        .replace("\t", " ")
    )


def build_logo_query(tickers) -> str:
    """Build a SPARQL query mapping each ticker to its company logo (P154).

    Uses a ``VALUES`` block so one request resolves a whole batch. The ticker is
    echoed back in the results, so :func:`parse_logo_results` can key logos to
    the exact ticker that matched — no positional guessing.

    Critically, Wikidata stores the ticker symbol (``P249``) two ways and most
    companies use the *second*:

    * as a top-level truthy statement (``wdt:P249``), or — far more commonly —
    * as a **qualifier** (``pq:P249``) on the "stock exchange" statement
      (``p:P414``).

    A query that only checks ``wdt:P249`` therefore misses the large majority of
    filers. The ``UNION`` below matches either form, then requires the entity's
    own logo (``P154``).
    """
    seen: list[str] = []
    for t in tickers:
        t = (t or "").strip()
        if t and t not in seen:
            seen.append(t)
    values = " ".join(f'"{_escape_sparql_literal(t)}"' for t in seen)
    return (
        "SELECT ?ticker ?logo WHERE { "
        f"VALUES ?ticker {{ {values} }} "
        "{ "
        f"?company wdt:{P_TICKER} ?ticker . "
        "} UNION { "
        f"?company p:{P_EXCHANGE} [ pq:{P_TICKER} ?ticker ] . "
        "} "
        f"?company wdt:{P_LOGO} ?logo . "
        "}"
    )


def commons_thumb(url: str, width: int = DEFAULT_THUMB_WIDTH) -> str:
    """Return a raster-thumbnail URL for a Wikimedia Commons file value.

    P154 values look like
    ``http://commons.wikimedia.org/wiki/Special:FilePath/Foo.svg``. Forcing
    ``https`` and appending ``?width=`` yields a fixed-width thumbnail that
    renders in an ``<img>`` (SVG originals get rasterized), so a big source logo
    never bloats the page.
    """
    if not url:
        return ""
    url = url.strip()
    if url.startswith("http://"):
        url = "https://" + url[len("http://"):]
    if "Special:FilePath/" not in url or width <= 0:
        return url
    sep = "&" if "?" in url else "?"
    return f"{url}{sep}width={int(width)}"


def parse_logo_results(data: dict, width: int = DEFAULT_THUMB_WIDTH) -> dict:
    """Turn a Wikidata SPARQL JSON response into ``{ticker: thumb_url}``.

    Keeps the first logo seen per ticker (SPARQL may return several bindings for
    an entity with more than one logo). Never fabricates: tickers with no P154
    binding simply do not appear in the result.
    """
    out: dict = {}
    bindings = (((data or {}).get("results") or {}).get("bindings")) or []
    for row in bindings:
        if not isinstance(row, dict):
            continue
        ticker = ((row.get("ticker") or {}).get("value") or "").strip()
        logo = ((row.get("logo") or {}).get("value") or "").strip()
        if not ticker or not logo or ticker in out:
            continue
        out[ticker] = commons_thumb(logo, width)
    return out


# =============================================================================
# Thin network client
# =============================================================================

class WikidataClient:
    """Rate-limited Wikidata Query Service client (SPARQL → JSON).

    Wikidata asks for a descriptive User-Agent; it is read from
    ``WIKIDATA_USER_AGENT`` (falling back to ``SEC_USER_AGENT`` so the deploy
    only needs one contact string) and never hardcoded.
    """

    def __init__(self, user_agent: str | None = None, max_rps: float = 2.0):
        ua = (
            user_agent
            or os.environ.get("WIKIDATA_USER_AGENT")
            or os.environ.get("SEC_USER_AGENT")
        )
        if not ua or not ua.strip():
            raise RuntimeError(
                "WIKIDATA_USER_AGENT (or SEC_USER_AGENT) is not set. The Wikidata "
                "Query Service requires a descriptive User-Agent with a contact, "
                "e.g. 'TechAtlas Agent you@example.com'. Set it in the environment."
            )
        self.user_agent = ua.strip()
        self._min_interval = 1.0 / max_rps if max_rps > 0 else 0.0
        self._last = 0.0
        self._session = None

    def _sess(self):
        if self._session is None:
            import requests  # lazy: keeps pure parsers dependency-free

            s = requests.Session()
            s.headers.update(
                {"User-Agent": self.user_agent, "Accept": "application/sparql-results+json"}
            )
            self._session = s
        return self._session

    def _throttle(self) -> None:
        if self._min_interval <= 0:
            return
        wait = self._min_interval - (time.monotonic() - self._last)
        if wait > 0:
            time.sleep(wait)
        self._last = time.monotonic()

    def _query(self, sparql: str, retries: int = 3) -> dict:
        import requests  # lazy

        url = f"{WIKIDATA_SPARQL_URL}?format=json&query={quote(sparql)}"
        backoff = 1.0
        last_exc: Exception | None = None
        for _ in range(retries):
            self._throttle()
            try:
                resp = self._sess().get(url, timeout=45)
            except requests.RequestException as exc:  # transient network error
                last_exc = exc
                time.sleep(backoff)
                backoff *= 2
                continue
            if resp.status_code in (429, 503):
                time.sleep(backoff)
                backoff *= 2
                continue
            resp.raise_for_status()
            return resp.json()
        if last_exc is not None:
            raise last_exc
        raise RuntimeError("Wikidata query failed after retries")

    def resolve_logos(self, tickers, *, width: int = DEFAULT_THUMB_WIDTH,
                      chunk: int = 60) -> dict:
        """Resolve ``{ticker: thumb_url}`` for many tickers, batched by ``chunk``."""
        clean = [(t or "").strip() for t in tickers if (t or "").strip()]
        out: dict = {}
        for i in range(0, len(clean), max(1, chunk)):
            batch = clean[i:i + max(1, chunk)]
            data = self._query(build_logo_query(batch))
            out.update(parse_logo_results(data, width))
        return out
