"""Offline unit tests for the SEC EDGAR Stage-1 parsers.

Runs with **no network** (this sandbox blocks SEC + Atlas) against inline
fixtures. Plain asserts; run from the repo root:

    python3 -m apps.techatlas.pipeline.test_edgar
"""

from __future__ import annotations

from apps.techatlas.pipeline import build_dataset, edgar, logos, sic
from apps.techatlas.pipeline.tiers import classify_tier


# --- raw-filing storage (pure; fake repo) -----------------------------------

class _FakeRaw:
    def __init__(self):
        self.docs = []

    def upsert(self, doc):
        self.docs.append(doc)


def test_store_raw_reference_only_by_default():
    # Default (store_full=False): keep only a URL reference + metadata, no text/raw.
    repo, counts = _FakeRaw(), {}
    html = "<html><body><p>Hello &amp; world</p></body></html>"
    filing = {"accession": "0001-24-1", "form": "10-K",
              "url": "http://x/10k.htm", "report_date": "2024-12-31"}
    build_dataset._store_raw(repo, {"id": "aapl", "ticker": "AAPL"}, 320193,
                             filing, html, "html", "2026-01-01T00:00:00Z", counts, False)
    assert len(repo.docs) == 1
    d = repo.docs[0]
    assert d["id"] == "0001-24-1" and d["company_id"] == "aapl" and d["form"] == "10-K"
    assert d["cik"] == "0000320193" and d["url"] == "http://x/10k.htm"
    assert d["as_of"] == "2024-12-31" and d["byte_size"] == len(html)
    assert d["has_text"] is False and "text" not in d and "raw" not in d
    assert counts["filings_stored"] == 1


def test_store_raw_full_keeps_cleaned_text_and_small_raw():
    repo, counts = _FakeRaw(), {}
    html = "<html><body><p>Hello &amp; world</p><script>x=1</script></body></html>"
    filing = {"accession": "0001-24-1", "form": "10-K", "url": "http://x/10k.htm",
              "report_date": "2024-12-31"}
    build_dataset._store_raw(repo, {"id": "aapl", "ticker": "AAPL"}, 320193,
                             filing, html, "html", "t", counts, True)
    d = repo.docs[0]
    assert d["has_text"] is True
    assert "Hello & world" in d["text"] and "<p>" not in d["text"] and "x=1" not in d["text"]
    assert d["raw"] == html and d["raw_stored"] is True
    assert counts["filings_stored"] == 1


def test_store_raw_skips_without_accession():
    repo, counts = _FakeRaw(), {}
    build_dataset._store_raw(repo, {"id": "x"}, 1, {"accession": ""}, "data", "xml", "t", counts, True)
    assert repo.docs == [] and counts == {}


def test_store_raw_full_drops_oversized_raw_but_keeps_text():
    repo, counts = _FakeRaw(), {}
    big = "a" * (build_dataset.RAW_MAX_BYTES + 10)  # over the raw-bytes cap
    filing = {"accession": "acc", "form": "4", "filing_date": "2025-01-10"}
    build_dataset._store_raw(repo, {"id": "c", "ticker": "C"}, 5, filing, big, "xml", "t", counts, True)
    d = repo.docs[0]
    assert d["raw"] is None and d["raw_stored"] is False
    assert d["byte_size"] == len(big)
    assert len(d["text"]) == min(len(big), build_dataset.TEXT_MAX_BYTES)


# --- Employee-count extraction ----------------------------------------------

def _wrap(sentence: str) -> str:
    """A minimal 10-K-ish HTML body around a human-capital sentence."""
    return (
        "<html><body><p>Item 1. Business</p>"
        "<div><span>" + sentence + "</span></div>"
        "<p>Item 1A. Risk Factors</p></body></html>"
    )


def test_employees_approximately_as_of():
    html = _wrap(
        "As of December 31, 2024, we had approximately 25,300 full-time employees."
    )
    got = edgar.extract_employees(
        html, as_of="2024-12-31", source_url="http://x/10k.htm", accession="0001-24-1"
    )
    assert got is not None
    assert got["value"] == 25300, got
    assert got["source"] == "sec-10k"
    assert got["source_url"] == "http://x/10k.htm"
    assert got["accession"] == "0001-24-1"
    assert got["as_of"] == "2024-12-31"
    assert "25,300" in got["matched"]


def test_employees_millions_with_commas():
    # A very large filer (Walmart-scale) — commas must parse to a full int.
    html = _wrap("As of January 31, 2025, we employed approximately 2,100,000 employees worldwide.")
    got = edgar.extract_employees(html)
    assert got is not None and got["value"] == 2100000, got


def test_employees_one_point_six_million():
    html = _wrap("As of the end of fiscal 2024, the Company had 1,600,000 employees.")
    got = edgar.extract_employees(html)
    assert got is not None and got["value"] == 1600000, got
    assert classify_tier(got["value"]) == "300k-plus"


def test_employees_employed_approximately_phrasing():
    html = _wrap("We employed approximately 164,000 people as of September 28, 2024.")
    got = edgar.extract_employees(html)
    assert got is not None and got["value"] == 164000, got


def test_employees_no_confident_match_returns_none():
    # No number is labelled "employees"; must NOT guess from unrelated figures.
    html = _wrap(
        "Our revenue was 383,285 million dollars and we operate in 175 countries."
    )
    assert edgar.extract_employees(html) is None


def test_employees_employed_without_headcount_noun_is_ignored():
    # "employed N <non-headcount>" must NOT be read as a headcount.
    html = _wrap("We employed 4 different methods to evaluate our goodwill.")
    assert edgar.extract_employees(html) is None


def test_employees_employed_with_headcount_noun_matches():
    html = _wrap("As of year-end we employed approximately 5,000 workers.")
    got = edgar.extract_employees(html)
    assert got is not None and got["value"] == 5000, got


def test_employees_prefers_as_of_sentence_over_earlier_mention():
    html = _wrap(
        "Historically we had 500 employees in 2010. "
        "As of December 31, 2024, we had 48,000 employees."
    )
    got = edgar.extract_employees(html)
    assert got is not None and got["value"] == 48000, got


# --- Form 4 ownership XML parsing -------------------------------------------

_FORM4_OFFICER_AND_DIRECTOR = """<?xml version="1.0"?>
<ownershipDocument>
  <reportingOwner>
    <reportingOwnerId><rptOwnerName>Cook Timothy D</rptOwnerName></reportingOwnerId>
    <reportingOwnerRelationship>
      <isDirector>1</isDirector>
      <isOfficer>1</isOfficer>
      <isTenPercentOwner>0</isTenPercentOwner>
      <officerTitle>Chief Executive Officer</officerTitle>
    </reportingOwnerRelationship>
  </reportingOwner>
</ownershipDocument>"""

_FORM4_OFFICER_ONLY = """<?xml version="1.0"?>
<ownershipDocument>
  <reportingOwner>
    <reportingOwnerId><rptOwnerName>Parekh Shantanu Narayen</rptOwnerName></reportingOwnerId>
    <reportingOwnerRelationship>
      <isDirector>false</isDirector>
      <isOfficer>true</isOfficer>
      <officerTitle>Chief Financial Officer</officerTitle>
    </reportingOwnerRelationship>
  </reportingOwner>
</ownershipDocument>"""

_FORM4_DIRECTOR_ONLY = """<?xml version="1.0"?>
<ownershipDocument>
  <reportingOwner>
    <reportingOwnerId><rptOwnerName>Jung Andrea</rptOwnerName></reportingOwnerId>
    <reportingOwnerRelationship>
      <isDirector>1</isDirector>
      <isOfficer>0</isOfficer>
    </reportingOwnerRelationship>
  </reportingOwner>
</ownershipDocument>"""


def test_leadership_officer_and_director_yields_two_entries():
    people = edgar.extract_leadership(
        _FORM4_OFFICER_AND_DIRECTOR, source_url="http://x/f4.xml",
        accession="0001-25-9", as_of="2025-01-10",
    )
    assert len(people) == 2, people
    officer = people[0]
    assert officer["name"] == "Cook Timothy D"
    assert officer["role_type"] == "officer"
    assert officer["title"] == "Chief Executive Officer"
    assert officer["source_url"] == "http://x/f4.xml"
    assert officer["accession"] == "0001-25-9"
    assert officer["as_of"] == "2025-01-10"
    director = people[1]
    assert director["role_type"] == "director" and director["title"] == "Director"


def test_leadership_officer_only():
    people = edgar.extract_leadership(_FORM4_OFFICER_ONLY)
    assert len(people) == 1 and people[0]["role_type"] == "officer"
    assert people[0]["title"] == "Chief Financial Officer"


def test_leadership_director_only():
    people = edgar.extract_leadership(_FORM4_DIRECTOR_ONLY)
    assert len(people) == 1 and people[0]["role_type"] == "director"
    assert people[0]["title"] == "Director"


def test_leadership_namespaced_schema():
    # Real ownership docs carry a default namespace — parsing must be ns-insensitive.
    xml = (
        '<ownershipDocument xmlns="http://www.sec.gov/edgar/ownership">'
        "<reportingOwner><reportingOwnerId>"
        "<rptOwnerName>Doe Jane</rptOwnerName></reportingOwnerId>"
        "<reportingOwnerRelationship><isOfficer>1</isOfficer>"
        "<officerTitle>President</officerTitle></reportingOwnerRelationship>"
        "</reportingOwner></ownershipDocument>"
    )
    people = edgar.extract_leadership(xml)
    assert people and people[0]["title"] == "President", people


def test_leadership_bad_xml_returns_empty():
    assert edgar.extract_leadership("<not-valid<<<") == []


# --- company_tickers.json + submissions JSON --------------------------------

_TICKERS_FIXTURE = {
    "0": {"cik_str": 320193, "ticker": "AAPL", "title": "Apple Inc."},
    "1": {"cik_str": 789019, "ticker": "MSFT", "title": "Microsoft Corp"},
}


def test_parse_company_tickers():
    rows = edgar.parse_company_tickers(_TICKERS_FIXTURE)
    assert len(rows) == 2
    assert rows[0] == {"cik": 320193, "ticker": "AAPL", "title": "Apple Inc."}


_SUBMISSION_FIXTURE = {
    "cik": 320193,
    "name": "Apple Inc.",
    "sic": "3571",
    "sicDescription": "Electronic Computers",
    "tickers": ["AAPL"],
    "exchanges": ["Nasdaq"],
    "formerNames": [{"name": "Apple Computer Inc"}],
    "addresses": {"business": {"stateOrCountry": "CA"}},
    "filings": {
        "recent": {
            "form": ["10-K", "4", "8-K", "4"],
            "accessionNumber": [
                "0000320193-24-000123",
                "0000320193-25-000010",
                "0000320193-24-000200",
                "0000320193-23-000050",
            ],
            "primaryDocument": ["aapl-10k.htm", "form4a.xml", "ex.htm", "form4b.xml"],
            "filingDate": ["2024-11-01", "2025-01-10", "2024-12-01", "2023-06-01"],
            "reportDate": ["2024-09-28", "2025-01-08", "2024-12-01", "2023-05-30"],
        }
    },
}


def test_parse_submission():
    s = edgar.parse_submission(_SUBMISSION_FIXTURE)
    assert s["cik"] == 320193
    assert s["name"] == "Apple Inc."
    assert s["sic"] == "3571"
    assert s["sic_description"] == "Electronic Computers"
    assert s["hq_state"] == "CA"
    assert s["former_names"] == ["Apple Computer Inc"]
    assert len(s["filings"]) == 4


def test_latest_filing_10k_and_ownership():
    s = edgar.parse_submission(_SUBMISSION_FIXTURE)

    tenk = edgar.latest_filing(s, edgar.FORMS_10K)
    assert tenk is not None
    assert tenk["accession"] == "0000320193-24-000123"
    assert tenk["report_date"] == "2024-09-28"
    assert tenk["url"] == (
        "https://www.sec.gov/Archives/edgar/data/320193/"
        "000032019324000123/aapl-10k.htm"
    )

    # Two Form 4s present — the 2025-01-10 one is the most recent by filing date.
    own = edgar.latest_filing(s, edgar.FORMS_OWNERSHIP)
    assert own is not None and own["accession"] == "0000320193-25-000010"
    assert own["primary_document"] == "form4a.xml"


def test_latest_filing_absent_returns_none():
    s = edgar.parse_submission(_SUBMISSION_FIXTURE)
    assert edgar.latest_filing(s, {"DEF 14A"}) is None


def test_ownership_xml_url_strips_xsl_render_prefix():
    # EDGAR lists the XSL-rendered HTML page as primaryDocument; we must fetch
    # the raw XML at the accession root instead.
    url = edgar.ownership_xml_url(320193, "0000320193-25-000010", "xslF345X05/wf-form4_1.xml")
    assert url == (
        "https://www.sec.gov/Archives/edgar/data/320193/"
        "000032019325000010/wf-form4_1.xml"
    )
    # Already-raw filenames pass through unchanged.
    assert edgar.ownership_xml_url(320193, "0000320193-25-000010", "form4a.xml") == (
        "https://www.sec.gov/Archives/edgar/data/320193/000032019325000010/form4a.xml"
    )
    assert edgar.ownership_xml_url(None, "x", "form4.xml") is None
    assert edgar.ownership_xml_url(1, "x", "") is None


# --- tier/domain wiring end-to-end on a fake record -------------------------

def test_tier_and_domain_wiring():
    # Simulate an enriched record built from the fixtures above.
    s = edgar.parse_submission(_SUBMISSION_FIXTURE)
    emp = edgar.extract_employees(
        _wrap("As of September 28, 2024, we had approximately 164,000 full-time employees.")
    )
    assert emp is not None
    record = {
        "id": "aapl",
        "sic": s["sic"],
        "sic_description": s["sic_description"],
        "employees": {"value": emp["value"], "tier": classify_tier(emp["value"])},
    }
    assert record["employees"]["tier"] == "100k-200k"

    domain = sic.domain_for(record["sic_description"], record["sic"])
    assert domain["label"] == "Electronic Computers"
    domains = sic.domains_from_records([record])
    assert domain["id"] in {d["id"] for d in domains}


def test_unknown_headcount_is_unknown_tier():
    assert classify_tier(None) == "unknown"


# --- logos (Wikidata P249 -> P154; pure) ------------------------------------

def test_build_logo_query_dedups_and_escapes():
    q = logos.build_logo_query(["AAPL", "AAPL", " MSFT ", ""])
    # Both distinct tickers appear once; blank dropped.
    assert '"AAPL"' in q and '"MSFT"' in q
    assert q.count('"AAPL"') == 1
    # Uses the correct properties and echoes the ticker back for keying.
    assert "wdt:P249" in q and "wdt:P154" in q
    assert "SELECT ?ticker ?logo" in q


def test_build_logo_query_matches_ticker_as_exchange_qualifier():
    # Most companies store the ticker as a pq:P249 qualifier on the p:P414
    # stock-exchange statement, not as a truthy wdt:P249 — the query must cover
    # both via UNION or it misses the large majority of filers.
    q = logos.build_logo_query(["AAPL"])
    assert "UNION" in q
    assert "p:P414" in q and "pq:P249" in q


def test_build_logo_query_escapes_quotes():
    q = logos.build_logo_query(['BRK"A'])
    assert '\\"' in q  # embedded quote escaped, not query-breaking


def test_commons_thumb_forces_https_and_width():
    src = "http://commons.wikimedia.org/wiki/Special:FilePath/Apple%20logo.svg"
    thumb = logos.commons_thumb(src, width=200)
    assert thumb.startswith("https://")
    assert thumb.endswith("?width=200")


def test_commons_thumb_leaves_non_filepath_urls_alone():
    src = "https://example.com/logo.png"
    assert logos.commons_thumb(src) == src


def test_parse_logo_results_keys_by_ticker_first_wins():
    data = {"results": {"bindings": [
        {"ticker": {"value": "AAPL"},
         "logo": {"value": "http://commons.wikimedia.org/wiki/Special:FilePath/A.svg"}},
        {"ticker": {"value": "AAPL"},
         "logo": {"value": "http://commons.wikimedia.org/wiki/Special:FilePath/B.svg"}},
        {"ticker": {"value": "MSFT"},
         "logo": {"value": "http://commons.wikimedia.org/wiki/Special:FilePath/M.svg"}},
    ]}}
    out = logos.parse_logo_results(data)
    assert set(out) == {"AAPL", "MSFT"}
    assert "Special:FilePath/A.svg" in out["AAPL"]  # first binding wins
    assert out["AAPL"].startswith("https://")


def test_parse_logo_results_skips_missing_logo():
    data = {"results": {"bindings": [
        {"ticker": {"value": "NOPE"}},  # no logo binding -> not fabricated
    ]}}
    assert logos.parse_logo_results(data) == {}


class _FakeLogoRepo:
    """In-memory stand-in for CompanyRepository's logo methods."""

    def __init__(self, tickers):
        self.pending = [{"id": t.lower(), "ticker": t} for t in tickers]
        self.checked = {}

    def missing_logo(self, limit):
        out = [c for c in self.pending if c["id"] not in self.checked]
        return out[:limit]

    def set_logo(self, cid, url, source, checked_at):
        self.checked[cid] = url


class _FakeWikidata:
    """Resolves every other ticker in a batch (deterministic, offline)."""

    def resolve_logos(self, tickers, **_):
        return {t: f"https://logo/{t}" for i, t in enumerate(tickers) if i % 2 == 0}


def _with_fake_wikidata(fn):
    orig = build_dataset.WikidataClient
    build_dataset.WikidataClient = lambda *a, **k: _FakeWikidata()
    try:
        return fn()
    finally:
        build_dataset.WikidataClient = orig


def test_logo_pass_drains_whole_backlog_within_budget():
    repo = _FakeLogoRepo([f"T{i}" for i in range(10)])
    counts = {"logos_found": 0, "logos_checked": 0}
    errors = []
    ticks = iter(range(100))  # advance 1 per clock() call; deadline far away
    _with_fake_wikidata(lambda: build_dataset._resolve_logos_pass(
        repo, "now", errors, counts, 3, deadline=50, clock=lambda: next(ticks)))
    assert counts["logos_checked"] == 10          # every company checked
    assert counts["logos_found"] == 7             # half of each page resolved
    assert errors == []


def test_logo_pass_stops_at_deadline():
    repo = _FakeLogoRepo([f"T{i}" for i in range(30)])
    counts = {"logos_found": 0, "logos_checked": 0}
    ticks = iter(range(100))
    _with_fake_wikidata(lambda: build_dataset._resolve_logos_pass(
        repo, "now", [], counts, 3, deadline=2, clock=lambda: next(ticks)))
    # Budget cuts it off well before the 30-company backlog is drained.
    assert 0 < counts["logos_checked"] < 30


# --- runner -----------------------------------------------------------------

def _run():
    tests = [v for k, v in sorted(globals().items()) if k.startswith("test_") and callable(v)]
    passed = 0
    for t in tests:
        t()
        print(f"  PASS {t.__name__}")
        passed += 1
    print(f"\n{passed}/{len(tests)} tests passed")


if __name__ == "__main__":
    _run()
