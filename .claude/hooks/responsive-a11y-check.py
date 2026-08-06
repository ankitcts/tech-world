#!/usr/bin/env python3
"""Static responsive + WCAG-AA heuristic checker.

Fast, dependency-free scan of web source files for machine-detectable
responsive-design and accessibility (WCAG 2.1 AA) problems. Used two ways:

* Directly / by the responsive-a11y agent:
    python3 responsive-a11y-check.py <file-or-dir> [--json]
* As a PostToolUse hook (via responsive-a11y-hook.sh) after every Edit/Write,
  in which case it checks just the changed file and prints findings for the
  agent to act on.

Static analysis cannot verify contrast ratios, keyboard flow, or screen-reader
semantics — those stay with the responsive-a11y agent's browser pass. Exit code
is always 0 (findings inform; they do not block).
"""

from __future__ import annotations

import argparse
import json
import re
import sys
from pathlib import Path

WEB_EXTS = {".html", ".htm", ".css", ".scss", ".jsx", ".tsx", ".vue", ".svelte"}
SKIP_DIRS = {".git", ".claude", "node_modules", "dist", "build", ".next", "out",
             "coverage", "vendor", "__pycache__", ".venv", "venv"}

Finding = tuple[str, int, str, str]  # (level, line, rule, message)


def _lines_matching(text: str, pattern: str, flags=re.I) -> list[int]:
    rx = re.compile(pattern, flags)
    return [i + 1 for i, ln in enumerate(text.splitlines()) if rx.search(ln)]


def check_htmlish(text: str, is_full_page: bool) -> list[Finding]:
    f: list[Finding] = []
    low = text.lower()

    # --- Responsive ---------------------------------------------------------
    if is_full_page:
        if "<meta" not in low or "viewport" not in low:
            f.append(("ERROR", 1, "viewport",
                      "missing <meta name=\"viewport\"> — page will not be responsive"))
        if re.search(r"user-scalable\s*=\s*no|maximum-scale\s*=\s*1(\.0)?[\"'\s,]", low):
            f.append(("ERROR", 1, "zoom-disabled",
                      "viewport disables user zoom — WCAG 1.4.4 violation"))
        if not re.search(r"<html[^>]*\slang\s*=", low):
            f.append(("ERROR", 1, "lang",
                      "<html> missing lang attribute — WCAG 3.1.1"))
        if "<title" not in low:
            f.append(("WARN", 1, "title", "page has no <title> — WCAG 2.4.2"))
        if "<main" not in low:
            f.append(("WARN", 1, "landmarks",
                      "no <main> landmark — add semantic landmarks for AT users"))

    # --- Images without alt -------------------------------------------------
    for m in re.finditer(r"<img\b[^>]*>", text, re.I | re.S):
        tag = m.group(0)
        if not re.search(r"\balt\s*=", tag, re.I):
            line = text[: m.start()].count("\n") + 1
            f.append(("ERROR", line, "img-alt",
                      "<img> without alt attribute — WCAG 1.1.1 (use alt=\"\" if decorative)"))

    # --- Inputs without labels ---------------------------------------------
    for m in re.finditer(r"<(input|select|textarea)\b[^>]*>", text, re.I):
        tag = m.group(0)
        if re.search(r"type\s*=\s*[\"'](hidden|submit|button|reset)[\"']", tag, re.I):
            continue
        if re.search(r"aria-label(ledby)?\s*=|\bid\s*=", tag, re.I):
            continue  # id may be labelled via <label for>; aria-label ok
        line = text[: m.start()].count("\n") + 1
        f.append(("WARN", line, "input-label",
                  f"<{m.group(1)}> has no id/aria-label — ensure it is labelled (WCAG 3.3.2)"))

    # --- Click handlers on non-interactive elements (JSX/HTML) -------------
    for m in re.finditer(r"<(div|span)\b[^>]*\bonclick\s*=", text, re.I):
        tag_start = m.start()
        tag = text[tag_start: text.find(">", tag_start) + 1]
        if not re.search(r"\brole\s*=|\btabindex\s*=", tag, re.I):
            line = text[:tag_start].count("\n") + 1
            f.append(("ERROR", line, "click-div",
                      f"onClick on <{m.group(1)}> without role/tabindex — not keyboard "
                      "accessible (WCAG 2.1.1); use <button>"))

    # --- Positive tabindex ---------------------------------------------------
    for line_no in _lines_matching(text, r"tabindex\s*=\s*[\"']?[1-9]"):
        f.append(("ERROR", line_no, "tabindex",
                  "positive tabindex breaks natural focus order — use 0 or -1"))

    # --- target=_blank without rel ------------------------------------------
    for m in re.finditer(r"<a\b[^>]*target\s*=\s*[\"']_blank[\"'][^>]*>", text, re.I):
        if not re.search(r"rel\s*=\s*[\"'][^\"']*(noopener|noreferrer)", m.group(0), re.I):
            line = text[: m.start()].count("\n") + 1
            f.append(("WARN", line, "blank-rel",
                      "target=_blank without rel=noopener — security/UX issue"))

    # --- Empty links/buttons -------------------------------------------------
    for m in re.finditer(r"<(a|button)\b[^>]*>\s*</\1>", text, re.I):
        tag = m.group(0)
        if not re.search(r"aria-label(ledby)?\s*=", tag, re.I):
            line = text[: m.start()].count("\n") + 1
            f.append(("ERROR", line, "empty-control",
                      f"empty <{m.group(1)}> with no accessible name — WCAG 4.1.2"))

    return f


def check_css(text: str) -> list[Finding]:
    f: list[Finding] = []
    has_media = "@media" in text or "@container" in text
    if not has_media and len(text) > 800:
        f.append(("WARN", 1, "media-queries",
                  "stylesheet has no @media/@container queries — verify responsiveness"))

    # Fixed large pixel widths on layout properties.
    for m in re.finditer(r"(?<![-\w])(width|min-width)\s*:\s*(\d{3,})px", text, re.I):
        if int(m.group(2)) > 400:
            line = text[: m.start()].count("\n") + 1
            f.append(("WARN", line, "fixed-width",
                      f"{m.group(1)}: {m.group(2)}px — fixed width may break reflow at "
                      "320px (WCAG 1.4.10); prefer max-width/%/clamp()"))

    # px font sizes (blocks 200% text resize behaviour with some setups).
    px_fonts = _lines_matching(text, r"font-size\s*:\s*\d+px")
    if px_fonts:
        f.append(("WARN", px_fonts[0], "px-font",
                  f"font-size in px on {len(px_fonts)} line(s) — prefer rem for WCAG 1.4.4"))

    # outline removal without replacement focus style.
    for line_no in _lines_matching(text, r"outline\s*:\s*(none|0)"):
        f.append(("WARN", line_no, "focus-visible",
                  "outline removed — ensure a visible :focus-visible style exists (WCAG 2.4.7)"))

    # prefers-reduced-motion when animating.
    if re.search(r"@keyframes|animation\s*:|transition\s*:", text, re.I) and \
       "prefers-reduced-motion" not in text:
        f.append(("WARN", 1, "reduced-motion",
                  "animations present but no prefers-reduced-motion handling"))
    return f


def check_file(path: Path) -> list[Finding]:
    try:
        text = path.read_text(encoding="utf-8", errors="ignore")
    except OSError:
        return []
    ext = path.suffix.lower()
    if ext in {".css", ".scss"}:
        return check_css(text)
    if ext in {".html", ".htm"}:
        return check_htmlish(text, is_full_page="<html" in text.lower())
    if ext in {".jsx", ".tsx", ".vue", ".svelte"}:
        findings = check_htmlish(text, is_full_page=False)
        findings += check_css(text) if "<style" in text.lower() else []
        return findings
    return []


def main(argv: list[str] | None = None) -> int:
    ap = argparse.ArgumentParser(description="Responsive + WCAG-AA static checker")
    ap.add_argument("target", nargs="?", default=".")
    ap.add_argument("--json", action="store_true")
    args = ap.parse_args(argv)

    root = Path(args.target)
    if root.is_file():
        files = [root] if root.suffix.lower() in WEB_EXTS else []
    else:
        files = [p for p in root.rglob("*")
                 if p.suffix.lower() in WEB_EXTS
                 and not any(part in SKIP_DIRS for part in p.parts)]

    all_findings: dict[str, list[Finding]] = {}
    for p in files:
        found = check_file(p)
        if found:
            all_findings[str(p)] = found

    if args.json:
        print(json.dumps({fp: [{"level": l, "line": ln, "rule": r, "msg": m}
                               for l, ln, r, m in fs]
                          for fp, fs in all_findings.items()}, indent=2))
        return 0

    if not all_findings:
        if files:
            print(f"responsive-a11y: {len(files)} file(s) checked, no static issues found.")
        return 0

    n_err = n_warn = 0
    print("responsive-a11y findings (static heuristics — contrast/keyboard/AT "
          "still need the browser pass):")
    for fp, fs in all_findings.items():
        print(f"\n{fp}")
        for level, line, rule, msg in sorted(fs, key=lambda x: x[1]):
            icon = "✗" if level == "ERROR" else "⚠"
            print(f"  {icon} L{line:<5} [{rule}] {msg}")
            if level == "ERROR":
                n_err += 1
            else:
                n_warn += 1
    print(f"\n{n_err} error(s), {n_warn} warning(s). "
          "Fix errors before shipping; verify warnings.")
    return 0


if __name__ == "__main__":
    sys.exit(main())
