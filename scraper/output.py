"""Serialize extracted records to JSON, CSV, or plain text."""

from __future__ import annotations

import csv
import io
import json
from typing import Any


def to_json(records: Any, *, pretty: bool = True) -> str:
    return json.dumps(records, indent=2 if pretty else None, ensure_ascii=False)


def to_csv(records: list[dict]) -> str:
    if not records:
        return ""
    # Union of keys preserves every column even with ragged records.
    fieldnames: list[str] = []
    for row in records:
        for key in row:
            if key not in fieldnames:
                fieldnames.append(key)
    buf = io.StringIO()
    writer = csv.DictWriter(buf, fieldnames=fieldnames, extrasaction="ignore")
    writer.writeheader()
    for row in records:
        writer.writerow({k: row.get(k, "") for k in fieldnames})
    return buf.getvalue()


def to_text(records: list[dict]) -> str:
    lines: list[str] = []
    for i, row in enumerate(records):
        lines.append(f"--- record {i} ---")
        for key, value in row.items():
            lines.append(f"{key}: {value}")
    return "\n".join(lines)


def serialize(records: Any, fmt: str) -> str:
    if fmt == "json":
        return to_json(records)
    if fmt == "csv":
        if not isinstance(records, list):
            raise ValueError("csv output requires a list of records")
        return to_csv(records)
    if fmt == "text":
        if not isinstance(records, list):
            records = [records]
        return to_text(records)
    raise ValueError(f"unknown format: {fmt!r} (expected json|csv|text)")
