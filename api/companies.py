"""Read endpoint: serve companies + domains for the frontend.

MongoDB is the source of truth (populated by the daily `/api/refresh` cron).
This function reads it live and is CDN-cached, so the Three.js app always shows
the latest daily snapshot without a rebuild. If Mongo is unreachable or empty it
falls back to the curated seed so the site never breaks.

Deployed as a Vercel Python Serverless Function at `/api/companies`.
"""

from __future__ import annotations

import json
import sys
from http.server import BaseHTTPRequestHandler
from pathlib import Path

# Bundled alongside the function via vercel.json `includeFiles`.
REPO_ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(REPO_ROOT))
SEED = REPO_ROOT / "apps" / "techatlas" / "pipeline" / "seed_data.json"


def _from_mongo() -> dict:
    from apps.techatlas.pipeline.models import (
        get_database, DomainRepository, CompanyRepository)
    db = get_database()
    return {
        "domains": DomainRepository(db).all(),
        "companies": CompanyRepository(db).all(),
    }


def _from_seed() -> dict:
    return json.loads(SEED.read_text(encoding="utf-8"))


class handler(BaseHTTPRequestHandler):
    def do_GET(self):  # noqa: N802 - Vercel handler contract
        try:
            data = _from_mongo()
            source = "mongo"
            if not data.get("companies"):
                data, source = _from_seed(), "seed-empty"
        except Exception:  # noqa: BLE001 - never fail the read; degrade to seed
            data, source = _from_seed(), "seed-fallback"

        payload = json.dumps(data).encode("utf-8")
        self.send_response(200)
        self.send_header("Content-Type", "application/json; charset=utf-8")
        # Short CDN cache so refreshes show up quickly (the pipeline updates
        # MongoDB continuously): fresh for 30s, serve-stale up to 5min.
        self.send_header(
            "Cache-Control", "public, s-maxage=30, stale-while-revalidate=300")
        self.send_header("X-Data-Source", source)
        self.send_header("Content-Length", str(len(payload)))
        self.end_headers()
        self.wfile.write(payload)
