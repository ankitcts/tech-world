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
import time

from apps.techatlas.pipeline import edgar, sic
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
    RawFilingRepository,
)
from apps.techatlas.pipeline.tiers import classify_tier

DEFAULT_BATCH_SIZE = 40
DEFAULT_TIME_BUDGET_S = 45       # per-invocation enrichment budget (serverless-safe)
RAW_MAX_BYTES = 6_000_000        # keep original bytes only under this size
TEXT_MAX_BYTES = 8_000_000       # cap cleaned text (flagged when truncated)


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


def _store_full_raw() -> bool:
    """Whether to persist full filing text/bytes (heavy) vs. a URL reference.

    Defaults to False so the DB stays small (free-tier friendly). The filing URL
    is permanent, so the RAG stage can re-fetch on demand. Set
    ``TECHATLAS_STORE_FULL_RAW=1`` only when the cluster has room.
    """
    return os.environ.get("TECHATLAS_STORE_FULL_RAW", "").strip().lower() in (
        "1", "true", "yes", "on")


def _store_raw(refs_repo, company_record, cik, filing, content, content_type,
               now_iso, counts, store_full):
    """Persist a filing **reference** (URL + metadata) for later LLM/RAG re-fetch.

    Full cleaned ``text`` + original ``raw`` bytes are stored only when
    ``store_full`` is set — otherwise we keep just enough to re-fetch from SEC on
    demand, so the DB stays tiny. Never fabricates.
    """
    if refs_repo is None:
        return
    accession = filing.get("accession") or ""
    if not accession:
        return
    doc = {
        "id": accession,
        "company_id": company_record["id"],
        "cik": f"{int(cik):010d}" if cik else None,
        "ticker": company_record.get("ticker"),
        "form": filing.get("form"),
        "accession": accession,
        "url": filing.get("url"),
        "as_of": filing.get("report_date") or filing.get("filing_date") or None,
        "content_type": content_type,
        "byte_size": len(content) if content else 0,
        "has_text": False,
        "fetched_at": now_iso,
    }
    if store_full and content:
        text = edgar.visible_text(content) if content_type == "html" else content
        text_truncated = len(text) > TEXT_MAX_BYTES
        if text_truncated:
            text = text[:TEXT_MAX_BYTES]
        doc["text"] = text
        doc["text_truncated"] = text_truncated
        doc["raw"] = content if len(content) <= RAW_MAX_BYTES else None
        doc["raw_stored"] = doc["raw"] is not None
        doc["has_text"] = True
    refs_repo.upsert(doc)
    counts["filings_stored"] = counts.get("filings_stored", 0) + 1


def _enrich_one(company_record, client, raw_repo, now_iso, errors, counts, store_full):
    """Enrich one company from its SEC filings; persist the raw docs fetched."""
    cik = company_record.get("cik")
    if not cik:
        return None
    submission = client.submission(int(cik))
    sic_desc = submission.get("sic_description")
    sic_code = submission.get("sic")
    domain = sic.domain_for(sic_desc, sic_code)

    # --- employees from the latest 10-K (raw stored; value never guessed) ---
    employees = {"value": None, "tier": "unknown", "source": None}
    tenk = latest_filing(submission, FORMS_10K)
    if tenk and tenk.get("url"):
        try:
            html = client.get_text(tenk["url"])
        except Exception as exc:  # noqa: BLE001
            errors.append(f"{company_record['id']} 10-K fetch: {exc}")
            html = None
        if html:
            _store_raw(raw_repo, company_record, cik, tenk, html, "html", now_iso, counts, store_full)
            found = extract_employees(
                html, as_of=tenk.get("report_date") or None,
                source_url=tenk.get("url"), accession=tenk.get("accession") or None,
            )
            if found:
                employees = {
                    "value": found["value"], "tier": classify_tier(found["value"]),
                    "source": found["source"], "source_url": found["source_url"],
                    "accession": found["accession"], "as_of": found["as_of"],
                    "confidence": "high",
                }
                counts["employees_found"] += 1
    if employees["tier"] == "unknown":
        counts["unknown_tier"] += 1

    # --- leadership from the latest Form 3/4/5 raw XML (cite the readable page) ---
    leadership = []
    own = latest_filing(submission, FORMS_OWNERSHIP)
    if own and own.get("primary_document"):
        raw_url = ownership_xml_url(
            submission.get("cik"), own.get("accession") or "", own["primary_document"])
        if raw_url:
            try:
                xml = client.get_text(raw_url)
            except Exception as exc:  # noqa: BLE001
                errors.append(f"{company_record['id']} ownership fetch: {exc}")
                xml = None
            if xml:
                _store_raw(raw_repo, company_record, cik,
                           {**own, "url": own.get("url") or raw_url}, xml, "xml", now_iso, counts, store_full)
                leadership = extract_leadership(
                    xml, source_url=own.get("url") or raw_url,
                    accession=own.get("accession") or None, as_of=own.get("filing_date") or None)
                if leadership:
                    counts["leadership_found"] += 1

    return {
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


def _time_budget_s() -> float:
    raw = os.environ.get("TECHATLAS_TIME_BUDGET_S")
    try:
        return max(5.0, float(raw)) if raw else float(DEFAULT_TIME_BUDGET_S)
    except (TypeError, ValueError):
        return float(DEFAULT_TIME_BUDGET_S)


def run_refresh(db, *, batch_size: int | None = None, now_iso: str,
                time_budget_s: float | None = None, clock=time.monotonic) -> dict:
    """Run one Stage-1 refresh against ``db``; return a summary dict.

    Enrichment is **time-budgeted**: it keeps pulling the stalest batch and
    processing new companies until the per-invocation budget is spent or the
    backlog is drained. Each enriched company's ``enriched_at`` is bumped, so
    successive batches advance oldest→newest without repeating within a run.
    ``clock`` is injectable so tests can drive the loop deterministically.
    """
    if batch_size is None:
        batch_size = _batch_size()
    if time_budget_s is None:
        time_budget_s = _time_budget_s()

    domains_repo = DomainRepository(db)
    companies_repo = CompanyRepository(db)
    runs_repo = AgentRunRepository(db)
    raw_repo = RawFilingRepository(db)
    for repo in (domains_repo, companies_repo, runs_repo, raw_repo):
        repo.ensure_indexes()

    errors: list[str] = []
    counts = {"employees_found": 0, "leadership_found": 0, "unknown_tier": 0, "filings_stored": 0}
    store_full = _store_full_raw()
    client = SecClient()

    # 1. Spine (cheap, full).
    spine_upserts, capped = _refresh_spine(client, companies_repo, now_iso, errors)

    # 2. Time-budgeted incremental enrichment (drains the backlog per invocation).
    deadline = clock() + time_budget_s
    enriched = 0
    seen: set = set()
    while clock() < deadline:
        batch = companies_repo.stalest_for_enrichment(batch_size)
        fresh = [c for c in batch if c.get("id") not in seen]
        if not fresh:
            break  # wrapped around — nothing left to advance this run
        for company_record in fresh:
            if clock() >= deadline:
                break
            seen.add(company_record.get("id"))
            try:
                enrichment = _enrich_one(company_record, client, raw_repo, now_iso, errors, counts, store_full)
                if enrichment:
                    companies_repo.upsert(enrichment)
                    enriched += 1
            except Exception as exc:  # noqa: BLE001 - one company must not fail the run
                errors.append(f"{company_record.get('id', '?')}: {exc}")

    # 3. Recompute the dynamic domains collection from what is actually present.
    all_records = companies_repo.all()
    for domain in sic.domains_from_records(all_records):
        domains_repo.upsert(domain)

    unenriched_remaining = companies_repo.count_unenriched()
    summary = {
        "spine_upserts": spine_upserts,
        "enriched": enriched,
        "employees_found": counts["employees_found"],
        "leadership_found": counts["leadership_found"],
        "unknown_tier": counts["unknown_tier"],
        "filings_stored": counts["filings_stored"],
        "store_full_raw": store_full,
        "unenriched_remaining": unenriched_remaining,
        "capped": capped,
        "batch_size": batch_size,
        "started_at": now_iso,
        "errors": errors,
    }
    runs_repo.record_run(summary)
    runs_repo.save_cursor({
        "last_run_at": now_iso, "last_enriched": enriched,
        "unenriched_remaining": unenriched_remaining,
    })
    return summary
