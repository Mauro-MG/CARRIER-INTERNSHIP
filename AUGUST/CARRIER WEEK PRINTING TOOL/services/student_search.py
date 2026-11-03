"""Student search matching shared by the desktop UI and tests."""

from __future__ import annotations

from collections.abc import Mapping
from typing import Any

from services.excel_importer import search_key


SEARCH_FIELDS = ("UniqueID", "Nombre completo", "Carrera")


def matches_student_search(student: Mapping[str, Any], query: str) -> bool:
    """Return whether a partial, accent-insensitive query matches a student."""
    needle = search_key(query)
    if not needle:
        return True
    return any(needle in search_key(student.get(field, "")) for field in SEARCH_FIELDS)
