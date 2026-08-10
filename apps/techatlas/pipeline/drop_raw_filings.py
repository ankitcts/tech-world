"""Maintenance: drop the ``raw_filings`` collection to free storage.

Use when the cluster hits a storage quota (e.g. the Atlas free tier's 512 MB).
The pipeline stores filing *references* (URL + metadata) by default now, so the
bulky ``raw_filings`` documents from an earlier full-text run can be dropped
without losing anything the RAG stage needs — it re-fetches from the SEC URL.

Reads the connection ONLY from the environment (never hardcoded), matching the
rest of the pipeline. Run from the repo root:

    MONGODB_URI='mongodb+srv://…' python -m apps.techatlas.pipeline.drop_raw_filings
"""

from __future__ import annotations

from apps.techatlas.pipeline.models import RawFilingRepository, get_database


def main() -> int:
    db = get_database()
    name = RawFilingRepository.collection_name
    before = db[name].estimated_document_count()
    db[name].drop()
    print(f"Dropped '{name}' ({before} documents). Storage freed.")
    print("Next refresh repopulates it reference-only (URL + metadata).")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
