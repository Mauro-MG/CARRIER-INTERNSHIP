from __future__ import annotations

import re
from dataclasses import dataclass
from typing import Any


RANGE_SEARCH = "range"
FULL_SEARCH = "full_search"

_PLACEHOLDER_RE = re.compile(r"\{(\d+)(?::(\d+))?\}")
_BRACE_RE = re.compile(r"[{}]")


@dataclass(frozen=True)
class BaseUnitResolution:
    source_catalog_number: str
    search_type: str | None
    search_value: str | None
    success: bool
    error: str | None


def resolve_base_unit_search(catalog_number: str, base_unit_rule: dict[str, Any] | None) -> BaseUnitResolution:
    """Resolve the configured base-unit DOCX search value for a full SAP catalog number."""
    source = str(catalog_number or "").strip().upper()
    if not isinstance(base_unit_rule, dict) or not base_unit_rule.get("enabled"):
        return BaseUnitResolution(source, None, None, False, "Base unit price extraction is not configured.")

    search_type = str(base_unit_rule.get("search_type", "")).strip().lower()
    if search_type == RANGE_SEARCH:
        return _resolve_range(source, base_unit_rule)
    if search_type == FULL_SEARCH:
        return _resolve_template(source, base_unit_rule)

    return BaseUnitResolution(source, search_type or None, None, False, "Base unit search type must be range or full_search.")


def validate_base_unit_rule(base_unit_rule: Any) -> list[str]:
    """Validate base-unit rule shape without requiring a sample catalog number."""
    errors: list[str] = []
    if base_unit_rule is None:
        return errors
    if not isinstance(base_unit_rule, dict):
        return ["Base Unit Master Price Rule must be stored as an object."]
    if not base_unit_rule.get("enabled"):
        return errors

    search_type = str(base_unit_rule.get("search_type", "")).strip().lower()
    if search_type not in {RANGE_SEARCH, FULL_SEARCH}:
        return ["Base Unit Master Price Rule search type must be range or full_search."]

    if search_type == RANGE_SEARCH:
        start_position = _coerce_positive_int(base_unit_rule.get("start_position"))
        end_position = _coerce_positive_int(base_unit_rule.get("end_position"))
        if start_position is None:
            errors.append("Base Unit range search requires a start position of 1 or greater.")
        if end_position is None:
            errors.append("Base Unit range search requires an end position of 1 or greater.")
        if start_position is not None and end_position is not None and end_position < start_position:
            errors.append("Base Unit range search end position cannot come before start position.")
        return errors

    template = str(base_unit_rule.get("template", "")).strip()
    if not template:
        return ["Base Unit full search requires a template."]
    return _validate_template_syntax(template)


def preview_base_unit_search(catalog_number: str, base_unit_rule: dict[str, Any] | None) -> str:
    """Small helper for tests/UI-like callers that want only the value or an empty string."""
    resolution = resolve_base_unit_search(catalog_number, base_unit_rule)
    return resolution.search_value or ""


def _resolve_range(source: str, rule: dict[str, Any]) -> BaseUnitResolution:
    start_position = _coerce_positive_int(rule.get("start_position"))
    end_position = _coerce_positive_int(rule.get("end_position"))
    if start_position is None or end_position is None:
        return BaseUnitResolution(source, RANGE_SEARCH, None, False, "Range search requires numeric start and end positions of 1 or greater.")
    if end_position < start_position:
        return BaseUnitResolution(source, RANGE_SEARCH, None, False, "Range search end position cannot come before start position.")
    if end_position > len(source):
        return BaseUnitResolution(
            source,
            RANGE_SEARCH,
            None,
            False,
            f"Range search requested position {end_position}, but the catalog number contains only {len(source)} characters.",
        )
    return BaseUnitResolution(source, RANGE_SEARCH, source[start_position - 1 : end_position], True, None)


def _resolve_template(source: str, rule: dict[str, Any]) -> BaseUnitResolution:
    template = str(rule.get("template", "")).strip()
    syntax_errors = _validate_template_syntax(template)
    if syntax_errors:
        return BaseUnitResolution(source, FULL_SEARCH, None, False, "; ".join(syntax_errors))

    parts: list[str] = []
    cursor = 0
    for match in _PLACEHOLDER_RE.finditer(template):
        parts.append(template[cursor : match.start()])
        start_position = int(match.group(1))
        end_position = int(match.group(2) or match.group(1))
        if end_position > len(source):
            return BaseUnitResolution(
                source,
                FULL_SEARCH,
                None,
                False,
                f"Template requested catalog position {end_position} but the entered catalog number contains only {len(source)} characters.",
            )
        parts.append(source[start_position - 1 : end_position])
        cursor = match.end()
    parts.append(template[cursor:])

    return BaseUnitResolution(source, FULL_SEARCH, "".join(parts).upper(), True, None)


def _validate_template_syntax(template: str) -> list[str]:
    errors: list[str] = []
    if not template:
        return ["Base Unit full search requires a template."]

    cursor = 0
    for match in _PLACEHOLDER_RE.finditer(template):
        literal = template[cursor : match.start()]
        if _BRACE_RE.search(literal):
            errors.append(f"Malformed Base Unit template near {literal!r}.")
            break
        start_position = int(match.group(1))
        end_position = int(match.group(2) or match.group(1))
        if start_position < 1:
            errors.append("Base Unit template positions must be 1 or greater.")
        if end_position < start_position:
            errors.append("Base Unit template range end cannot come before its start.")
        cursor = match.end()

    tail = template[cursor:]
    if _BRACE_RE.search(tail):
        errors.append(f"Malformed Base Unit template near {tail!r}.")

    if not list(_PLACEHOLDER_RE.finditer(template)):
        errors.append("Base Unit full search template must include at least one placeholder such as {1} or {1:4}.")
    return errors


def _coerce_positive_int(value: Any) -> int | None:
    try:
        result = int(value)
    except (TypeError, ValueError):
        return None
    return result if result >= 1 else None
