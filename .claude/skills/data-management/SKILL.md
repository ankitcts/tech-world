---
name: data-management
description: >-
  Use this skill for ANY data persistence, storage, or data-access work in an
  application: creating/reading/updating/deleting records, defining schemas or
  models, seeding or migrating data, config/settings storage, caching state,
  or wiring a database layer. Enforces a single rule set — ALL data is managed
  through MongoDB, nothing is hardcoded, everything is dynamic, and the
  connection is configured via environment variables. Trigger whenever the
  work involves persisting or retrieving application data, "store this",
  "save to DB", "database", "collection", "model", "repository/DAO", "seed",
  "migration", or when you are about to embed data directly in source code.
---

# Data Management (MongoDB-only, fully dynamic)

This skill defines how **all** data in the application is managed. It is not a
suggestion layer — it is the data policy. Apply it to every feature that reads
or writes application data.

## Non-negotiable rules

1. **MongoDB is the single source of truth.** Every piece of application data —
   records, config, feature flags, lookup tables, content, user state — lives
   in MongoDB. No other datastore is introduced without the user's explicit
   approval.
2. **Nothing is hardcoded.** No literal records, seed rows, config values,
   option lists, or "example data" embedded in source files. If the app needs
   data, it reads it from MongoDB at runtime. Constants that are *data* (not
   code) belong in a collection.
3. **Everything is dynamic.** UIs, APIs, and logic render/operate on whatever
   the database currently holds. Never ship a screen or endpoint whose content
   is fixed in the code. Empty state is handled by querying and getting zero
   documents — not by falling back to baked-in data.
4. **Connection comes from the environment.** The connection string is read
   from `MONGODB_URI` (and DB name from `MONGODB_DB`). Never hardcode a URI,
   host, password, or cluster name in source. Fail loudly if the env var is
   missing.
5. **Ask before starting a cluster.** If no working MongoDB connection is
   provided (env var unset / unreachable), **stop and ask the user** how they
   want to connect — an existing Atlas/self-hosted URI, or explicit permission
   to start a local/dev instance. Do **not** spin up a cluster, container, or
   local `mongod` on your own initiative.
6. **Do not start work until connection is confirmed — or it's a static site.**
   This is a hard gate. Do **not** begin any implementation, scaffolding, or
   data code until **either** (a) a working MongoDB connection has been provided
   and verified, **or** (b) the user has explicitly stated the project is a
   **static website** with no dynamic data. Until one of those two conditions is
   met, stop and ask; do not write model/repository/seed code, and do not stub
   data in the meantime.

## When you start any data task

0. **Gate first (Rule 6).** Before writing any code, confirm one of two things
   is true: a MongoDB connection is provided, **or** the user has said the
   project is a static website. If neither is true, stop here and ask — do not
   scaffold, stub, or "start with placeholders."
1. **Check for a connection.** Look for `MONGODB_URI` in the environment / a
   `.env` file. Confirm it is reachable with a quick `ping`.
2. **If there is no connection:** ask the user (do not guess, do not auto-start).
   Present the options from Rule 5 and wait for their choice. Only skip the DB
   entirely if the user confirms it is a **static website**.
3. **Model the data as collections**, not as code. Define the shape, indexes,
   and validation in MongoDB — see `references/patterns.py`.
4. **Access data only through a repository layer** (see below). No raw
   collection access scattered across the app; no inline literals.
5. **Seed via scripts, not source.** If initial data is needed, write an
   idempotent seed script that inserts into MongoDB and is safe to re-run — the
   application code still reads everything from the DB.

## Architecture: connection + repository pattern

Keep three layers, all driven by env config:

- **`db.py`** — one place that builds the client from `MONGODB_URI`, exposes the
  database handle, and pings on startup. No credentials in code.
- **Repositories** (one per collection/aggregate) — the *only* code that touches
  collections. CRUD + queries live here; the rest of the app calls repositories.
- **Config in the DB** — application settings/flags/lookups are documents, read
  at runtime, cached briefly if needed, never inlined.

Full, copy-ready Python patterns (pymongo sync + motor async, indexes,
validation, repository base class, idempotent seeding, migrations) are in
`references/patterns.py`. Read that file before writing data code.

## Anti-patterns to reject (and fix on sight)

- A list/dict of records defined in a `.py`/`.js`/`.json` file that the app
  serves as if it were live data → move it into MongoDB and read it back.
- `DEFAULT_ITEMS = [...]` / `SAMPLE_DATA = {...}` used as a fallback → delete the
  fallback; query the DB and handle the empty result.
- A hardcoded connection string, `localhost:27017` literal, or credentials in
  source → replace with `os.environ["MONGODB_URI"]`.
- Reading a config value from a constant or `settings.py` literal when it is
  operational *data* → store it as a config document.
- Auto-starting Docker/`mongod` because no DB was found → stop and ask first.

## Definition of done

- App runs with an **empty** database without crashing (dynamic empty states).
- Grepping the codebase for seed/sample/default data literals returns nothing.
- The only connection info is `MONGODB_URI` / `MONGODB_DB` from the environment.
- All reads/writes go through repositories; no stray collection access.
- Any initial data is produced by a re-runnable seed script, not source code.
