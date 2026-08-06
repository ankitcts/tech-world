"""Daily agent endpoint: refresh the company dataset from SEC EDGAR.

Stage 1 of the TechAtlas daily agent. Vercel Cron hits this once a day (see
`vercel.json`), sending `Authorization: Bearer $CRON_SECRET`; when that env var
is set the function rejects anything else, so the public cannot trigger a run.

It connects to MongoDB (the source of truth), runs the bounded refresh
(`build_dataset.run_refresh`), and returns the run summary as JSON. All heavy
lifting — SEC I/O, parsing, provenance — lives in the pipeline package, bundled
alongside this function via `vercel.json` `includeFiles`.

Deployed as a Vercel Python Serverless Function at `/api/refresh`.
"""

from __future__ import annotations

import json
import os
import sys
from datetime import datetime, timezone
from http.server import BaseHTTPRequestHandler
from pathlib import Path

# Bundled alongside the function via vercel.json `includeFiles`.
REPO_ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(REPO_ROOT))


def _now_iso() -> str:
    return datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ")


class handler(BaseHTTPRequestHandler):
    def _send(self, status: int, payload: dict) -> None:
        body = json.dumps(payload).encode("utf-8")
        self.send_response(status)
        self.send_header("Content-Type", "application/json; charset=utf-8")
        self.send_header("Cache-Control", "no-store")
        self.send_header("Content-Length", str(len(body)))
        self.end_headers()
        self.wfile.write(body)

    def do_GET(self):  # noqa: N802 - Vercel handler contract
        secret = os.environ.get("CRON_SECRET")
        if secret:
            # Vercel Cron sends the secret as a Bearer header; also accept it as a
            # ?key= query param so the run can be triggered manually from a browser.
            from urllib.parse import urlparse, parse_qs

            auth = self.headers.get("Authorization", "")
            key = parse_qs(urlparse(self.path).query).get("key", [""])[0]
            if auth != f"Bearer {secret}" and key != secret:
                self._send(401, {"error": "unauthorized"})
                return

        try:
            from apps.techatlas.pipeline.build_dataset import run_refresh
            from apps.techatlas.pipeline.models import get_database

            db = get_database()
            summary = run_refresh(db, now_iso=_now_iso())
            self._send(200, {"ok": True, "summary": summary})
        except Exception as exc:  # noqa: BLE001 - report failure, never fabricate
            self._send(500, {"ok": False, "error": str(exc)})
