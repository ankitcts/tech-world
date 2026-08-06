"""Command-line entry point for the web-scraper toolkit.

Examples
--------
Static page, extract repeating records::

    python -m scraper fetch https://example.com \
        --scope "article.post" \
        --select title="h2.title" url="a.headline@href" \
        --format csv

JS-rendered page (headless Chromium)::

    python -m scraper fetch https://example.com/app \
        --mode dynamic --wait-selector ".loaded" \
        --select price=".price"

API endpoint, pull a nested field::

    python -m scraper fetch https://api.example.com/v1/items \
        --mode api --json-path "data.items"

All HTML tables on a page::

    python -m scraper fetch https://example.com/stats --tables
"""

from __future__ import annotations

import argparse
import sys
from typing import Optional

from . import extractors, output
from .fetchers import fetch


def _parse_kv(pairs: Optional[list[str]]) -> dict[str, str]:
    """Turn ``["a=b", "c=d"]`` into ``{"a": "b", "c": "d"}``."""
    result: dict[str, str] = {}
    for pair in pairs or []:
        if "=" not in pair:
            raise SystemExit(f"expected key=value, got: {pair!r}")
        key, value = pair.split("=", 1)
        result[key.strip()] = value.strip()
    return result


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        prog="scraper",
        description="Scrape static pages, JS-rendered pages, and APIs.",
    )
    sub = parser.add_subparsers(dest="command", required=True)

    f = sub.add_parser("fetch", help="fetch a URL and extract data")
    f.add_argument("url")
    f.add_argument(
        "--mode",
        choices=["static", "dynamic", "api"],
        default="static",
        help="fetch strategy (default: static)",
    )
    # Extraction options (mutually complementary; pick what fits the target).
    f.add_argument("--select", nargs="*", metavar="field=selector",
                   help="CSS selectors; use @attr suffix to read an attribute")
    f.add_argument("--scope", help="CSS selector for the repeating container")
    f.add_argument("--tables", action="store_true",
                   help="extract every HTML <table>")
    f.add_argument("--links", action="store_true",
                   help="extract every anchor as text+url")
    f.add_argument("--json-path", help="dotted path into API JSON (api mode)")
    # Fetch tuning.
    f.add_argument("--header", nargs="*", metavar="Name=Value",
                   help="extra request headers")
    f.add_argument("--wait-selector",
                   help="dynamic mode: wait for this selector before reading")
    f.add_argument("--wait-ms", type=int, default=0,
                   help="dynamic mode: extra settle time in milliseconds")
    f.add_argument("--timeout", type=int, default=30)
    # Output.
    f.add_argument("--format", choices=["json", "csv", "text"], default="json")
    f.add_argument("--out", help="write to this file instead of stdout")
    return parser


def run_fetch(args: argparse.Namespace) -> int:
    headers = _parse_kv(args.header)

    fetch_kwargs: dict = {"headers": headers, "timeout": args.timeout}
    if args.mode == "dynamic":
        fetch_kwargs["wait_selector"] = args.wait_selector
        fetch_kwargs["wait_ms"] = args.wait_ms

    result = fetch(args.mode, args.url, **fetch_kwargs)
    if result.status >= 400:
        print(f"warning: {args.url} returned HTTP {result.status}",
              file=sys.stderr)

    # Decide what to extract.
    if args.json_path is not None or (args.mode == "api" and not any(
            [args.select, args.tables, args.links])):
        records = extractors.extract_json_path(result.content,
                                               args.json_path or "")
    elif args.tables:
        tables = extractors.extract_tables(result.content)
        # Flatten single-table results for convenience.
        records = tables[0] if len(tables) == 1 else tables
    elif args.links:
        records = extractors.extract_links(result.content, base_url=result.url)
    elif args.select:
        selectors = _parse_kv(args.select)
        records = extractors.extract_by_selectors(
            result.content, selectors, scope=args.scope)
    else:
        # No extraction requested: return the raw content.
        records = result.content

    if isinstance(records, str):
        payload = records
    else:
        payload = output.serialize(records, args.format)

    if args.out:
        with open(args.out, "w", encoding="utf-8") as fh:
            fh.write(payload)
        n = len(records) if isinstance(records, list) else 1
        print(f"wrote {n} record(s) to {args.out} "
              f"({result.mode}, {result.elapsed:.2f}s)", file=sys.stderr)
    else:
        print(payload)
    return 0


def main(argv: Optional[list[str]] = None) -> int:
    args = build_parser().parse_args(argv)
    if args.command == "fetch":
        return run_fetch(args)
    return 1


if __name__ == "__main__":
    raise SystemExit(main())
