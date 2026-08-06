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
        from urllib.parse import urlparse, parse_qs

        query = urlparse(self.path).query
        params = parse_qs(query)
        try:
            chain = int((params.get("chain", ["0"])[0] or "0"))
        except ValueError:
            chain = 0

        secret = (os.environ.get("CRON_SECRET") or "").strip()
        if secret:
            # Vercel Cron sends the secret as a Bearer header; also accept it as a
            # ?key= query param so the run can be triggered manually from a browser.
            # Values are stripped because pasted env vars often carry a trailing
            # newline/space that would otherwise never match.
            auth = self.headers.get("Authorization", "").strip()
            key = (params.get("key", [""])[0] or "").strip()
            if auth != f"Bearer {secret}" and key != secret:
                # Safe diagnostics only — never echoes the secret or the key value.
                self._send(401, {
                    "error": "unauthorized",
                    "hint": {
                        "secret_configured": True,
                        "received_key_len": len(key),
                        "secret_len": len(secret),
                        "received_auth_header": bool(auth),
                        "path_has_query": bool(query),
                    },
                })
                return

        # Maintenance: drop the bulky raw_filings collection to free space
        # (e.g. after hitting a free-tier storage quota). Whitelisted + secret-
        # gated. Deletes are permitted even when writes are quota-blocked.
        purge = (params.get("purge", [""])[0] or "").strip()
        if purge:
            allowed = {"raw_filings"}
            if purge not in allowed:
                self._send(400, {"ok": False, "error": f"purge allowed only for {sorted(allowed)}"})
                return
            try:
                from apps.techatlas.pipeline.models import get_database

                get_database()[purge].drop()
                self._send(200, {"ok": True, "purged": purge})
            except Exception as exc:  # noqa: BLE001
                self._send(500, {"ok": False, "error": str(exc)})
            return

        try:
            from apps.techatlas.pipeline.build_dataset import run_refresh
            from apps.techatlas.pipeline.models import get_database

            db = get_database()
            summary = run_refresh(db, now_iso=_now_iso())
            self._send(200, {"ok": True, "summary": summary})
        except Exception as exc:  # noqa: BLE001 - report failure, never fabricate
            self._send(500, {"ok": False, "error": str(exc)})
            return

        # Self-continue the backfill so a single fire drains the backlog without
        # anyone re-hitting the URL. Best-effort (works on the public production
        # deployment; preview deployments are auth-gated). Bounded + opt-out.
        self._maybe_continue(secret, chain, summary)

    def _maybe_continue(self, secret: str, chain: int, summary: dict) -> None:
        auto = (os.environ.get("TECHATLAS_AUTO_CONTINUE", "1").strip().lower()
                not in ("0", "false", "no", "off", ""))
        try:
            chain_max = int(os.environ.get("TECHATLAS_CHAIN_MAX", "500"))
        except ValueError:
            chain_max = 500
        if not (auto and secret and chain < chain_max):
            return
        if summary.get("enriched", 0) <= 0 or summary.get("unenriched_remaining", 0) <= 0:
            return
        host = os.environ.get("VERCEL_URL")
        if not host:
            return
        try:
            import urllib.request
            from urllib.parse import quote

            url = f"https://{host}/api/refresh?key={quote(secret)}&chain={chain + 1}"
            req = urllib.request.Request(url, headers={"User-Agent": "techatlas-selfcontinue"})
            # Kick the next invocation; don't block on its full run. The daily
            # cron resumes via the stalest-first cursor if this link is dropped.
            urllib.request.urlopen(req, timeout=3).read(0)
        except Exception:  # noqa: BLE001 - best-effort; never fail the primary run
            pass
