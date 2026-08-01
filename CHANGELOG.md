# Changelog

All notable changes to this project are documented here.

The format is based on [Keep a Changelog](https://keepachangelog.com/en/1.1.0/),
and this project adheres to [Semantic Versioning](https://semver.org/spec/v2.0.0.html).

## [Unreleased]

### Added
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
- Global `responsive-a11y` subagent (`.claude/agents/responsive-a11y.md`) for
  responsive layout and WCAG 2.1 AA accessibility compliance, with a
  dependency-free static checker (`.claude/hooks/responsive-a11y-check.py`)
  and a `PostToolUse` hook that runs it automatically on every change to a
  web source file in any project.

### Changed
### Deprecated
### Removed
### Fixed
### Security
