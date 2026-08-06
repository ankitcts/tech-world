---
name: living-docs
description: >-
  Use this skill continuously while developing ANY feature, fix, or change:
  it keeps living documentation and a running changelog up to date on every
  change, and cuts versioned release notes + a release log when a release is
  made. Trigger whenever code or behavior changes, when the user says
  "document this", "update the changelog", "cut/tag a release", "release
  notes", "what changed", "bump version", or after implementing anything that
  alters how the system works. Also applies right after any commit-worthy edit.
---

# Living Documentation & Release Notes

This skill makes documentation a continuous byproduct of development, not an
afterthought. Every change is recorded as it happens; releases turn the
accumulated record into versioned, permanent notes.

Conventions: **Semantic Versioning** (MAJOR.MINOR.PATCH) and
**Keep a Changelog** (https://keepachangelog.com).

## Artifacts this skill maintains

- **`CHANGELOG.md`** (repo root) — the single running log. Newest at top, an
  `[Unreleased]` section that accumulates changes between releases, then one
  dated section per released version.
- **`docs/releases/vX.Y.Z.md`** — a fuller, permanent release document created
  when a version is cut (highlights, full change list, upgrade/migration notes,
  known issues).
- **`docs/`** — feature/system docs that are updated in the same change that
  alters behavior (never let docs drift from code).

## Continuous loop — do this on EVERY change

Every time you implement or modify something worth a commit:

1. **Add a changelog entry** to the `[Unreleased]` section of `CHANGELOG.md`,
   under the right category:
   - `Added` — new features/capabilities.
   - `Changed` — changes to existing behavior.
   - `Deprecated` — soon-to-be-removed features.
   - `Removed` — removed features.
   - `Fixed` — bug fixes.
   - `Security` — vulnerability fixes.
   Write it for a human reader (what changed and why it matters), not a git
   subject line. One bullet per user-visible change.
2. **Update affected docs** in `docs/` in the *same* change (API surface, config,
   usage, behavior). Code and docs move together.
3. Keep entries factual and scoped to what actually changed in this iteration.

Never batch this up "for later" — the whole point is that the record is always
current. If several changes land in one turn, log each as its own bullet.

## Cutting a release

When the user asks to release / tag / bump a version:

1. **Choose the version** by SemVer against the accumulated `[Unreleased]`
   entries: breaking → MAJOR, new backward-compatible features → MINOR,
   only fixes → PATCH. Confirm the number with the user if ambiguous.
2. **Run the release script** (preferred — it does the moves atomically):
   ```bash
   python .claude/skills/living-docs/scripts/cut_release.py X.Y.Z
   ```
   It will:
   - Move everything under `[Unreleased]` into a new dated `[X.Y.Z]` section in
     `CHANGELOG.md` and reset `[Unreleased]` to empty categories.
   - Generate `docs/releases/vX.Y.Z.md` from the release template, pre-filled
     with the version's change list and today's date.
   - Leave a `git tag` suggestion for the user (it does not tag automatically).
3. **Fill in the release doc** highlights, upgrade/migration notes, and known
   issues (the script scaffolds these sections).
4. Commit with a message like `docs: release vX.Y.Z` and, once the user
   approves, tag: `git tag -a vX.Y.Z -m "vX.Y.Z"`.

If the script cannot be used, perform the same moves by hand following
`references/changelog-template.md` and `references/release-template.md`.

## Rules

- **Date only released versions.** `[Unreleased]` never carries a date.
- **Never rewrite released history.** Past version sections are immutable; new
  facts go into `[Unreleased]` or a follow-up patch release.
- **One source of truth.** All change history flows through `CHANGELOG.md`;
  release docs elaborate but do not contradict it.
- **Provenance.** Reference PRs/issues where useful, but keep entries readable
  without following links.
- Do not invent changes — only log what was actually implemented this session.

## Automation

A `UserPromptSubmit` hook (`.claude/hooks/doc-reminder.sh`) injects a short
reminder on each interaction so the running changelog stays current even when
this skill is not explicitly invoked. The hook only nudges; this skill defines
what to write.
