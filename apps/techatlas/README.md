# TechAtlas (first app)

An interactive 3D map of major U.S. technology companies, each linked to the
technology domains it builds in. Dogfoods the tech-world platform: the
`web-scraper`/`data-management`/`threed-frontend` tooling and the compliance
gates.

> **Brand name is a placeholder** ("TechAtlas") — rename anytime.

## Architecture (C4, summary)

```
[ Developer ] → runs pipeline → [ MongoDB ]  ──export──▶  companies.json
                                     ▲                          │
        scrape.py (scraper toolkit)  │                          ▼
   public sources ───────────────────┘                 [ Three.js web app ]
```

- **pipeline/** (Python) — source of truth is **MongoDB**, connection from
  `MONGODB_URI` only (data-management skill; nothing hardcoded).
  - `models.py` — env-driven connection + `DomainRepository` / `CompanyRepository`.
  - `scrape.py` — pulls company names via the repo `scraper` toolkit, merges
    curated domain classification, upserts into MongoDB.
  - `seed_data.json` — curated dataset (seed input / classification).
  - `export.py` — dumps Mongo → `web/public/companies.json` for the frontend.
- **web/** (Vite + Three.js) — reads `companies.json` (no hardcoded company
  data in the app) and renders the constellation in WebGL with orbit controls,
  hover/click details, search, and domain filters.

## Run

### 1. Populate the database (where egress + Atlas are reachable)
```bash
export MONGODB_URI='mongodb+srv://<credentials>@host/?appName=...'   # never commit this
export MONGODB_DB='techatlas'
pip install -r apps/techatlas/pipeline/requirements.txt
python -m apps.techatlas.pipeline.scrape          # scrape + upsert
python -m apps.techatlas.pipeline.export          # Mongo → companies.json
```
No connection yet? Build the frontend data from the curated seed:
```bash
python -m apps.techatlas.pipeline.export --from-seed
```

### 2. Run the web app
```bash
cd apps/techatlas/web
npm install
npm run dev        # http://localhost:5173
npm run build      # production build → dist/
```

## Notes
- **Secrets:** `MONGODB_URI` (and any keys) come only from the environment.
  The connection string is never stored in the repo.
- **Network:** the managed sandbox blocks general web + Atlas egress, so the
  scrape/DB steps run in an environment with open egress; the curated seed lets
  the frontend build anywhere.
- The committed `companies.json` was generated with `export --from-seed`.
