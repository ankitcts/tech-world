"""Stage 1 orchestration: fetch the SEC public-company universe, segment, enrich.

Pure of Vercel — :func:`run_refresh` takes an already-connected ``db`` and a
caller-supplied ``now_iso`` so it can be driven from the ``/api/refresh`` cron
function *and* from a script/test without importing the serverless runtime.

The daily job does two things:

1. **Spine refresh (cheap, full):** one bulk ``company_tickers.json`` fetch →
   upsert an identity record per filer. Never clobbers enrichment fields.
2. **Bounded enrichment (incremental):** take the ``batch_size`` companies with
   the stalest/absent ``enriched_at``; for each, pull its submission → latest
   10-K → conservative headcount, and latest Form 3/4/5 → officer/director
   records. Provenance-wrapped; unverifiable values stay explicitly empty.

Everything is env-driven (``TECHATLAS_BATCH_SIZE``, optional
``TECHATLAS_SPINE_CAP``); nothing about the dataset is hardcoded.
"""

from __future__ import annotations

import hashlib
import json
import os
import re

from apps.techatlas.pipeline import sic
from apps.techatlas.pipeline.edgar import (
    FORMS_10K,
    FORMS_OWNERSHIP,
    SecClient,
    extract_employees,
    extract_leadership,
    latest_filing,
    ownership_xml_url,
)
from apps.techatlas.pipeline.models import (
    AgentRunRepository,
    CompanyRepository,
    DomainRepository,
)
from apps.techatlas.pipeline.tiers import classify_tier

DEFAULT_BATCH_SIZE = 40


def _slug(text: str) -> str:
    s = re.sub(r"[^a-z0-9]+", "-", (text or "").strip().lower()).strip("-")
    return s


def _content_hash(*parts) -> str:
    payload = json.dumps(parts, sort_keys=True, default=str)
    return hashlib.sha1(payload.encode("utf-8")).hexdigest()


def _company_id(ticker: str, name: str) -> str:
    return _slug(ticker) or _slug(name) or _slug(f"cik-{name}")


def _batch_size() -> int:
    raw = os.environ.get("TECHATLAS_BATCH_SIZE")
    if raw and raw.strip().isdigit():
        return max(1, int(raw))
    return DEFAULT_BATCH_SIZE


def _spine_cap() -> int | None:
    raw = os.environ.get("TECHATLAS_SPINE_CAP")
    if raw and raw.strip().isdigit():
        return max(0, int(raw))
    return None


def _refresh_spine(client, companies_repo, now_iso, errors) -> tuple[int, bool]:
    """Upsert one identity record per SEC filer. Returns (upserts, capped)."""
    try:
        tickers = client.company_tickers()
    except Exception as exc:  # noqa: BLE001 - surfaced in the run summary
        errors.append(f"company_tickers: {exc}")
        return 0, False

    capped = False
    cap = _spine_cap()
    if cap is not None and len(tickers) > cap:
        print(f"[spine] capping {len(tickers)} filers to {cap} (TECHATLAS_SPINE_CAP)")
        tickers = tickers[:cap]
        capped = True

    inserts = 0
    for t in tickers:
        cid = _company_id(t.get("ticker", ""), t.get("title", ""))
        if not cid:
            continue
        identity = {
            "id": cid,
            "cik": f"{int(t['cik']):010d}",
            "name": t.get("title", ""),
            "ticker": t.get("ticker", ""),
            "updated_at": now_iso,
            "content_hash": _content_hash(cid, t.get("cik"), t.get("ticker"), t.get("title")),
        }
        # Enrichment-owned fields seeded empty on first insert, never overwritten here.
        scaffold = {
            "hq": None,
            "sic": None,
            "sic_description": None,
            "domains": [],
            "employees": {"value": None, "tier": "unknown", "source": None},
            "leadership": [],
            "enriched_at": None,
        }
        if companies_repo.spine_upsert(identity, scaffold):
            inserts += 1
    return inserts, capped


def _employees_field(company_record, submission, client, now_iso, errors):
    """Return (employees_dict, found_bool). Never fabricates a value."""
    empty = {"value": None, "tier": "unknown", "source": None}
    filing = latest_filing(submission, FORMS_10K)
    if not filing or not filing.get("url"):
        return empty, False
    try:
        html = client.get_text(filing["url"])
    except Exception as exc:  # noqa: BLE001
        errors.append(f"{company_record['id']} 10-K fetch: {exc}")
        return empty, False
    found = extract_employees(
        html,
        as_of=filing.get("report_date") or None,
        source_url=filing.get("url"),
        accession=filing.get("accession") or None,
    )
    if not found:
        return empty, False
    value = found["value"]
    return (
        {
            "value": value,
            "tier": classify_tier(value),
            "source": found["source"],
            "source_url": found["source_url"],
            "accession": found["accession"],
            "as_of": found["as_of"],
            "confidence": "high",
        },
        True,
    )


def _leadership_field(company_record, submission, client, errors):
    filing = latest_filing(submission, FORMS_OWNERSHIP)
    if not filing or not filing.get("primary_document"):
        return [], False
    # Parse the RAW ownership XML (not the XSL-rendered HTML page EDGAR lists as
    # primaryDocument), but cite the human-readable filing page.
    raw_url = ownership_xml_url(
        submission.get("cik"), filing.get("accession") or "", filing["primary_document"]
    )
    if not raw_url:
        return [], False
    try:
        xml = client.get_text(raw_url)
    except Exception as exc:  # noqa: BLE001
        errors.append(f"{company_record['id']} ownership fetch: {exc}")
        return [], False
    people = extract_leadership(
        xml,
        source_url=filing.get("url") or raw_url,
        accession=filing.get("accession") or None,
        as_of=filing.get("filing_date") or None,
    )
    return people, bool(people)


def _enrich_one(company_record, client, now_iso, errors, counts):
    cik = company_record.get("cik")
    if not cik:
        return
    submission = client.submission(int(cik))

    sic_desc = submission.get("sic_description")
    sic_code = submission.get("sic")
    domain = sic.domain_for(sic_desc, sic_code)

    employees, emp_found = _employees_field(company_record, submission, client, now_iso, errors)
    leadership, lead_found = _leadership_field(company_record, submission, client, errors)

    if emp_found:
        counts["employees_found"] += 1
    if employees["tier"] == "unknown":
        counts["unknown_tier"] += 1
    if lead_found:
        counts["leadership_found"] += 1

    enrichment = {
        "id": company_record["id"],
        "name": submission.get("name") or company_record.get("name"),
        "hq": submission.get("hq_state"),
        "sic": sic_code,
        "sic_description": sic_desc,
        "domains": [domain["id"]],
        "employees": employees,
        "leadership": leadership,
        "enriched_at": now_iso,
    }
    return enrichment


def run_refresh(db, *, batch_size: int | None = None, now_iso: str) -> dict:
    """Run one Stage-1 refresh against ``db``; return a summary dict."""
    if batch_size is None:
        batch_size = _batch_size()

    domains_repo = DomainRepository(db)
    companies_repo = CompanyRepository(db)
    runs_repo = AgentRunRepository(db)
    domains_repo.ensure_indexes()
    companies_repo.ensure_indexes()
    runs_repo.ensure_indexes()

    errors: list[str] = []
    counts = {"employees_found": 0, "leadership_found": 0, "unknown_tier": 0}

    client = SecClient()

    # 1. Spine (cheap, full).
    spine_upserts, capped = _refresh_spine(client, companies_repo, now_iso, errors)

    # 2. Bounded incremental enrichment.
    enriched = 0
    batch = companies_repo.stalest_for_enrichment(batch_size)
    for company_record in batch:
        try:
            enrichment = _enrich_one(company_record, client, now_iso, errors, counts)
            if enrichment:
                companies_repo.upsert(enrichment)
                enriched += 1
        except Exception as exc:  # noqa: BLE001 - one company must not fail the run
            errors.append(f"{company_record.get('id', '?')}: {exc}")

    # 3. Recompute the dynamic domains collection from what is actually present.
    all_records = companies_repo.all()
    for domain in sic.domains_from_records(all_records):
        domains_repo.upsert(domain)

    summary = {
        "spine_upserts": spine_upserts,
        "enriched": enriched,
        "employees_found": counts["employees_found"],
        "leadership_found": counts["leadership_found"],
        "unknown_tier": counts["unknown_tier"],
        "capped": capped,
        "batch_size": batch_size,
        "started_at": now_iso,
        "errors": errors,
    }
    runs_repo.record_run(summary)
    runs_repo.save_cursor({"last_run_at": now_iso, "last_enriched": enriched})
    return summary
