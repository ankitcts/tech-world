# Changelog

All notable changes to this project are documented here.

The format is based on [Keep a Changelog](https://keepachangelog.com/en/1.1.0/),
and this project adheres to [Semantic Versioning](https://semver.org/spec/v2.0.0.html).

## [Unreleased]

### Fixed
- Live-data UI regressions on the landing page: (1) brand **logos** now render
  for known companies regardless of source — the curated seed is merged with the
  live SEC data, so familiar companies keep their logo/blurb/domains and are
  *enriched* with live SEC employee tiers + leadership (matched by ticker), while
  the SEC long-tail is added on top; (2) the curated companies no longer
  "disappear" when live data loads; (3) the marquee rows **always scroll** now
  (each row is padded past ~1.6 viewports so the loop always has travel), and
  sparse SIC domains are hidden until they have ≥3 companies to avoid dozens of
  one-company rows during backfill.
- Vercel build failure ("No python entrypoint found"): moved the `scraper/`
  toolkit's dependency list from the repo-root `requirements.txt` to
  `scraper/requirements.txt`. A root `requirements.txt` made Vercel's newer
  builder treat the whole repo as a single Python app needing one entrypoint,
  instead of deploying `api/*.py` as independent serverless functions (whose
  deps come from `api/requirements.txt`). Updated the one doc reference.

### Added
- `/api/refresh` accepts the `CRON_SECRET` via a `?key=` query param (in addition
  to the `Authorization: Bearer` header the cron sends), so a run can be triggered
  manually from a browser.
- Landing page shows a **data-source badge** ("Live · MongoDB" vs "Sample data ·
  seed") derived from the `X-Data-Source` response header, so it's obvious whether
  the site is serving live pipeline data or the curated fallback.

### Changed
- TechAtlas landing page: added a **Rows ⇄ List view toggle** with a **live
  search** box (filters by name/ticker in both views). The list view is a
  simple, sortable, keyboard-accessible directory of every company; clicking a
  row opens the same deep-linked detail tab. Responsive down to mobile.
- TechAtlas seed data: expanded the curated dataset from 31 to **78 real,
  U.S.-headquartered public companies** (verified name, ticker, HQ, domain
  only — employee counts and leadership remain `unknown` until the SEC pipeline
  fills them authoritatively). Added 26 more brand logos via simple-icons;
  companies without an available mark render a clean monogram tile.
- TechAtlas web app: replaced the 3D WebGL constellation with a simple,
  fast landing page — **Netflix-style rows of company logos, one row per
  domain, auto-scrolling slowly** (pause on hover; static + swipeable under
  `prefers-reduced-motion`). Clicking a logo opens the company's detail in a
  **new tab** via a deep-linkable `?company=<id>` URL. The view is fully
  data-driven and reads `/api/companies` (live from MongoDB) with a fallback to
  the committed `companies.json`. Dropping Three.js cut the JS bundle from
  ~hundreds of KB to ~30 KB.

### Added
- TechAtlas daily company-data agent — **Stage 1 (fetch + segment + enrich)**:
  - `apps/techatlas/pipeline/edgar.py` — SEC EDGAR client with a required
    `SEC_USER_AGENT` (fair-access policy), ~8 req/s throttle and 429/503
    backoff, plus **pure, offline-testable parsers**: `company_tickers`,
    `submission`, `latest_filing`, a **conservative** 10-K `extract_employees`
    (returns `None` rather than guess when no number is explicitly labelled
    "employees"), and a Form 3/4/5 `extract_leadership` (officer/director
    records with titles, namespace-insensitive) — every value provenance-tagged.
  - `apps/techatlas/pipeline/build_dataset.py` — `run_refresh(db, batch_size,
    now_iso)` orchestration: cheap full **spine** upsert from
    `company_tickers.json` (never clobbers enriched fields) + **bounded
    incremental enrichment** of the stalest companies (10-K headcount → tier,
    Forms 3/4/5 → leadership), then recomputes the dynamic **domains**
    collection from the SIC data actually present. Env-driven
    (`TECHATLAS_BATCH_SIZE`, `TECHATLAS_SPINE_CAP`); per-run cap surfaced in the
    summary and `agent_runs`.
  - `api/refresh.py` — Vercel Cron serverless function (`/api/refresh`) that
    connects to MongoDB and runs the refresh; requires
    `Authorization: Bearer $CRON_SECRET` when that env var is set.
  - `apps/techatlas/pipeline/models.py` — added `AgentRunRepository`
    (`agent_runs` collection: run log + batch cursor) and `CompanyRepository`
    `spine_upsert`/`stalest_for_enrichment` helpers (identity vs. enrichment
    fields kept separate so the daily spine pass never overwrites verified data).
  - `vercel.json` — daily cron (`0 6 * * *`) on `/api/refresh` and a `functions`
    `includeFiles` glob so the cross-directory pipeline modules + seed are
    bundled with the Python API functions.
  - `api/requirements.txt` — `requests`, `beautifulsoup4`, `lxml`,
    `pymongo[srv]` (dnspython for `mongodb+srv://`).
  - `apps/techatlas/pipeline/test_edgar.py` — offline unit tests (no network)
    over inline 10-K/Form-4/submission fixtures: employee-regex incl.
    no-match→`None` and 1.6M-employee cases, officer/director XML parsing, and
    tier/domain wiring end-to-end.
- Company detail page **Leadership & board** section (CEO, CTO, other executive
  officers, directors) — rendered from provenance-backed records sourced from
  **SEC filings** (Forms 3/4/5 + DEF 14A), each entry linking to its source.
  When not yet ingested it shows an explicit "sourced from filings" state rather
  than any unverified names.
- TechAtlas daily company-data agent — foundations + deployment plan:
  - `apps/techatlas/pipeline/tiers.py` — employee-count "horizon" tiers
    (`< 100` … `300,000+` plus `unknown`), with `classify_tier()` that assigns a
    band only from a verified headcount and never guesses unverifiable values.
  - `apps/techatlas/pipeline/sic.py` — industry domains taken verbatim from
    SEC's own `sicDescription` on each real record (no hand-picked catalog); the
    domain set is exactly the industries present in the fetched data ("all
    available domains"), with deterministic per-domain colors.
  - `api/companies.py` — Vercel Python serverless read endpoint serving
    companies + domains live from MongoDB (CDN-cached), with a curated-seed
    fallback so the frontend never breaks.
  - `docs/deploy/daily-agent.md` — end-to-end deployment plan for running the
    agent daily on Vercel Cron: SEC EDGAR authoritative spine, 10-K-only
    employee counts with per-field provenance, dynamic SIC domains, a RAG
    enrichment stage over SEC filings (MongoDB Atlas Vector Search, cited
    answers), env-driven secrets, and incremental batching for scale.
  - Offline unit tests for the tier boundaries and SIC/domain mapping.
- MIT `LICENSE`.
- Global `web-scraper` subagent (`.claude/agents/web-scraper.md`) for scraping
  static HTML, JS-rendered pages, and JSON/XML APIs.
- Global `threed-frontend` subagent (`.claude/agents/threed-frontend.md`) for
  building interactive 3D web experiences (Three.js / React Three Fiber / WebGL).
- `scraper/` Python toolkit backing the web-scraper agent: env-driven fetchers
  (static/dynamic/api), CSS/table/link/JSON-path extraction, and JSON/CSV/text
  output, with a `python -m scraper` CLI.
- Global `data-management` skill (`.claude/skills/data-management/`) enforcing
  MongoDB-only, fully dynamic, no-hardcoded-data persistence, with env-based
  connection config and a hard "confirm connection or static-site before
  starting work" gate.
- Global `living-docs` skill (`.claude/skills/living-docs/`) that maintains this
  changelog and per-release documents, plus a `cut_release.py` helper and a
  `UserPromptSubmit` doc-reminder hook.
- Global `adsense-compliance` skill (`.claude/skills/adsense-compliance/`) with
  a heuristic `audit.py` scanner, a manual checklist, and a `PreToolUse`
  pre-push gate (`.claude/hooks/adsense-pre-push.sh`) that blocks `git push`
  when an AdSense-integrated project is missing a valid `ads.txt` or privacy
  policy, while leaving non-ad projects untouched.
- Global hook wiring (`~/.claude/settings.json`) registering the
  `UserPromptSubmit` doc reminder and the `PreToolUse` AdSense pre-push gate,
  documented for version control in `.claude/hooks/README.md`.
- Global `security-tester` subagent (`.claude/agents/security-tester.md`) for
  defensive, first-party website/app security testing (secrets, OWASP Top 10,
  dependencies, security headers, auth/session), backed by a `PreToolUse`
  pre-commit gate (`.claude/hooks/security-precommit.sh` + `.py`) that scans
  staged files and blocks `git commit` on CRITICAL findings (committed secrets
  or `.env` files) while reporting risky patterns without blocking.
- Global `architecture-diagrams` subagent (`.claude/agents/architecture-diagrams.md`)
  producing C4-model interactive diagrams + documents (Mermaid source of
  truth; Tier-1 self-contained HTML viewer, Tier-2 React Flow app; build-time
  ElevenLabs audio narration keyed by `ELEVENLABS_API_KEY`), with an
  architecture-first `UserPromptSubmit` gate (`.claude/hooks/arch-gate.sh`)
  requiring architecture docs before new projects start or when changing an
  existing project that lacks them.
- `docs/architecture/` for this repo (dogfooding): C4 context + container
  Mermaid diagrams, written architecture document, interactive viewer
  (verified: keyboard/a11y clean, no 320px overflow), narration transcripts,
  and an ElevenLabs generation script.
- Global `responsive-a11y` subagent (`.claude/agents/responsive-a11y.md`) for
  responsive layout and WCAG 2.1 AA accessibility compliance, with a
  dependency-free static checker (`.claude/hooks/responsive-a11y-check.py`)
  and a `PostToolUse` hook that runs it automatically on every change to a
  web source file in any project.

### Changed
- Architecture-first policy strengthened from a soft nudge to a hard gate:
  new `PreToolUse` hook `.claude/hooks/arch-precode.sh` blocks writing
  application source code when a project has no `docs/architecture/`, prompting
  the user (via the architecture-diagrams agent's AskUserQuestion flow) to
  create the architecture first or explicitly opt out. Exempts docs, `.claude`,
  tests, and non-source files.

### Deprecated
### Removed
### Fixed
- adsense-compliance auditor no longer reports "AdSense integrated"
  from documentation/markdown that merely mentions AdSense; integration is
  now detected only in real web code files, preventing false pre-push blocks
  on tooling/docs repos.

### Security
