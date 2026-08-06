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
