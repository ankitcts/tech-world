#!/usr/bin/env python3
"""Heuristic AdSense-compliance auditor.

Scans a project directory for the machine-checkable AdSense requirements and
reports PASS / WARN / FAIL per item. It cannot judge content quality, ad
placement, or traffic — those are manual (see ../references/checklist.md).

Exit codes:
  * default mode : always 0 (it only reports).
  * --gate mode  : 0 if the project does NOT integrate AdSense (not applicable)
                   or all hard blockers pass; 1 if AdSense is integrated and a
                   hard blocker FAILs. Used by the pre-push hook.

Hard blockers (gate): ads.txt present & valid, and a privacy-policy page.
Everything else is a WARN and never blocks a push on its own.

Usage:
    python audit.py <project-dir> [--gate] [--json]
"""

from __future__ import annotations

import argparse
import json
import re
import sys
from pathlib import Path

SKIP_DIRS = {".git", ".claude", "node_modules", ".venv", "venv", "dist", "build",
             ".next", "out", "__pycache__", ".cache", "coverage", "vendor"}
TEXT_EXTS = {".html", ".htm", ".js", ".jsx", ".ts", ".tsx", ".vue", ".svelte",
             ".md", ".mdx", ".php", ".astro", ".ejs", ".hbs", ".txt", ".json"}
# AdSense integration is only detected in real web *code* — never in markdown
# or plain-text docs, which routinely *mention* AdSense (specs, changelogs,
# this skill itself) without integrating it. Prevents false "integrated" flags.
CODE_EXTS = {".html", ".htm", ".js", ".jsx", ".ts", ".tsx", ".vue", ".svelte",
             ".php", ".astro", ".ejs", ".hbs"}
MAX_BYTES = 2_000_000  # skip very large files

ADSENSE_SIGNALS = [
    "pagead2.googlesyndication.com",
    "adsbygoogle",
    "data-ad-client",
    re.compile(r"ca-pub-\d{10,20}"),
]
CONSENT_SIGNALS = [
    "__tcfapi", "fundingchoicesmessages", "funding-choices",
    "consent", "cookiebot", "onetrust", "cookieconsent", "quantcast",
    "gtag('consent'", 'gtag("consent"', "consentmode", "consent mode",
]
PRIVACY_HINTS = ["privacy policy", "privacy-policy", "privacypolicy",
                 "/privacy", "privacy.html", "privacy.md"]


class Result:
    def __init__(self):
        self.items: list[tuple[str, str, str]] = []  # (level, name, detail)

    def add(self, level: str, name: str, detail: str = "") -> None:
        self.items.append((level, name, detail))

    def has_fail(self) -> bool:
        return any(lvl == "FAIL" for lvl, _, _ in self.items)


def iter_files(root: Path):
    for p in root.rglob("*"):
        if p.is_dir():
            if p.name in SKIP_DIRS:
                # prune by skipping; rglob can't prune, so filter on parts
                continue
            continue
        if any(part in SKIP_DIRS for part in p.parts):
            continue
        yield p


def read_text(p: Path) -> str:
    try:
        if p.stat().st_size > MAX_BYTES:
            return ""
        return p.read_text(encoding="utf-8", errors="ignore")
    except OSError:
        return ""


def matches(text: str, signal) -> bool:
    if isinstance(signal, re.Pattern):
        return signal.search(text) is not None
    return signal in text


def audit(root: Path) -> tuple[Result, bool]:
    result = Result()
    files = [p for p in iter_files(root) if p.suffix.lower() in TEXT_EXTS
             or p.name in {"ads.txt", "app-ads.txt", "robots.txt", "sitemap.xml"}]

    # --- Detect AdSense integration -----------------------------------------
    adsense_used = False
    pub_ids: set[str] = set()
    consent_found = False
    privacy_found = False
    for p in files:
        low = read_text(p).lower()
        if not low:
            continue
        if p.suffix.lower() in CODE_EXTS and any(matches(low, s) for s in ADSENSE_SIGNALS):
            adsense_used = True
            for m in re.findall(r"ca-pub-\d{10,20}", low):
                pub_ids.add(m.replace("ca-", ""))
        if any(s in low for s in CONSENT_SIGNALS):
            consent_found = True
        if any(h in low for h in PRIVACY_HINTS) or p.name.lower().startswith("privacy"):
            privacy_found = True

    # --- ads.txt -------------------------------------------------------------
    ads_txt_paths = [root / "ads.txt", root / "public" / "ads.txt",
                     root / "static" / "ads.txt", root / "www" / "ads.txt"]
    ads_txt = next((p for p in ads_txt_paths if p.exists()), None)
    if ads_txt is None:
        result.add("FAIL" if adsense_used else "WARN", "ads.txt",
                   "no ads.txt found at root/public/static")
    else:
        content = read_text(ads_txt).lower()
        if re.search(r"google\.com\s*,\s*pub-\d{10,20}\s*,\s*direct", content):
            result.add("PASS", "ads.txt", f"valid google line in {ads_txt.name}")
        else:
            result.add("FAIL" if adsense_used else "WARN", "ads.txt",
                       "present but missing a valid 'google.com, pub-..., DIRECT' line")

    # --- Privacy policy ------------------------------------------------------
    if privacy_found:
        result.add("PASS", "privacy-policy", "privacy policy page/link detected")
    else:
        result.add("FAIL" if adsense_used else "WARN", "privacy-policy",
                   "no privacy policy page/link detected (AdSense requires one)")

    # --- Consent / CMP -------------------------------------------------------
    if consent_found:
        result.add("PASS", "consent-cmp", "consent/CMP signal detected")
    else:
        result.add("WARN", "consent-cmp",
                   "no CMP / Consent Mode signal found (required for EEA/UK users)")

    # --- AdSense tag validity ------------------------------------------------
    if adsense_used:
        if pub_ids:
            result.add("PASS", "adsense-tag",
                       f"AdSense code present ({', '.join(sorted(pub_ids))})")
        else:
            result.add("WARN", "adsense-tag",
                       "AdSense script present but no ca-pub- client id found")
    else:
        result.add("WARN", "adsense-tag",
                   "no AdSense code detected (skill not applicable, or ads not wired yet)")

    # --- Crawlability signals ------------------------------------------------
    robots = next((root / n for n in ["robots.txt", "public/robots.txt",
                                      "static/robots.txt"] if (root / n).exists()), None)
    if robots and re.search(r"disallow:\s*/\s*$", read_text(robots).lower(), re.M):
        result.add("WARN", "robots.txt", "robots.txt appears to block all crawling (Disallow: /)")
    elif robots:
        result.add("PASS", "robots.txt", "present")
    else:
        result.add("WARN", "robots.txt", "no robots.txt found")

    sitemap = any((root / n).exists() for n in
                  ["sitemap.xml", "public/sitemap.xml", "static/sitemap.xml"])
    result.add("PASS" if sitemap else "WARN", "sitemap.xml",
               "present" if sitemap else "no sitemap.xml found")

    # Site-wide noindex is a red flag for ad serving.
    noindex = False
    for p in files:
        if p.suffix.lower() in {".html", ".htm"} and "noindex" in read_text(p).lower():
            noindex = True
            break
    if noindex:
        result.add("WARN", "indexability", "a 'noindex' directive was found in HTML")

    return result, adsense_used


ICON = {"PASS": "✓", "WARN": "⚠", "FAIL": "✗"}


def main(argv: list[str] | None = None) -> int:
    ap = argparse.ArgumentParser(description="Audit a project for AdSense compliance")
    ap.add_argument("project_dir", nargs="?", default=".")
    ap.add_argument("--gate", action="store_true",
                    help="exit 1 only if AdSense is used and a hard blocker fails")
    ap.add_argument("--json", action="store_true")
    args = ap.parse_args(argv)

    root = Path(args.project_dir).resolve()
    if not root.exists():
        print(f"error: {root} does not exist", file=sys.stderr)
        return 2

    result, adsense_used = audit(root)

    if args.json:
        print(json.dumps({
            "adsense_used": adsense_used,
            "items": [{"level": l, "name": n, "detail": d}
                      for l, n, d in result.items],
        }, indent=2))
    else:
        print(f"AdSense compliance audit — {root}")
        print(f"AdSense integrated: {'yes' if adsense_used else 'no'}\n")
        for level, name, detail in result.items:
            print(f"  {ICON.get(level, '?')} {level:<4} {name:<16} {detail}")
        fails = [n for l, n, _ in result.items if l == "FAIL"]
        warns = [n for l, n, _ in result.items if l == "WARN"]
        print(f"\n  {len(fails)} FAIL, {len(warns)} WARN. "
              f"See references/checklist.md for the manual items "
              f"(content quality, placement, traffic).")

    if args.gate:
        # Only block when the project actually serves AdSense and a blocker fails.
        if adsense_used and result.has_fail():
            return 1
        return 0
    return 0


if __name__ == "__main__":
    sys.exit(main())
