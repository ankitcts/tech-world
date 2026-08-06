"""SEC EDGAR client + pure parsers for the TechAtlas daily agent (Stage 1).

Authenticity first: this module only ever surfaces values it can attribute to an
authoritative SEC filing. The conservative extractors return ``None`` (never a
guess) when a value cannot be confidently read from the source document.

Design split so the logic is unit-testable **offline** (this sandbox blocks
`www.sec.gov`):

* Thin network methods live on :class:`SecClient` (``requests`` imported lazily
  so the pure parsers below have no third-party dependency).
* Everything that turns bytes into facts is a **pure function** —
  :func:`parse_company_tickers`, :func:`parse_submission`,
  :func:`latest_filing`, :func:`extract_employees`, :func:`extract_leadership` —
  exercised against inline fixtures in ``test_edgar.py``.

SEC fair-access policy requires a descriptive User-Agent; it is read from the
``SEC_USER_AGENT`` environment variable and never hardcoded.
"""

from __future__ import annotations

import os
import re
import time
import xml.etree.ElementTree as ET
from html import unescape

# --- Endpoints (documented; hit only from the thin network methods) ----------
COMPANY_TICKERS_URL = "https://www.sec.gov/files/company_tickers.json"
SUBMISSIONS_URL = "https://data.sec.gov/submissions/CIK{cik:010d}.json"
ARCHIVE_URL = (
    "https://www.sec.gov/Archives/edgar/data/{cik}/{accession}/{document}"
)

FORMS_10K = frozenset({"10-K"})
FORMS_OWNERSHIP = frozenset({"3", "4", "5"})


# =============================================================================
# Pure parsers  (no network, no third-party deps — unit-tested offline)
# =============================================================================

def parse_company_tickers(data: dict) -> list[dict]:
    """Normalize ``company_tickers.json`` into ``[{cik, ticker, title}]``.

    The SEC file is a dict keyed by a stringified index; each value carries
    ``cik_str`` (int), ``ticker`` and ``title``. ``cik`` is returned as an int
    (zero-pad only when building URLs).
    """
    out: list[dict] = []
    for entry in (data or {}).values():
        if not isinstance(entry, dict):
            continue
        cik = entry.get("cik_str")
        ticker = (entry.get("ticker") or "").strip()
        title = (entry.get("title") or "").strip()
        if cik is None or not title:
            continue
        out.append({"cik": int(cik), "ticker": ticker, "title": title})
    return out


def parse_submission(data: dict) -> dict:
    """Flatten a ``submissions/CIK*.json`` document into the fields we use.

    Returns a dict with ``cik`` (int), ``name``, ``sic``, ``sic_description``,
    ``tickers``, ``exchanges``, ``hq_state`` (business ``stateOrCountry``),
    ``former_names`` and ``filings`` — the last being a list of per-filing dicts
    ``{form, accession, primary_document, filing_date, report_date}`` rebuilt
    from EDGAR's parallel ``filings.recent`` arrays.
    """
    data = data or {}
    addresses = data.get("addresses") or {}
    business = addresses.get("business") or {}
    former = [
        (fn.get("name") or "").strip()
        for fn in (data.get("formerNames") or [])
        if (fn.get("name") or "").strip()
    ]

    recent = (data.get("filings") or {}).get("recent") or {}
    forms = recent.get("form") or []
    accessions = recent.get("accessionNumber") or []
    primary_docs = recent.get("primaryDocument") or []
    filing_dates = recent.get("filingDate") or []
    report_dates = recent.get("reportDate") or []

    filings: list[dict] = []
    for i, form in enumerate(forms):
        filings.append(
            {
                "form": form,
                "accession": accessions[i] if i < len(accessions) else "",
                "primary_document": primary_docs[i] if i < len(primary_docs) else "",
                "filing_date": filing_dates[i] if i < len(filing_dates) else "",
                "report_date": report_dates[i] if i < len(report_dates) else "",
            }
        )

    cik_raw = data.get("cik")
    return {
        "cik": int(cik_raw) if cik_raw not in (None, "") else None,
        "name": (data.get("name") or "").strip(),
        "sic": (str(data.get("sic")).strip() if data.get("sic") not in (None, "") else None),
        "sic_description": (data.get("sicDescription") or "").strip() or None,
        "tickers": list(data.get("tickers") or []),
        "exchanges": list(data.get("exchanges") or []),
        "hq_state": (business.get("stateOrCountry") or "").strip() or None,
        "former_names": former,
        "filings": filings,
    }


def _archive_url(cik: int, accession: str, document: str) -> str:
    return ARCHIVE_URL.format(
        cik=int(cik), accession=(accession or "").replace("-", ""), document=document
    )


def ownership_xml_url(cik, accession: str, primary_document: str) -> str | None:
    """Raw ownership-XML URL for a Form 3/4/5 filing.

    EDGAR lists an XSL-rendered *HTML* page as the filing's ``primaryDocument``
    for ownership forms (e.g. ``xslF345X05/wf-form4_1.xml``); fetching that
    yields HTML the XML parser can't read. The raw XML sits at the accession
    root under the same filename, so we drop any leading render-path segment.
    """
    if cik is None or not primary_document:
        return None
    raw = primary_document.split("/")[-1]  # strip any "xslF345X0N/" render prefix
    return _archive_url(cik, accession, raw)


def latest_filing(submission: dict, forms) -> dict | None:
    """Most recent filing in ``submission`` whose ``form`` is in ``forms``.

    Returns ``{form, accession, primary_document, report_date, filing_date,
    url}`` (``url`` is the archive URL of the primary document) or ``None`` if
    the filer has no matching filing. "Most recent" is by ``filing_date``
    (ISO ``YYYY-MM-DD`` sorts lexicographically), tie-broken by list order,
    which EDGAR already returns newest-first.
    """
    forms = set(forms)
    cik = submission.get("cik")
    best: dict | None = None
    for f in submission.get("filings") or []:
        if f.get("form") not in forms:
            continue
        if best is None or (f.get("filing_date") or "") > (best.get("filing_date") or ""):
            best = f
    if best is None:
        return None
    return {
        "form": best["form"],
        "accession": best.get("accession") or "",
        "primary_document": best.get("primary_document") or "",
        "report_date": best.get("report_date") or "",
        "filing_date": best.get("filing_date") or "",
        "url": _archive_url(cik, best.get("accession") or "", best.get("primary_document") or "")
        if cik is not None and best.get("primary_document")
        else None,
    }


# --- Employee-count extraction ----------------------------------------------

_NUM = r"(\d{1,3}(?:,\d{3})+|\d+)"

# Each pattern requires the literal word "employees" adjacent to the number
# (except "employed approximately N", which is the canonical inverted phrasing).
# Ordered most-specific first; all patterns are scanned and matches merged.
_EMP_PATTERNS = [
    re.compile(
        r"(?i)\bhad\s+(?:approximately\s+|about\s+|roughly\s+|nearly\s+)?"
        + _NUM
        + r"\s+(?:full[- ]?time\s+|part[- ]?time\s+|regular\s+|total\s+)?employees\b"
    ),
    re.compile(
        r"(?i)\bapproximately\s+"
        + _NUM
        + r"\s+(?:full[- ]?time\s+|part[- ]?time\s+|regular\s+|total\s+)?employees\b"
    ),
    # Inverted phrasing "employed approximately N employees/people/workers".
    # Requires an employment noun after the number so it can't match unrelated
    # prose like "employed 4 different methods".
    re.compile(
        r"(?i)\bemployed\s+(?:approximately\s+|about\s+|roughly\s+|nearly\s+)?"
        + _NUM
        + r"\s+(?:full[- ]?time\s+|part[- ]?time\s+|regular\s+|total\s+)?"
        + r"(?:employees|persons|people|workers|staff|individuals)\b"
    ),
    re.compile(
        r"(?i)\b"
        + _NUM
        + r"\s+(?:full[- ]?time\s+|part[- ]?time\s+|regular\s+|total\s+)?employees\b"
    ),
]


def visible_text(html: str) -> str:
    """Public: cleaned, LLM-ready plain text from filing HTML (see _visible_text)."""
    return _visible_text(html)


def _visible_text(html: str) -> str:
    """Strip tags/entities from filing HTML to a single normalized text line."""
    text = re.sub(r"(?is)<(script|style)[^>]*>.*?</\1>", " ", html or "")
    text = re.sub(r"(?s)<[^>]+>", " ", text)
    text = unescape(text)
    text = text.replace("\xa0", " ")
    text = re.sub(r"\s+", " ", text).strip()
    return text


def _sentence_around(text: str, start: int, end: int) -> str:
    left = text.rfind(".", 0, start)
    right = text.find(".", end)
    s = left + 1 if left != -1 else max(0, start - 80)
    e = right + 1 if right != -1 else min(len(text), end + 60)
    return text[s:e].strip()


def extract_employees(
    html: str,
    *,
    as_of: str | None = None,
    source_url: str | None = None,
    accession: str | None = None,
) -> dict | None:
    """Conservatively extract a headcount from 10-K primary-document HTML.

    Strips tags to text, then looks for a number the filing explicitly labels as
    "employees". Matches near an "as of" clause are preferred (that is the
    disclosure sentence). Returns
    ``{value, source, source_url, accession, as_of, matched}`` or ``None`` when
    no confident match exists — it never guesses.
    """
    text = _visible_text(html)
    if not text:
        return None

    lowered = text.lower()
    candidates: list[tuple[int, int, int, int]] = []  # (score, -idx, value, idx)
    seen: set[int] = set()

    for pattern in _EMP_PATTERNS:
        for m in pattern.finditer(text):
            idx = m.start()
            if idx in seen:
                continue
            seen.add(idx)
            raw = m.group(1).replace(",", "")
            if not raw.isdigit():
                continue
            value = int(raw)
            if value <= 0:
                continue
            # Prefer a match whose sentence is anchored by "as of".
            window = lowered[max(0, idx - 160): idx]
            score = 1 if "as of" in window else 0
            candidates.append((score, -idx, value, idx))

    if not candidates:
        return None

    # Highest score wins; tie-break to the earliest occurrence in the document.
    score, _, value, idx = max(candidates)
    # Recover the matched span end for the sentence snippet.
    end = idx
    for pattern in _EMP_PATTERNS:
        m = pattern.match(text, idx)
        if m:
            end = m.end()
            break
    else:
        end = idx + 20

    return {
        "value": value,
        "source": "sec-10k",
        "source_url": source_url,
        "accession": accession,
        "as_of": as_of,
        "matched": _sentence_around(text, idx, end),
    }


# --- Leadership extraction (Forms 3/4/5 ownership XML) -----------------------

def _is_true(value: str | None) -> bool:
    return (value or "").strip().lower() in {"1", "true", "yes", "y"}


def _localname(tag: str) -> str:
    return tag.rsplit("}", 1)[-1]


def _find_local(elem, name):
    """Namespace-insensitive first descendant whose local tag == ``name``."""
    for child in elem.iter():
        if _localname(child.tag) == name and child is not elem:
            return child
    return None


def extract_leadership(
    xml: str,
    *,
    source_url: str | None = None,
    accession: str | None = None,
    as_of: str | None = None,
) -> list[dict]:
    """Parse officer/director records from a Form 3/4/5 ownership document.

    For each ``<reportingOwner>`` reads ``<rptOwnerName>`` and the relationship
    flags (``<isDirector>``, ``<isOfficer>``, ``<officerTitle>``). A person who
    is both an officer and a director yields two entries (officer first, using
    the disclosed title). Every entry carries provenance. Emits ``[]`` on
    unparseable XML rather than raising — Stage 1 must degrade to "empty", never
    fabricate.
    """
    try:
        root = ET.fromstring(xml)
    except ET.ParseError:
        return []

    people: list[dict] = []
    owners = [e for e in root.iter() if _localname(e.tag) == "reportingOwner"]
    for owner in owners:
        name_el = _find_local(owner, "rptOwnerName")
        name = (name_el.text or "").strip() if name_el is not None else ""
        if not name:
            continue
        rel = None
        for e in owner.iter():
            if _localname(e.tag) == "reportingOwnerRelationship":
                rel = e
                break
        if rel is None:
            continue

        is_director = _is_true(_text_local(rel, "isDirector"))
        is_officer = _is_true(_text_local(rel, "isOfficer"))
        officer_title = (_text_local(rel, "officerTitle") or "").strip()

        if is_officer:
            people.append(
                {
                    "name": name,
                    "title": officer_title or "Officer",
                    "role_type": "officer",
                    "source_url": source_url,
                    "accession": accession,
                    "as_of": as_of,
                }
            )
        if is_director:
            people.append(
                {
                    "name": name,
                    "title": "Director",
                    "role_type": "director",
                    "source_url": source_url,
                    "accession": accession,
                    "as_of": as_of,
                }
            )
    return people


def _text_local(parent, name) -> str | None:
    for child in parent.iter():
        if _localname(child.tag) == name and child is not parent:
            return child.text
    return None


# =============================================================================
# Thin network client  (exercised for real on Vercel; blocked in this sandbox)
# =============================================================================

class SecClient:
    """Rate-limited SEC EDGAR HTTP client.

    Keeps I/O in a handful of thin methods; all parsing is delegated to the pure
    functions above. Requires ``SEC_USER_AGENT`` (SEC fair-access policy).
    """

    def __init__(self, user_agent: str | None = None, max_rps: float = 8.0):
        ua = user_agent or os.environ.get("SEC_USER_AGENT")
        if not ua or not ua.strip():
            raise RuntimeError(
                "SEC_USER_AGENT is not set. SEC fair-access policy requires a "
                "descriptive User-Agent like 'TechAtlas Agent you@example.com'. "
                "Set it in the environment (never hardcode it)."
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
                {"User-Agent": self.user_agent, "Accept-Encoding": "gzip, deflate"}
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

    def _get(self, url: str, *, host: str | None = None, retries: int = 4):
        import requests  # lazy

        headers = {"Host": host} if host else {}
        backoff = 1.0
        last_exc: Exception | None = None
        for attempt in range(retries):
            self._throttle()
            try:
                resp = self._sess().get(url, headers=headers, timeout=30)
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
            return resp
        if last_exc is not None:
            raise last_exc
        raise RuntimeError(f"SEC request failed after {retries} retries: {url}")

    def company_tickers(self) -> list[dict]:
        return parse_company_tickers(self._get(COMPANY_TICKERS_URL).json())

    def submission(self, cik: int | str) -> dict:
        url = SUBMISSIONS_URL.format(cik=int(cik))
        return parse_submission(self._get(url, host="data.sec.gov").json())

    def get_text(self, url: str) -> str:
        """Fetch a primary document (10-K HTML / ownership XML) as text."""
        return self._get(url).text
