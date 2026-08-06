#!/usr/bin/env python3
"""Pre-commit security scanner (defensive, first-party).

Scans files for committed secrets and risky code patterns before they enter
git history. Used by the global pre-commit gate (security-precommit.sh) and
directly by the security-tester agent.

Severity model:
  * CRITICAL — blocks the commit (exit 1 in --gate mode): real secrets
    (cloud/API keys, private keys, credentialed connection URIs) and staged
    .env-style files.
  * WARN — reported but never blocking: dangerous-but-contextual patterns
    (eval, innerHTML, string-built SQL, shell=True, ...).

Usage:
    security-precommit.py --staged [--gate]   # scan git-staged files
    security-precommit.py <path> [--gate]     # scan a file or tree
"""

from __future__ import annotations

import argparse
import re
import subprocess
import sys
from pathlib import Path

SKIP_DIRS = {".git", ".claude", "node_modules", "dist", "build", ".next",
             "out", "__pycache__", ".venv", "venv", "coverage", "vendor"}
BINARY_EXTS = {".png", ".jpg", ".jpeg", ".gif", ".webp", ".ico", ".pdf",
               ".zip", ".gz", ".mp3", ".mp4", ".woff", ".woff2", ".ttf"}

# --- CRITICAL: secrets --------------------------------------------------------
SECRET_PATTERNS: list[tuple[str, re.Pattern]] = [
    ("aws-access-key", re.compile(r"\bAKIA[0-9A-Z]{16}\b")),
    ("aws-secret-key", re.compile(
        r"aws.{0,20}secret.{0,20}['\"][0-9A-Za-z/+=]{40}['\"]", re.I)),
    ("private-key-block", re.compile(
        r"-----BEGIN (?:RSA |EC |DSA |OPENSSH |PGP )?PRIVATE KEY(?: BLOCK)?-----")),
    ("github-token", re.compile(r"\bgh[pousr]_[0-9A-Za-z]{36,}\b")),
    ("openai-key", re.compile(r"\bsk-[0-9A-Za-z_-]{20,}\b")),
    ("anthropic-key", re.compile(r"\bsk-ant-[0-9A-Za-z_-]{20,}\b")),
    ("slack-token", re.compile(r"\bxox[baprs]-[0-9A-Za-z-]{10,}\b")),
    ("google-api-key", re.compile(r"\bAIza[0-9A-Za-z_-]{35}\b")),
    ("stripe-key", re.compile(r"\b[sr]k_live_[0-9A-Za-z]{20,}\b")),
    ("credentialed-uri", re.compile(
        r"\b(?:mongodb(?:\+srv)?|postgres(?:ql)?|mysql|redis|amqp)://"
        r"[^\s:@/'\"]+:[^\s@/'\"]{4,}@", re.I)),
    ("jwt-in-source", re.compile(
        r"\beyJ[0-9A-Za-z_-]{10,}\.eyJ[0-9A-Za-z_-]{10,}\.[0-9A-Za-z_-]{10,}\b")),
]
ENV_FILE = re.compile(r"(^|/)\.env(\.|$)")

# --- WARN: risky patterns -----------------------------------------------------
RISK_PATTERNS: list[tuple[str, re.Pattern, str]] = [
    ("eval-exec", re.compile(r"\b(?:eval|exec)\s*\("),
     "eval/exec — code injection risk if input reaches it"),
    ("inner-html", re.compile(r"\.(innerHTML|outerHTML)\s*=|dangerouslySetInnerHTML"),
     "raw HTML injection — XSS risk; sanitize or use textContent"),
    ("document-write", re.compile(r"document\.write\s*\("),
     "document.write — XSS-prone and blocks parsing"),
    ("sql-concat", re.compile(
        r"(?:SELECT|INSERT|UPDATE|DELETE)\b[^\n]{0,80}(?:\+\s*\w|%s*['\"]?\s*%|"
        r"f['\"](?:[^'\"\n]*\{))", re.I),
     "SQL built from strings — use parameterized queries"),
    ("shell-true", re.compile(r"subprocess\.[A-Za-z_]+\([^)]*shell\s*=\s*True"),
     "subprocess with shell=True — command injection risk"),
    ("os-system", re.compile(r"\bos\.system\s*\("),
     "os.system — prefer subprocess with an argument list"),
    ("pickle-load", re.compile(r"\bpickle\.loads?\s*\("),
     "pickle deserialization — arbitrary code execution on untrusted data"),
    ("yaml-unsafe", re.compile(r"\byaml\.load\s*\((?![^)]*Loader)"),
     "yaml.load without a safe Loader — use yaml.safe_load"),
    ("debug-true", re.compile(r"\bdebug\s*=\s*True\b", re.I),
     "debug mode flag — must be off in production"),
    ("cors-wildcard", re.compile(
        r"Access-Control-Allow-Origin[^\n]{0,10}[:=][^\n]{0,10}\*"),
     "wildcard CORS — restrict allowed origins"),
    ("verify-false", re.compile(r"\bverify\s*=\s*False\b"),
     "TLS verification disabled — never ship this"),
    ("http-endpoint", re.compile(r"['\"]http://(?!localhost|127\.0\.0\.1|0\.0\.0\.0)[\w.-]+"),
     "plain-HTTP endpoint — use HTTPS"),
]

ALLOW_MARKER = "security-ok:"  # inline suppression, e.g. // security-ok: test fixture


def staged_files() -> list[Path]:
    out = subprocess.run(
        ["git", "diff", "--cached", "--name-only", "--diff-filter=ACM"],
        capture_output=True, text=True, check=False)
    return [Path(p) for p in out.stdout.splitlines() if p.strip()]


def iter_target(target: str) -> list[Path]:
    root = Path(target)
    if root.is_file():
        return [root]
    return [p for p in root.rglob("*") if p.is_file()
            and not any(part in SKIP_DIRS for part in p.parts)]


def scan_file(path: Path) -> list[tuple[str, str, int, str, str]]:
    """Return (severity, rule, line, snippet, note) findings for one file."""
    findings = []
    rel = str(path)
    if any(part in SKIP_DIRS for part in path.parts):
        return findings
    if ENV_FILE.search(rel.replace("\\", "/")) and path.name != ".env.example":
        findings.append(("CRITICAL", "env-file", 0, path.name,
                         "environment file staged — keep secrets out of git "
                         "(commit a .env.example instead)"))
        return findings
    if path.suffix.lower() in BINARY_EXTS:
        return findings
    try:
        text = path.read_text(encoding="utf-8", errors="ignore")
    except OSError:
        return findings
    lines = text.splitlines()
    for i, line in enumerate(lines, 1):
        if ALLOW_MARKER in line:
            continue
        for rule, rx in SECRET_PATTERNS:
            if rx.search(line):
                findings.append(("CRITICAL", rule, i, line.strip()[:100],
                                 "possible secret — move to env var and ROTATE it"))
        for rule, rx, note in RISK_PATTERNS:
            if rx.search(line):
                findings.append(("WARN", rule, i, line.strip()[:100], note))
    return findings


def main(argv: list[str] | None = None) -> int:
    ap = argparse.ArgumentParser(description="Pre-commit security scanner")
    ap.add_argument("target", nargs="?", help="file or directory to scan")
    ap.add_argument("--staged", action="store_true", help="scan git-staged files")
    ap.add_argument("--gate", action="store_true",
                    help="exit 1 if any CRITICAL finding (used by the hook)")
    args = ap.parse_args(argv)

    if args.staged:
        files = staged_files()
    elif args.target:
        files = iter_target(args.target)
    else:
        ap.error("provide a target path or --staged")

    all_findings: dict[str, list] = {}
    for f in files:
        if f.exists():
            found = scan_file(f)
            if found:
                all_findings[str(f)] = found

    n_crit = sum(1 for fs in all_findings.values()
                 for (sev, *_rest) in fs if sev == "CRITICAL")
    n_warn = sum(1 for fs in all_findings.values()
                 for (sev, *_rest) in fs if sev == "WARN")

    if not all_findings:
        print(f"security-precommit: {len(files)} file(s) scanned, no findings.")
    else:
        print("security-precommit findings:")
        for fp, fs in all_findings.items():
            print(f"\n{fp}")
            for sev, rule, line, snippet, note in fs:
                icon = "✗" if sev == "CRITICAL" else "⚠"
                loc = f"L{line}" if line else "-"
                print(f"  {icon} {sev:<8} {loc:<6} [{rule}] {note}")
                if snippet and line:
                    print(f"      | {snippet}")
        print(f"\n{n_crit} CRITICAL, {n_warn} WARN. "
              f"(suppress a false positive with an inline '{ALLOW_MARKER} reason' comment)")

    if args.gate and n_crit:
        return 1
    return 0


if __name__ == "__main__":
    sys.exit(main())
