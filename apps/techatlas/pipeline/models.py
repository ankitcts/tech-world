"""MongoDB connection + repositories for TechAtlas.

Follows the data-management skill: connection comes ONLY from the environment
(`MONGODB_URI`, optional `MONGODB_DB`), nothing hardcoded, repository pattern,
and a hard failure if the connection is missing/unreachable — never a silent
fallback to embedded data.
"""

from __future__ import annotations

import os

DEFAULT_DB = "techatlas"


def get_database():
    """Return a live pymongo Database, pinging to prove connectivity."""
    from pymongo import MongoClient
    from pymongo.errors import PyMongoError

    uri = os.environ.get("MONGODB_URI")
    if not uri:
        raise RuntimeError(
            "MONGODB_URI is not set. Provide the MongoDB connection string via "
            "the environment (never hardcode it). Example:\n"
            "  export MONGODB_URI='mongodb+srv://<credentials>@host/?appName=...'"
        )
    db_name = os.environ.get("MONGODB_DB", DEFAULT_DB)
    client = MongoClient(uri, serverSelectionTimeoutMS=8000, appName="techatlas")
    try:
        client.admin.command("ping")
    except PyMongoError as exc:
        raise RuntimeError(
            f"Could not reach MongoDB: {exc}. Check the URI, network egress, and "
            "that this host/IP is allow-listed in Atlas."
        ) from exc
    return client[db_name]


class DomainRepository:
    collection_name = "domains"

    def __init__(self, db):
        self.col = db[self.collection_name]

    def ensure_indexes(self):
        self.col.create_index("id", unique=True)

    def upsert(self, domain: dict) -> None:
        self.col.update_one({"id": domain["id"]}, {"$set": domain}, upsert=True)

    def all(self) -> list[dict]:
        return list(self.col.find({}, {"_id": 0}))


class CompanyRepository:
    collection_name = "companies"

    def __init__(self, db):
        self.col = db[self.collection_name]

    def ensure_indexes(self):
        self.col.create_index("id", unique=True)
        self.col.create_index("domains")
        self.col.create_index([("name", "text"), ("blurb", "text")])

    def upsert(self, company: dict) -> None:
        self.col.update_one({"id": company["id"]}, {"$set": company}, upsert=True)

    def spine_upsert(self, identity: dict, scaffold: dict | None = None) -> bool:
        """Upsert only the identity fields, seeding empty enrichment fields once.

        The daily spine pass must never clobber values written by enrichment
        (``sic``, ``hq``, ``employees``, ``leadership``, ``enriched_at`` …), so
        those are set with ``$setOnInsert`` and left untouched on later runs.
        Returns ``True`` when a new company document was inserted.
        """
        update = {"$set": identity}
        if scaffold:
            update["$setOnInsert"] = scaffold
        res = self.col.update_one({"id": identity["id"]}, update, upsert=True)
        return res.upserted_id is not None

    def stalest_for_enrichment(self, limit: int) -> list[dict]:
        """Companies with the oldest/absent ``enriched_at`` (absent sorts first)."""
        return list(
            self.col.find({}, {"_id": 0})
            .sort("enriched_at", 1)
            .limit(max(0, int(limit)))
        )

    def count_unenriched(self) -> int:
        """How many companies have never been enriched (``enriched_at`` null/missing)."""
        return self.col.count_documents({"enriched_at": None})

    def missing_logo(self, limit: int) -> list[dict]:
        """Companies whose logo has never been resolved (``logo_checked_at`` absent).

        Returns just the identity fields the logo resolver needs (id, ticker),
        oldest/absent check first, so successive runs sweep the backlog.
        """
        cur = (
            self.col.find(
                {"logo_checked_at": None, "ticker": {"$nin": [None, ""]}},
                {"_id": 0, "id": 1, "ticker": 1},
            )
            .limit(max(0, int(limit)))
        )
        return list(cur)

    def count_missing_logo(self) -> int:
        """How many ticker-bearing companies still have no logo check recorded."""
        return self.col.count_documents(
            {"logo_checked_at": None, "ticker": {"$nin": [None, ""]}})

    def set_logo(self, company_id: str, logo_url, source: str, checked_at: str) -> None:
        """Record a logo-resolution result (``logo_url`` may be ``None`` = a miss).

        Always stamps ``logo_checked_at`` so a resolved *or* not-found company is
        not retried before every other company has had a first pass.
        """
        self.col.update_one(
            {"id": company_id},
            {"$set": {
                "logo_url": logo_url,
                "logo_source": source if logo_url else None,
                "logo_checked_at": checked_at,
            }},
        )

    def by_domain(self, domain_id: str) -> list[dict]:
        return list(self.col.find({"domains": domain_id}, {"_id": 0}))

    def all(self) -> list[dict]:
        return list(self.col.find({}, {"_id": 0}))


class AgentRunRepository:
    """Observability + batch cursor for the daily refresh (collection ``agent_runs``)."""

    collection_name = "agent_runs"
    CURSOR_ID = "cursor"

    def __init__(self, db):
        self.col = db[self.collection_name]

    def ensure_indexes(self):
        self.col.create_index("started_at")

    def record_run(self, summary: dict) -> None:
        self.col.insert_one({"kind": "run", **summary})

    def get_cursor(self) -> dict:
        doc = self.col.find_one({"_id": self.CURSOR_ID}, {"_id": 0})
        return doc or {}

    def save_cursor(self, cursor: dict) -> None:
        self.col.update_one(
            {"_id": self.CURSOR_ID}, {"$set": cursor}, upsert=True
        )


class RawFilingRepository:
    """Raw fetched SEC filings kept for later LLM/RAG use (collection ``raw_filings``).

    One document per filing (keyed by accession): the cleaned, LLM-ready ``text``
    plus the original bytes in ``raw`` when small enough, with provenance. This is
    the source corpus Stage 2 (embeddings/RAG) will chunk and index.
    """

    collection_name = "raw_filings"

    def __init__(self, db):
        self.col = db[self.collection_name]

    def ensure_indexes(self):
        self.col.create_index("id", unique=True)
        self.col.create_index("cik")
        self.col.create_index("company_id")
        self.col.create_index("form")

    def upsert(self, doc: dict) -> None:
        self.col.update_one({"id": doc["id"]}, {"$set": doc}, upsert=True)

    def all(self, projection: dict | None = None) -> list[dict]:
        return list(self.col.find({}, projection or {"_id": 0}))
