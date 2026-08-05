# Daily Company-Data Agent — Deployment Plan

How the TechAtlas dataset is fetched, segmented, enriched, and served — and how
the whole thing runs **every day on Vercel** with **authentic, source-attributed
data and no fabricated values**.

> **Non-negotiable rule (drives every choice below):** we only present a value we
> can attribute to an authoritative source. Anything we cannot verify is stored
> as `unknown` and shown as unknown — never guessed.

---

## 1. What the agent does (three stages)

```
                 ┌─────────────────────────── Vercel Cron (daily) ───────────────────────────┐
                 │                                                                            │
   SEC EDGAR ───▶│  Stage 1  FETCH + SEGMENT        Stage 2  RAG INGEST      Stage 3  SERVE   │
 (official       │  identity, ticker, HQ, SIC   →   filing text → chunk  →   /api/companies   │
  filings)       │  employees from 10-K only        embed → Atlas Vector    /api/stats        │
                 │  → employee tier + domain        Search (+ citations)    /api/ask (RAG)     │
                 │            │                             │                      ▲            │
                 │            └────────────▶  MongoDB  ◀────┘──────────────────────┘           │
                 └────────────────────────────────────────────────────────────────────────────┘
```

- **Stage 1 — Fetch + segment.** Pull the authoritative company spine from
  **SEC EDGAR**, classify each company into an **industry domain** (from its
  official SIC code) and an **employee tier** (from its latest 10-K), and upsert
  into MongoDB. Every field carries provenance.
- **Stage 2 — RAG ingest.** For companies new or changed since the last run,
  pull authentic **SEC filing text**, chunk it, embed it, and store the vectors
  in **MongoDB Atlas Vector Search** — same database, no new infrastructure —
  each chunk tagged with its filing URL + accession so answers are citable.
- **Stage 3 — Serve.** The Three.js app and any analysis reads live from Mongo
  via `/api/companies`; `/api/stats` gives tier/domain aggregates; `/api/ask`
  answers natural-language questions **grounded only in retrieved filings, with
  citations**, and says "unknown" when the filings don't support an answer.

---

## 2. Data sources & why (authenticity first)

| Field | Source | Authority | Notes |
|---|---|---|---|
| Company identity, CIK, ticker, former names | SEC EDGAR `company_tickers.json` + `submissions/CIK*.json` | **Authoritative** (regulatory) | The dataset spine. |
| HQ state, exchange | SEC EDGAR submissions | **Authoritative** | Structured fields. |
| Industry / **domain** | SEC **`sicDescription`** verbatim (see `pipeline/sic.py`) | **Authoritative** (from the source) | No hand-picked catalog — domains *are* the industries present in the real data → "all available domains". |
| **Employee count** → tier | SEC **10-K** human-capital disclosure only | **Authoritative** | Parsed conservatively; unverifiable → `unknown` tier. |
| **Leadership & board** (CEO, CTO, officers, directors) | SEC **Forms 3/4/5** (structured officer/director records + titles) + **DEF 14A** proxy (full board/committees/bios) | **Authoritative** | Names/titles only where a filing attributes them; each entry carries `source_url` + `as_of`. Never invented. |
| Company narrative (for RAG) | SEC 10-K business / risk / human-capital sections + DEF 14A | **Authoritative** | Stored verbatim + citation; never paraphrased into "facts". |

**Why not Wikidata / scraped tables for headcount?** They have the field but are
crowdsourced/estimated — presenting them as fact is exactly the "wrong
information" risk we reject. SEC filings are the authoritative record; private
companies with no disclosure obligation are legitimately `unknown`.

---

## 3. Employee tiers ("horizons")

Defined once in `pipeline/tiers.py` (lower-inclusive / upper-exclusive):

`< 100` · `100–1,000` · `1,000–10,000` · `10,000–50,000` · `50,000–100,000` ·
`100,000–200,000` · `200,000–300,000` · `300,000+` · **`unknown`**

`classify_tier(None)` and any unverifiable input → `unknown`. Counts are only
ever assigned to a band from a verified 10-K value.

---

## 4. Data model (MongoDB)

**`companies`** — one doc per company (upserted by `cik`):

```jsonc
{
  "id": "aapl", "cik": "0000320193", "name": "Apple Inc.", "ticker": "AAPL",
  "hq_state": "CA",
  "domains": ["sic-36"],                     // dynamic, from SIC major group
  "sic": "3571", "sic_description": "Electronic Computers",
  "employees": {                              // provenance-wrapped field
    "value": 164000, "tier": "100k-200k",
    "source": "sec-10k",
    "source_url": "https://www.sec.gov/Archives/edgar/data/320193/....htm",
    "accession": "0000320193-24-000123", "as_of": "2024-09-28",
    "confidence": "high"
  },
  "updated_at": "2026-08-05T06:00:00Z",
  "content_hash": "…"                         // drives incremental RAG ingest
}
```

If headcount is not verifiable: `employees.value = null`, `tier = "unknown"`,
`source = null` — the field is present but explicitly empty.

**`leadership`** — array of provenance-wrapped people, populated from filings:

```jsonc
"leadership": [
  { "name": "…", "title": "Chief Executive Officer", "role_type": "officer",
    "source_url": "https://www.sec.gov/Archives/edgar/data/320193/….htm",
    "accession": "…", "as_of": "2025-01-10" },
  { "name": "…", "title": "Director", "role_type": "director", "source_url": "…", "as_of": "…" }
]
```

`role_type` ∈ `officer` | `director`. Structured officer/director records come
from Forms 3/4/5; fuller board/committee/bio detail comes from the DEF 14A proxy
via the RAG stage. Absent → the detail page shows a "sourced from filings, not
yet ingested" state — never placeholder names.

**`domains`** — dynamic domain list (id, label, color) derived from the SIC
groups actually present. **`filings`** — RAG chunks: `{ cik, accession, url,
section, chunk_index, text, embedding[], as_of }` with an Atlas Vector Search
index on `embedding`. **`agent_runs`** — one doc per cron run (counts, errors,
batch cursor) for observability.

---

## 5. RAG pipeline (Stage 2 + `/api/ask`)

- **Ingest** (`rag/ingest.py`): pull 10-K sections for changed companies → chunk
  (~800 tokens, overlap) → embed via a **pluggable provider** (env-selected;
  nothing hardcoded) → upsert into `filings` with citation metadata. Bounded to
  a batch per run so it fits serverless limits and SEC rate limits; a cursor in
  `agent_runs` advances across days until the corpus is covered, then just keeps
  it fresh.
- **Query** (`rag/query.py`, `/api/ask`): embed the question → Atlas Vector
  Search top-k → answer **only** from retrieved chunks, **with citations**. If
  retrieval is empty/weak → respond "not supported by available filings"
  (no hallucination). This is what makes RAG safe under the no-wrong-info rule.
- **Why Atlas Vector Search:** the vectors live in the same MongoDB — no extra
  vector DB to provision, secure, or pay for.

---

## 6. Deploying on Vercel (runs every day)

**a. Cron.** `vercel.json` registers a daily job hitting the agent endpoint:

```jsonc
{ "crons": [ { "path": "/api/refresh", "schedule": "0 6 * * *" } ] }   // 06:00 UTC daily
```

Vercel invokes cron endpoints with `Authorization: Bearer $CRON_SECRET`; the
function rejects anything else, so the agent can't be triggered by the public.

**b. Serverless functions** (`/api`, Python): `refresh` (Stage 1 + a bounded
Stage 2 batch), `companies`, `stats`, `ask`. Cross-directory pipeline modules
are bundled via `functions[].includeFiles`; deps in `api/requirements.txt`
(`requests`, `beautifulsoup4`, `lxml`, `pymongo[srv]`, embedding client).

**c. Environment variables** (Project → Settings → Environment Variables — never
committed):

| Var | Purpose |
|---|---|
| `MONGODB_URI` | Atlas connection string (SRV). |
| `MONGODB_DB` | Database name (default `techatlas`). |
| `CRON_SECRET` | Shared secret Vercel sends on cron calls. |
| `SEC_USER_AGENT` | Descriptive UA `name email` — **required** by SEC fair-access policy. |
| `EMBEDDING_PROVIDER` + provider key | RAG embeddings (e.g. `OPENAI_API_KEY`). |

**d. Atlas network access.** Allow Vercel egress (Atlas allowlist `0.0.0.0/0`
with SCRAM auth, or Vercel static IPs on paid plans). Create the Vector Search
index on `filings.embedding`.

**e. Scale within limits (this is the crux for "all companies").** ~10k+ filers
can't be fetched-and-parsed in one invocation:
- Stage 1 spine refresh is one bulk file → cheap, runs fully each day.
- Employee-10-K parsing and RAG ingest are **incremental & bounded** — each run
  processes the N companies with the stalest `updated_at`/`content_hash`,
  advancing a cursor in `agent_runs`. Coverage builds over the first days, then
  the daily job only touches what changed. Respects SEC's ~10 req/s limit and
  the function's max duration. **Any per-run cap is logged in `agent_runs`** so
  truncation is visible, never silent.

---

## 7. Verification (before trusting a run)

- `pipeline/tiers.py` + `pipeline/sic.py` have offline unit tests (boundaries,
  no-guess, deterministic domains) — run in CI, no network needed.
- Stage 1: assert every `employees.value` has a non-null `source_url` + `as_of`,
  or else `tier == "unknown"`. Fail the run if a number lacks provenance.
- `/api/ask`: every answer must carry ≥1 citation resolving to a real filing
  URL; unsupported questions must return the "unknown" response.
- `agent_runs` records counts + errors per stage for daily review.

> **Sandbox note:** this managed dev environment blocks outbound egress (SEC +
> Atlas unreachable), so Stages 1–2 are validated by unit tests + dry-run here
> and exercised for real in the Vercel runtime, which has open egress.

---

## 8. Rollout order

1. **Foundations (done):** `tiers.py`, `sic.py` + unit tests.
2. **Stage 1:** EDGAR client, 10-K employee extraction w/ provenance, upsert.
3. **Serve:** `/api/companies` (live), `/api/stats`; frontend reads the API.
4. **Cron:** wire `vercel.json` + env; confirm daily green run in `agent_runs`.
5. **Stage 2 RAG:** ingest + Atlas Vector index + `/api/ask` with citations.
6. **Harden:** provenance assertions in CI, per-run caps surfaced, alerting.
