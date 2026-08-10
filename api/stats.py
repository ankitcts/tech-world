"""Lightweight progress endpoint for the live-updating frontend.

The landing page polls this every few seconds to learn whether the dataset has
changed (new companies enriched, more logos resolved) without re-downloading the
full `/api/companies` payload each time. It returns only small counts, so it is
cheap to hit repeatedly. When Mongo is unreachable it degrades softly (``ok:
false``) rather than erroring, so the poller just skips that tick.

Deployed as a Vercel Python Serverless Function at `/api/stats`.
"""

from __future__ import annotations

import json
import sys
from http.server import BaseHTTPRequestHandler
from pathlib import Path

# Bundled alongside the function via vercel.json `includeFiles`.
REPO_ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(REPO_ROOT))


def _stats() -> dict:
    from apps.techatlas.pipeline.models import (
        AgentRunRepository, CompanyRepository, get_database)

    db = get_database()
    comp = CompanyRepository(db)
    cursor = AgentRunRepository(db).get_cursor()
    return {
        "ok": True,
        "source": "mongo",
        "companies": comp.col.estimated_document_count(),
        # Only VERIFIED logos count (logo_url set + non-null); recorded misses
        # (logo_url == None) and never-checked docs are excluded.
        "logos": comp.col.count_documents({"logo_url": {"$ne": None}}),
        "logos_remaining": comp.count_missing_logo(),
        "unenriched_remaining": comp.count_unenriched(),
        "last_run_at": cursor.get("last_run_at"),
    }


class handler(BaseHTTPRequestHandler):
    def do_GET(self):  # noqa: N802 - Vercel handler contract
        try:
            payload = _stats()
        except Exception as exc:  # noqa: BLE001 - soft-fail; poller skips the tick
            payload = {"ok": False, "source": "unavailable", "error": str(exc)}

        body = json.dumps(payload).encode("utf-8")
        self.send_response(200)
        self.send_header("Content-Type", "application/json; charset=utf-8")
        # Tiny CDN window so rapid polling collapses to one origin hit / ~5s.
        self.send_header("Cache-Control", "public, s-maxage=5, stale-while-revalidate=15")
        self.send_header("Content-Length", str(len(body)))
        self.end_headers()
        self.wfile.write(body)
