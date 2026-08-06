"""Industry domains derived from **real SEC data** — nothing hand-picked.

A company's domain is taken directly from the industry description SEC assigns to
it (the ``sicDescription`` on its EDGAR submission). We do **not** maintain our
own catalog of domains: the domain set is exactly the set of industries present
in the fetched data ("all available domains", straight from the source).

Domain ids and colors are derived deterministically from the label so a domain
keeps a stable identity/color across runs without being stored or guessed.
"""

from __future__ import annotations

import colorsys
import hashlib
import re

# Single fallback for records SEC leaves without an industry description.
_UNKNOWN = {"id": "unknown", "label": "Uncategorized", "color": "#8892A0"}


def _slug(text: str) -> str:
    s = re.sub(r"[^a-z0-9]+", "-", text.strip().lower()).strip("-")
    return s or "uncategorized"


def _color_for(domain_id: str) -> str:
    """Deterministic, well-spread hex color derived from the domain id."""
    h = int(hashlib.sha1(domain_id.encode("utf-8")).hexdigest(), 16)
    hue = (h % 360) / 360.0
    r, g, b = colorsys.hls_to_rgb(hue, 0.55, 0.55)
    return "#{:02X}{:02X}{:02X}".format(int(r * 255), int(g * 255), int(b * 255))


def domain_for(description: str | None = None, sic: str | int | None = None) -> dict:
    """Build a domain ``{id, label, color}`` from real SEC fields.

    ``description`` is SEC's own ``sicDescription`` (preferred, verbatim). If it
    is missing we fall back to the bare SIC code; if both are missing the record
    is ``Uncategorized`` — we never invent an industry name.
    """
    label = (description or "").strip()
    if not label and sic not in (None, ""):
        label = f"SIC {str(sic).strip()}"
    if not label:
        return dict(_UNKNOWN)
    domain_id = f"sic-{_slug(label)}"
    return {"id": domain_id, "label": label, "color": _color_for(domain_id)}


def domains_from_records(records: list[dict]) -> list[dict]:
    """Distinct domains actually present, from records' real SEC fields.

    Each record is expected to carry ``sic_description`` (and/or ``sic``). Result
    is sorted by label for stable display order.
    """
    by_id: dict[str, dict] = {}
    for r in records:
        d = domain_for(r.get("sic_description"), r.get("sic"))
        by_id.setdefault(d["id"], d)
    return sorted(by_id.values(), key=lambda d: d["label"].lower())
