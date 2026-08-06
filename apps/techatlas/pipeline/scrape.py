"""Scrape U.S. big-tech company data and upsert it into MongoDB.

Uses the repo's `scraper` toolkit to pull a source table of the largest U.S.
technology companies, normalizes each row into a company record, classifies it
into technology domains, and writes the result to MongoDB via the repository
layer. Run where outbound egress is open (this managed sandbox blocks general
web + Atlas):

    export MONGODB_URI='...'            # never hardcode
    python -m apps.techatlas.pipeline.scrape --source wikipedia

Because live sources change and require per-site ToS review, this script is
conservative: it scrapes names/tickers, then enriches domain classification
from `seed_data.json` (curated) so the graph is always well-formed. Anything it
cannot classify is flagged for manual review rather than guessed.
"""

from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path

HERE = Path(__file__).resolve().parent
# Make the repo root importable so we can reuse the `scraper` package.
REPO_ROOT = HERE.parents[2]
sys.path.insert(0, str(REPO_ROOT))

WIKI_URL = ("https://en.wikipedia.org/wiki/"
            "List_of_largest_technology_companies_by_revenue")


def load_seed() -> dict:
    return json.loads((HERE / "seed_data.json").read_text(encoding="utf-8"))


def scrape_company_names(url: str) -> list[dict]:
    """Return [{name, ticker?}] scraped from the source's first data table."""
    from scraper.fetchers import fetch_static
    from scraper.extractors import extract_tables

    res = fetch_static(url)
    tables = extract_tables(res.content)
    rows: list[dict] = []
    for table in tables:
        for row in table:
            # Heuristic: a "Company"/"Name" column identifies the company.
            name = (row.get("Company") or row.get("Name")
                    or row.get("Company name") or "").strip()
            if name:
                rows.append({"name": name})
        if rows:
            break
    return rows


def merge_with_seed(scraped: list[dict], seed: dict) -> tuple[list[dict], list[str]]:
    """Attach curated domain/metadata to scraped names; collect unmatched."""
    by_name = {c["name"].lower(): c for c in seed["companies"]}
    merged, unmatched = [], []
    seen = set()
    for row in scraped:
        key = row["name"].lower()
        if key in by_name:
            merged.append(by_name[key])
            seen.add(key)
        else:
            unmatched.append(row["name"])
    # Always include curated companies even if the source omitted them.
    for c in seed["companies"]:
        if c["name"].lower() not in seen:
            merged.append(c)
    return merged, unmatched


def run(source_url: str, dry_run: bool) -> int:
    seed = load_seed()
    try:
        scraped = scrape_company_names(source_url)
        print(f"scraped {len(scraped)} candidate rows from source")
    except Exception as exc:  # noqa: BLE001 - network/egress errors expected in sandbox
        print(f"scrape failed ({exc}); falling back to curated seed only",
              file=sys.stderr)
        scraped = []

    companies, unmatched = merge_with_seed(scraped, seed)
    if unmatched:
        print(f"note: {len(unmatched)} scraped names not yet classified "
              f"(manual review): {', '.join(unmatched[:8])}"
              + (" …" if len(unmatched) > 8 else ""))

    if dry_run:
        print(f"[dry-run] would upsert {len(seed['domains'])} domains and "
              f"{len(companies)} companies")
        return 0

    from apps.techatlas.pipeline.models import (
        get_database, DomainRepository, CompanyRepository)
    db = get_database()
    domains = DomainRepository(db)
    companies_repo = CompanyRepository(db)
    domains.ensure_indexes()
    companies_repo.ensure_indexes()
    for d in seed["domains"]:
        domains.upsert(d)
    for c in companies:
        companies_repo.upsert(c)
    print(f"upserted {len(seed['domains'])} domains and {len(companies)} "
          f"companies into MongoDB")
    return 0


def main(argv=None) -> int:
    ap = argparse.ArgumentParser(description="Scrape company data into MongoDB")
    ap.add_argument("--source", default="wikipedia",
                    help="source key or a full URL (default: wikipedia)")
    ap.add_argument("--dry-run", action="store_true",
                    help="scrape/merge but do not touch MongoDB")
    args = ap.parse_args(argv)
    url = WIKI_URL if args.source == "wikipedia" else args.source
    return run(url, args.dry_run)


if __name__ == "__main__":
    sys.exit(main())
