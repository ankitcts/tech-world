# Project Plan

Two linked initiatives, planned as a Jira-ready backlog. Epics and stories map
1:1 to Jira issues (Epic → Story), with acceptance criteria, estimates (story
points, Fibonacci), priority (P1 highest), and labels. Once the Jira connector
is available, these become Jira issues directly.

- **Initiative A — Platform:** harden and release the `tech-world` global Claude
  tooling suite (agents, skills, enforcement hooks) as a reusable platform.
- **Initiative B — First app (proposed):** a data-driven content site that
  dogfoods the platform end to end. **Scope is a proposal — confirm/adjust.**

Status legend: ☐ todo · ◐ in progress · ☑ done.

---

## Initiative A — tech-world Platform

Goal: go from "works in this session" to a versioned, installable, CI-enforced
platform anyone can adopt in one step.

### EPIC A1 — Packaging & global install
*One-command install of agents/skills/hooks; no manual copying.*

| Story | Acceptance criteria | Pts | Pri |
|-------|--------------------|-----|-----|
| A1-1 Installer script (`install.sh`) | Copies agents, skills, hooks to `~/.claude/`; merges hook settings without clobbering existing `settings.json`; idempotent; `--uninstall` supported | 5 | P1 |
| A1-2 Settings merge safety | Existing user hooks preserved; re-run does not duplicate entries; JSON validated after write | 3 | P1 |
| A1-3 Version pinning | Installed components record a version; `--version` prints it; mismatch warns | 2 | P2 |
| A1-4 Cross-platform check | Works on macOS/Linux bash; documents Windows/WSL notes | 2 | P3 |

### EPIC A2 — CI/CD server-side enforcement
*Mirror the local gates as CI so they enforce on every PR, not just locally.*

| Story | Acceptance criteria | Pts | Pri |
|-------|--------------------|-----|-----|
| A2-1 GitHub Action: security scan | Runs `security-precommit.py` on the diff; fails on CRITICAL | 3 | P1 |
| A2-2 GitHub Action: a11y/responsive | Runs `responsive-a11y-check.py` on changed web files; reports errors | 3 | P2 |
| A2-3 GitHub Action: AdSense audit | Runs `audit.py --gate` for ad-integrated projects | 2 | P2 |
| A2-4 Lint & syntax | `python -m py_compile` + shellcheck on all scripts | 2 | P2 |
| A2-5 Branch protection docs | Document required checks + default-branch setup | 1 | P3 |

### EPIC A3 — Tests & reliability
*Unit tests so the scanners/scripts don't regress.*

| Story | Acceptance criteria | Pts | Pri |
|-------|--------------------|-----|-----|
| A3-1 Scraper tests | Fetchers (mocked HTTP), extractors, output serializers covered | 5 | P1 |
| A3-2 Scanner tests | security/a11y/adsense checkers: fixture-based true/false positive tests | 5 | P1 |
| A3-3 cut_release test | Golden-file test of changelog move + release doc generation | 3 | P2 |
| A3-4 Hook smoke tests | Each hook: block/allow/silent cases asserted | 3 | P2 |

### EPIC A4 — Docs & onboarding
| Story | Acceptance criteria | Pts | Pri |
|-------|--------------------|-----|-----|
| A4-1 Top-level README | What each agent/skill/hook does + quickstart | 3 | P1 |
| A4-2 Per-tool usage docs | Invocation examples for every agent/skill | 3 | P2 |
| A4-3 Contribution guide | How to add a new agent/skill/hook safely | 2 | P3 |

### EPIC A5 — Release management
| Story | Acceptance criteria | Pts | Pri |
|-------|--------------------|-----|-----|
| A5-1 Cut v1.0.0 | `cut_release.py 1.0.0`; release doc filled; tag pushed | 2 | P1 |
| A5-2 Merge PR #1 to main | Set `main` default; merge platform baseline | 1 | P1 |

---

## Initiative B — First App (proposed: data-driven content site)

Goal: a real product that exercises every platform tool. Proposed concept: a
**responsive, accessible, MongoDB-backed content site** whose data is collected
by the scraper, with a 3D landing experience and AdSense monetization —
architecture-first, security-gated, fully dynamic (no hardcoded data).

> **Confirm the concept** before B-stories are estimated for real; scope below is
> the working assumption.

### EPIC B1 — Architecture & foundations *(blocks all other B epics)*
| Story | Acceptance criteria | Pts | Pri |
|-------|--------------------|-----|-----|
| B1-1 Architecture docs (C4) | `docs/architecture/` context+container+key flows via architecture-diagrams agent; interactive viewer | 5 | P1 |
| B1-2 Repo scaffold | App skeleton, env config (`MONGODB_URI`), no hardcoded data; passes arch-precode gate | 3 | P1 |
| B1-3 MongoDB schema & repos | Collections, indexes, validation, repository layer (data-management skill) | 5 | P1 |
| B1-4 CI wired | Initiative-A actions enabled on the app repo | 2 | P2 |

### EPIC B2 — Data ingestion
| Story | Acceptance criteria | Pts | Pri |
|-------|--------------------|-----|-----|
| B2-1 Source selection & robots/ToS review | Legal-to-scrape sources documented | 2 | P1 |
| B2-2 Scraper pipelines | `scraper` jobs (static/dynamic/api) → normalized records | 5 | P1 |
| B2-3 Ingestion → MongoDB | Idempotent upsert into collections; scheduling | 5 | P1 |
| B2-4 Data quality checks | Dedupe, validation, freshness metrics | 3 | P2 |

### EPIC B3 — Backend API
| Story | Acceptance criteria | Pts | Pri |
|-------|--------------------|-----|-----|
| B3-1 API endpoints | List/detail/search over dynamic data; pagination | 5 | P1 |
| B3-2 Caching & performance | Response caching; query indexes verified | 3 | P2 |
| B3-3 Error handling & logging | No stack-trace leaks; structured logs | 2 | P2 |

### EPIC B4 — Frontend (responsive + WCAG AA)
| Story | Acceptance criteria | Pts | Pri |
|-------|--------------------|-----|-----|
| B4-1 Layout & navigation | Responsive shell; passes responsive-a11y checker at 320–1440px | 5 | P1 |
| B4-2 Content list/detail views | Dynamic rendering from API; empty states | 5 | P1 |
| B4-3 Accessibility pass | WCAG 2.1 AA verified (keyboard, contrast, labels, landmarks) | 3 | P1 |
| B4-4 Required pages | Privacy Policy, About, Contact (AdSense prerequisite) | 2 | P1 |

### EPIC B5 — 3D landing experience
| Story | Acceptance criteria | Pts | Pri |
|-------|--------------------|-----|-----|
| B5-1 3D hero (threed-frontend) | React Three Fiber scene; reduced-motion fallback; 60fps budget | 5 | P2 |
| B5-2 Perf & fallback | Non-WebGL fallback; DPR cap; asset compression | 3 | P2 |

### EPIC B6 — Monetization & compliance
| Story | Acceptance criteria | Pts | Pri |
|-------|--------------------|-----|-----|
| B6-1 AdSense integration | Ad units on content pages only; `adsbygoogle` tag | 3 | P2 |
| B6-2 ads.txt + privacy + consent | `ads.txt`, privacy policy, CMP/Consent Mode; `audit.py --gate` passes | 3 | P1 |
| B6-3 Content quality review | Original, substantial content; no thin/placeholder pages | 3 | P1 |

### EPIC B7 — Security hardening
| Story | Acceptance criteria | Pts | Pri |
|-------|--------------------|-----|-----|
| B7-1 Security review (security-tester) | OWASP Top 10 pass; no secrets; headers set | 5 | P1 |
| B7-2 Dependency audit | `pip-audit`/`npm audit` clean or triaged | 2 | P2 |
| B7-3 Auth/session (if applicable) | Hashing, session flags, access control | 3 | P2 |

### EPIC B8 — Launch & observability
| Story | Acceptance criteria | Pts | Pri |
|-------|--------------------|-----|-----|
| B8-1 Deployment | Hosting + env secrets; HTTPS; sitemap/robots | 3 | P1 |
| B8-2 Analytics & monitoring | Traffic + error monitoring; Core Web Vitals | 2 | P2 |
| B8-3 Launch checklist | Release doc; AdSense review submitted | 2 | P2 |

---

## Delivery order (dependencies)

1. **A5-2** (merge baseline) + **A1** (install) → platform usable.
2. **A2/A3** (CI + tests) in parallel → platform trustworthy.
3. **B1** (architecture-first — hard prerequisite) → then B2/B3 (data+API) →
   B4/B5 (frontend+3D) → B6 (monetization) → B7 (security) → B8 (launch).

## Jira mapping

- Each `EPIC X` → Jira **Epic** (summary = epic title, label `initiative-a`/`initiative-b`).
- Each `X-n` row → Jira **Story** linked to its epic; description = acceptance
  criteria; story points = Pts; priority = Pri; labels by area
  (`scraper`,`frontend`,`a11y`,`security`,`adsense`,`3d`,`data`,`ci`).
- Sprints: suggest 2-week; Sprint 1 = A5-2, A1-1/2, B1-1/2/3.
