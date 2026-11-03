from __future__ import annotations

import re

_TYPOGRAPHIC_DASHES = str.maketrans({"–": "-", "—": "-", "−": "-", "‐": "-", "‑": "-"})


def normalize_catalog_number(value: str) -> str:
    """Normalize a catalog number while preserving meaningful punctuation."""
    if not isinstance(value, str):
        raise TypeError("Catalog number must be text.")
    normalized = value.strip().upper().translate(_TYPOGRAPHIC_DASHES)
    return re.sub(r"\s+", "", normalized)
