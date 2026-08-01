"""Export companies + domains from MongoDB to the frontend's data file.

The Three.js app reads `web/public/companies.json`; MongoDB is the source of
truth. Run after scraping/seeding to refresh the frontend data:

    export MONGODB_URI='...'
    python -m apps.techatlas.pipeline.export

With `--from-seed`, it exports the curated `seed_data.json` instead of querying
MongoDB — useful for a first build before the database is populated (this is
how the committed `companies.json` was generated in the sandbox, which has no
Atlas access).
"""

from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path

HERE = Path(__file__).resolve().parent
OUT = HERE.parents[0] / "web" / "public" / "companies.json"


def from_mongo() -> dict:
    from apps.techatlas.pipeline.models import (
        get_database, DomainRepository, CompanyRepository)
    db = get_database()
    return {
        "domains": DomainRepository(db).all(),
        "companies": CompanyRepository(db).all(),
    }


def from_seed() -> dict:
    return json.loads((HERE / "seed_data.json").read_text(encoding="utf-8"))


def main(argv=None) -> int:
    ap = argparse.ArgumentParser(description="Export data for the frontend")
    ap.add_argument("--from-seed", action="store_true",
                    help="export curated seed instead of querying MongoDB")
    args = ap.parse_args(argv)

    data = from_seed() if args.from_seed else from_mongo()
    OUT.parent.mkdir(parents=True, exist_ok=True)
    OUT.write_text(json.dumps(data, indent=2), encoding="utf-8")
    print(f"wrote {len(data['companies'])} companies + {len(data['domains'])} "
          f"domains to {OUT.relative_to(HERE.parents[1])}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
