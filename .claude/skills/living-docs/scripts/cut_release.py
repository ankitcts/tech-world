#!/usr/bin/env python3
"""Cut a release from the running CHANGELOG.

Given a version, this:
  1. Moves everything under `## [Unreleased]` in CHANGELOG.md into a new dated
     `## [X.Y.Z] - YYYY-MM-DD` section directly below Unreleased.
  2. Resets `## [Unreleased]` to empty category headings.
  3. Writes docs/releases/vX.Y.Z.md from the release template, pre-filled with
     this version's change list and date.

It does NOT git-commit or git-tag — it prints the suggested commands so the
human stays in control of history.

Usage:
    python .claude/skills/living-docs/scripts/cut_release.py 1.2.0 [--date YYYY-MM-DD]

Run from the repository root.
"""

from __future__ import annotations

import argparse
import datetime as _dt
import re
import sys
from pathlib import Path

CATEGORIES = ["Added", "Changed", "Deprecated", "Removed", "Fixed", "Security"]
SEMVER_RE = re.compile(r"^\d+\.\d+\.\d+(?:[-+][0-9A-Za-z.\-]+)?$")

HERE = Path(__file__).resolve().parent
RELEASE_TEMPLATE = HERE.parent / "references" / "release-template.md"


def empty_unreleased() -> str:
    body = "\n".join(f"### {c}" for c in CATEGORIES)
    return f"## [Unreleased]\n\n{body}\n"


def split_unreleased(changelog: str) -> tuple[str, str, str]:
    """Return (prefix, unreleased_body, rest).

    prefix           = everything before the `## [Unreleased]` heading.
    unreleased_body  = the content under Unreleased (excluding its heading).
    rest             = the next `## [` section onward (older releases).
    """
    m = re.search(r"^## \[Unreleased\]\s*$", changelog, flags=re.MULTILINE)
    if not m:
        raise SystemExit("error: no '## [Unreleased]' section found in CHANGELOG.md")
    prefix = changelog[: m.start()]
    after = changelog[m.end():]
    # Find the next top-level version section.
    nxt = re.search(r"^## \[", after, flags=re.MULTILINE)
    if nxt:
        unreleased_body = after[: nxt.start()]
        rest = after[nxt.start():]
    else:
        unreleased_body = after
        rest = ""
    return prefix, unreleased_body.strip("\n"), rest


def extract_nonempty(unreleased_body: str) -> str:
    """Return the change bullets under populated categories, or '' if none."""
    lines = unreleased_body.splitlines()
    out: list[str] = []
    current: str | None = None
    buffer: dict[str, list[str]] = {}
    for line in lines:
        h = re.match(r"^### (.+)$", line.strip())
        if h:
            current = h.group(1).strip()
            buffer.setdefault(current, [])
            continue
        if current is not None and line.strip():
            buffer[current].append(line.rstrip())
    for cat in CATEGORIES:
        items = [ln for ln in buffer.get(cat, []) if ln.strip()]
        if items:
            out.append(f"### {cat}")
            out.extend(items)
            out.append("")
    return "\n".join(out).strip("\n")


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description="Cut a release from CHANGELOG.md")
    parser.add_argument("version", help="new version, e.g. 1.2.0")
    parser.add_argument("--date", help="release date YYYY-MM-DD (default: today)")
    parser.add_argument("--repo-root", default=".", help="repository root")
    args = parser.parse_args(argv)

    version = args.version.lstrip("v")
    if not SEMVER_RE.match(version):
        raise SystemExit(f"error: {version!r} is not a valid SemVer version")

    if args.date:
        date = args.date
    else:
        # Date.today() is fine in a standalone script run by the user.
        date = _dt.date.today().isoformat()

    root = Path(args.repo_root).resolve()
    changelog_path = root / "CHANGELOG.md"
    if not changelog_path.exists():
        raise SystemExit(f"error: {changelog_path} not found (run from repo root)")

    changelog = changelog_path.read_text(encoding="utf-8")
    prefix, unreleased_body, rest = split_unreleased(changelog)
    changes = extract_nonempty(unreleased_body)
    if not changes:
        raise SystemExit(
            "error: [Unreleased] has no entries to release. Document changes "
            "in CHANGELOG.md before cutting a release."
        )

    # Rebuild CHANGELOG: prefix + fresh Unreleased + new version section + rest.
    new_section = f"## [{version}] - {date}\n\n{changes}\n"
    new_changelog = (
        prefix.rstrip("\n")
        + "\n\n"
        + empty_unreleased()
        + "\n"
        + new_section
        + ("\n" + rest.lstrip("\n") if rest.strip() else "\n")
    )
    changelog_path.write_text(new_changelog, encoding="utf-8")

    # Write the versioned release document.
    releases_dir = root / "docs" / "releases"
    releases_dir.mkdir(parents=True, exist_ok=True)
    template = (RELEASE_TEMPLATE.read_text(encoding="utf-8")
               if RELEASE_TEMPLATE.exists()
               else "# Release {VERSION} — {DATE}\n\n## Changes\n\n{CHANGES}\n")
    doc = (template
           .replace("{VERSION}", version)
           .replace("{DATE}", date)
           .replace("{CHANGES}", changes)
           .replace("{PREV}", ""))
    release_path = releases_dir / f"v{version}.md"
    release_path.write_text(doc, encoding="utf-8")

    print(f"✓ CHANGELOG.md: added [{version}] - {date}")
    print(f"✓ {release_path.relative_to(root)}: written")
    print("\nNext steps:")
    print(f"  1. Fill in highlights / migration / known-issues in "
          f"{release_path.relative_to(root)}")
    print(f'  2. git add -A && git commit -m "docs: release v{version}"')
    print(f'  3. git tag -a v{version} -m "v{version}"   # after review')
    return 0


if __name__ == "__main__":
    sys.exit(main())
