"""Employee-count tiers ("horizons") — the single source of truth.

The dataset is segmented by verified employee headcount into the bands below.
Boundaries are lower-inclusive / upper-exclusive so every count maps to exactly
one tier. A company whose headcount cannot be verified from an authoritative
source (SEC 10-K) is assigned ``unknown`` — it is never guessed into a band.
"""

from __future__ import annotations

# id, label, lower bound (inclusive), upper bound (exclusive; None = open-ended)
TIERS: list[dict] = [
    {"id": "lt-100",    "label": "< 100",             "min": 0,      "max": 100},
    {"id": "100-1k",    "label": "100 – 1,000",       "min": 100,    "max": 1_000},
    {"id": "1k-10k",    "label": "1,000 – 10,000",    "min": 1_000,  "max": 10_000},
    {"id": "10k-50k",   "label": "10,000 – 50,000",   "min": 10_000, "max": 50_000},
    {"id": "50k-100k",  "label": "50,000 – 100,000",  "min": 50_000, "max": 100_000},
    {"id": "100k-200k", "label": "100,000 – 200,000", "min": 100_000, "max": 200_000},
    {"id": "200k-300k", "label": "200,000 – 300,000", "min": 200_000, "max": 300_000},
    {"id": "300k-plus", "label": "300,000+",          "min": 300_000, "max": None},
]

UNKNOWN_TIER = {"id": "unknown", "label": "Unknown (unverified)", "min": None, "max": None}

_ORDERED = TIERS  # kept sorted by ascending min by construction


def classify_tier(employees: int | None) -> str:
    """Return the tier id for a verified headcount, or ``unknown``.

    ``None`` (no authoritative value) maps to ``unknown``. Negative or
    non-integer inputs are treated as unverifiable rather than forced into a
    band — we never fabricate a tier.
    """
    if employees is None:
        return UNKNOWN_TIER["id"]
    if not isinstance(employees, int) or isinstance(employees, bool):
        return UNKNOWN_TIER["id"]
    if employees < 0:
        return UNKNOWN_TIER["id"]
    for tier in _ORDERED:
        lo, hi = tier["min"], tier["max"]
        if employees >= lo and (hi is None or employees < hi):
            return tier["id"]
    return UNKNOWN_TIER["id"]


def all_tiers(include_unknown: bool = True) -> list[dict]:
    """Return tier definitions in display order (optionally with ``unknown``)."""
    return [*TIERS, UNKNOWN_TIER] if include_unknown else list(TIERS)
