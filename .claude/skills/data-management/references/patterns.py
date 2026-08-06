"""Copy-ready MongoDB data-management patterns (Python).

Everything here is env-driven and dynamic. There is not a single hardcoded
record, URI, or credential — that is the whole point of this skill.

Contents
--------
1. Connection layer      (db.py)           — sync (pymongo) and async (motor)
2. Repository base       + example repo
3. Indexes & validation  (defined in code, applied to the live DB)
4. Idempotent seeding    (a script, never inline app data)
5. Simple migrations
6. The "no connection" guard — ask, never auto-start

Install: pip install pymongo motor
"""

from __future__ import annotations

import os
from typing import Any, Iterable, Optional


# ---------------------------------------------------------------------------
# 1. Connection layer  (put this in db.py)
# ---------------------------------------------------------------------------
# The URI and DB name come ONLY from the environment. Missing config is a hard,
# loud failure — never a silent fallback to a hardcoded default.

def get_settings() -> tuple[str, str]:
    uri = os.environ.get("MONGODB_URI")
    db_name = os.environ.get("MONGODB_DB")
    if not uri:
        raise RuntimeError(
            "MONGODB_URI is not set. Provide a MongoDB connection string via "
            "the environment (e.g. an Atlas or self-hosted URI). Do NOT hardcode "
            "a connection, and do NOT start a cluster without asking the user."
        )
    if not db_name:
        raise RuntimeError("MONGODB_DB is not set. Provide the database name.")
    return uri, db_name


# --- Sync client (pymongo) -------------------------------------------------
def get_database():
    """Return a live pymongo Database, pinging to prove the connection works."""
    from pymongo import MongoClient
    from pymongo.errors import PyMongoError

    uri, db_name = get_settings()
    client = MongoClient(uri, serverSelectionTimeoutMS=5000, appname="app")
    try:
        client.admin.command("ping")
    except PyMongoError as exc:
        # Do NOT auto-start anything here. Surface the failure so the caller can
        # ask the user how to connect.
        raise RuntimeError(
            f"Could not reach MongoDB at the configured URI: {exc}. "
            "Ask the user for a reachable connection before proceeding."
        ) from exc
    return client[db_name]


# --- Async client (motor) --------------------------------------------------
def get_async_database():
    """Return a live motor AsyncIOMotorDatabase (ping in an async startup hook)."""
    from motor.motor_asyncio import AsyncIOMotorClient

    uri, db_name = get_settings()
    client = AsyncIOMotorClient(uri, serverSelectionTimeoutMS=5000, appname="app")
    return client[db_name]  # `await db.command("ping")` during app startup


# ---------------------------------------------------------------------------
# 2. Repository base + example repository
# ---------------------------------------------------------------------------
# Repositories are the ONLY place collections are touched. Application code
# calls these methods; it never reaches into a collection directly, and it
# never embeds record literals.

class Repository:
    """Minimal CRUD base. Subclass per collection/aggregate."""

    collection_name: str = ""

    def __init__(self, db=None):
        self.db = db or get_database()
        if not self.collection_name:
            raise ValueError("collection_name must be set on the subclass")
        self.col = self.db[self.collection_name]

    def create(self, doc: dict) -> str:
        return str(self.col.insert_one(doc).inserted_id)

    def get(self, query: dict) -> Optional[dict]:
        return self.col.find_one(query)

    def list(self, query: Optional[dict] = None, *,
             limit: int = 0, skip: int = 0, sort: Optional[list] = None
             ) -> list[dict]:
        cursor = self.col.find(query or {})
        if sort:
            cursor = cursor.sort(sort)
        if skip:
            cursor = cursor.skip(skip)
        if limit:
            cursor = cursor.limit(limit)
        return list(cursor)

    def update(self, query: dict, changes: dict) -> int:
        return self.col.update_many(query, {"$set": changes}).modified_count

    def delete(self, query: dict) -> int:
        return self.col.delete_many(query).deleted_count

    def ensure_indexes(self) -> None:
        """Override to declare indexes; called once at startup."""


class ItemRepository(Repository):
    collection_name = "items"

    def ensure_indexes(self) -> None:
        # Indexes are declared in code and applied to the live DB — the data
        # itself still lives only in MongoDB.
        self.col.create_index("sku", unique=True)
        self.col.create_index([("name", "text")])

    def find_by_sku(self, sku: str) -> Optional[dict]:
        return self.get({"sku": sku})


# ---------------------------------------------------------------------------
# 3. Schema validation applied to the live collection (not to code)
# ---------------------------------------------------------------------------

def apply_item_validation(db) -> None:
    """Attach a JSON-schema validator to the `items` collection."""
    schema = {
        "$jsonSchema": {
            "bsonType": "object",
            "required": ["sku", "name"],
            "properties": {
                "sku": {"bsonType": "string"},
                "name": {"bsonType": "string"},
                "price": {"bsonType": ["double", "int", "decimal"]},
            },
        }
    }
    existing = db.list_collection_names()
    if "items" in existing:
        db.command("collMod", "items", validator=schema)
    else:
        db.create_collection("items", validator=schema)


# ---------------------------------------------------------------------------
# 4. Idempotent seed script (run manually; app never reads baked-in data)
# ---------------------------------------------------------------------------
# Seed data is created by RUNNING this script against MongoDB. It is not what
# the application serves at runtime — the app always queries the DB. Seeding is
# safe to re-run (upsert by natural key).

def seed_items(db, records: Iterable[dict]) -> int:
    """Upsert seed records by `sku`. `records` comes from a data file/CLI arg,
    NOT from a literal embedded in application code."""
    col = db["items"]
    count = 0
    for rec in records:
        col.update_one({"sku": rec["sku"]}, {"$set": rec}, upsert=True)
        count += 1
    return count


# ---------------------------------------------------------------------------
# 5. Lightweight migrations (versioned, tracked in a collection)
# ---------------------------------------------------------------------------

def run_migrations(db, migrations: list[tuple[str, Any]]) -> None:
    """`migrations` is a list of (id, callable(db)). Applied once each; the
    applied set is tracked in a `_migrations` collection in Mongo."""
    applied = {d["_id"] for d in db["_migrations"].find({}, {"_id": 1})}
    for mig_id, fn in migrations:
        if mig_id in applied:
            continue
        fn(db)
        db["_migrations"].insert_one({"_id": mig_id})


# ---------------------------------------------------------------------------
# 6. The "no connection" guard
# ---------------------------------------------------------------------------
# Use this at the entry point. If it raises, the agent/app must ASK the user how
# to connect (existing URI, or explicit OK to start a local/dev instance) —
# never auto-provision.

def require_connection():
    try:
        return get_database()
    except RuntimeError as exc:
        raise SystemExit(
            f"\n[data-management] No usable MongoDB connection.\n  {exc}\n"
            "  → Ask the user: provide MONGODB_URI, or explicitly approve "
            "starting a local/dev instance. Do not start one automatically.\n"
        )


if __name__ == "__main__":
    # Example wiring — reads everything dynamically from the live DB.
    database = require_connection()
    apply_item_validation(database)
    repo = ItemRepository(database)
    repo.ensure_indexes()
    print(f"connected; items in DB: {len(repo.list())}")
