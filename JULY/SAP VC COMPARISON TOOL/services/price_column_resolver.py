from __future__ import annotations

import itertools
import re
from dataclasses import dataclass, field
from typing import Any


PRICE_COLUMN_CRITERIA_NOT_CONFIGURED = "price_column_criteria_not_configured"
PRICE_COLUMN_KEY_MISSING = "price_column_key_missing"
PRICE_COLUMN_NOT_FOUND = "price_column_not_found"
AMBIGUOUS_PRICE_COLUMN = "ambiguous_price_column"

ALL_CRITERIA = "ALL_CRITERIA"
PARTIAL_CRITERIA = "PARTIAL_CRITERIA"
SINGLE_CRITERION = "SINGLE_CRITERION"
NOT_FOUND = "NOT_FOUND"
AMBIGUOUS = "AMBIGUOUS"


@dataclass(frozen=True)
class ColumnCandidate:
    column_index: int
    raw_parts: list[str]
    normalized_tokens: list[str]
    token_groups: list[set[str]] = field(default_factory=list)
    matched_keys: list[str] = field(default_factory=list)


@dataclass(frozen=True)
class PriceColumnResolution:
    success: bool
    column_index: int | None
    configured_keys: list[str]
    catalog_values: dict[str, str]
    matched_keys: list[str]
    matched_header_parts: list[str]
    match_level: str | None
    confidence: str
    candidate_columns: list[ColumnCandidate]
    diagnostic: str | None
    reason: str


def resolve_price_column(
    *,
    table: Any,
    price_columns: dict[int, str],
    catalog_context: dict[str, Any],
    column_criteria: dict[str, Any] | None,
    selected_row: Any | None = None,
) -> PriceColumnResolution:
    configured_keys = _configured_keys(column_criteria)
    catalog_values, criterion_alternatives, missing_keys = _criterion_alternatives(configured_keys, catalog_context)
    candidates = _column_candidates(table, price_columns, selected_row)

    if not price_columns:
        return _result(False, None, configured_keys, catalog_values, [], [], NOT_FOUND, "LOW", candidates, PRICE_COLUMN_NOT_FOUND, "No credible Master Price columns were detected.")
    if len(price_columns) == 1:
        column_index = next(iter(price_columns))
        candidate = next((item for item in candidates if item.column_index == column_index), None)
        return _result(True, column_index, configured_keys, catalog_values, [], candidate.raw_parts if candidate else [], SINGLE_CRITERION, "HIGH", candidates, None, "Only one credible Master Price column exists.")
    if not configured_keys:
        return _result(False, None, configured_keys, catalog_values, [], [], NOT_FOUND, "LOW", candidates, PRICE_COLUMN_CRITERIA_NOT_CONFIGURED, "Multiple price columns exist, but no price-column criteria are configured.")

    available_keys = [key for key in configured_keys if key in criterion_alternatives]
    if not available_keys:
        return _result(False, None, configured_keys, catalog_values, [], [], NOT_FOUND, "LOW", candidates, PRICE_COLUMN_KEY_MISSING, "None of the configured price-column criteria were available in the catalog context.")

    for size in range(len(available_keys), 0, -1):
        for key_subset in itertools.combinations(available_keys, size):
            matches = [_candidate_with_matches(candidate, key_subset, criterion_alternatives) for candidate in candidates]
            matches = [candidate for candidate in matches if set(key_subset).issubset(candidate.matched_keys)]
            if not matches:
                continue
            match_level = ALL_CRITERIA if size == len(configured_keys) and not missing_keys else PARTIAL_CRITERIA
            if size == 1:
                match_level = SINGLE_CRITERION
            if len(matches) == 1:
                selected = matches[0]
                diagnostic = PRICE_COLUMN_KEY_MISSING if missing_keys else None
                reason = f"Selected column using {', '.join(key_subset)}."
                if missing_keys:
                    reason += f" Missing configured criteria: {', '.join(missing_keys)}."
                return _result(True, selected.column_index, configured_keys, catalog_values, list(key_subset), selected.raw_parts, match_level, "HIGH" if match_level == ALL_CRITERIA else "MEDIUM", matches, diagnostic, reason)
            return _result(False, None, configured_keys, catalog_values, list(key_subset), [], AMBIGUOUS, "LOW", matches, AMBIGUOUS_PRICE_COLUMN, f"Criteria {', '.join(key_subset)} matched multiple price columns.")

    return _result(False, None, configured_keys, catalog_values, [], [], NOT_FOUND, "LOW", candidates, PRICE_COLUMN_NOT_FOUND, "No price column matched the configured criteria.")


def normalize_header_tokens(value: str) -> list[str]:
    normalized = str(value or "").upper().replace("\n", " ")
    return re.findall(r"[A-Z0-9]+", normalized)


def _configured_keys(column_criteria: dict[str, Any] | None) -> list[str]:
    if not isinstance(column_criteria, dict) or not column_criteria.get("enabled"):
        return []
    keys: list[str] = []
    for key in column_criteria.get("keys") or []:
        normalized = str(key or "").strip().upper()
        if normalized and normalized not in keys:
            keys.append(normalized)
    return keys


def _criterion_alternatives(
    configured_keys: list[str],
    catalog_context: dict[str, Any],
) -> tuple[dict[str, str], dict[str, list[set[str]]], list[str]]:
    structure_values = catalog_context.get("structure_values") if isinstance(catalog_context, dict) else {}
    structure_aliases = catalog_context.get("structure_aliases") if isinstance(catalog_context, dict) else {}
    catalog_values: dict[str, str] = {}
    alternatives: dict[str, list[set[str]]] = {}
    missing: list[str] = []

    for key in configured_keys:
        raw_value = str((structure_values or {}).get(key, "")).strip()
        alias_values = [str(value).strip() for value in (structure_aliases or {}).get(key, []) if str(value).strip()]
        if not raw_value and not alias_values:
            missing.append(key)
            continue
        if raw_value:
            catalog_values[key] = raw_value
        token_sets: list[set[str]] = []
        for value in [raw_value, *alias_values]:
            tokens = set(normalize_header_tokens(value))
            if tokens and tokens not in token_sets:
                token_sets.append(tokens)
            ordered_tokens = normalize_header_tokens(value)
            if len(ordered_tokens) > 1:
                first_token = {ordered_tokens[0]}
                if first_token not in token_sets:
                    token_sets.append(first_token)
        alternatives[key] = token_sets
    return catalog_values, alternatives, missing


def _column_candidates(table: Any, price_columns: dict[int, str], selected_row: Any | None) -> list[ColumnCandidate]:
    rows = list(getattr(table, "rows", []) or [])
    selected_row_number = getattr(selected_row, "row_number", None)
    header_rows = _header_rows_for_signature(rows, selected_row_number)
    candidates: list[ColumnCandidate] = []

    for column_index in sorted(price_columns):
        raw_parts: list[str] = []
        for row in header_rows:
            raw_cells = getattr(row, "raw_cells", []) or []
            if 0 <= column_index < len(raw_cells):
                value = str(raw_cells[column_index] or "").strip()
                if value and value not in raw_parts:
                    raw_parts.append(value)
        fallback_header = str(price_columns.get(column_index) or "").strip()
        if fallback_header and not _has_equivalent_header_part(raw_parts, fallback_header):
            raw_parts.append(fallback_header)
        tokens: list[str] = []
        for part in raw_parts:
            for token in normalize_header_tokens(part):
                if token not in tokens:
                    tokens.append(token)
        candidates.append(
            ColumnCandidate(
                column_index=column_index,
                raw_parts=raw_parts,
                normalized_tokens=tokens,
                token_groups=_candidate_token_groups(raw_parts),
            )
        )
    return candidates


def _has_equivalent_header_part(raw_parts: list[str], fallback_header: str) -> bool:
    fallback_tokens = normalize_header_tokens(fallback_header)
    return any(normalize_header_tokens(part) == fallback_tokens for part in raw_parts)


def _header_rows_for_signature(rows: list[Any], selected_row_number: int | None) -> list[Any]:
    header_rows: list[Any] = []
    for row in rows:
        row_number = getattr(row, "row_number", 0)
        if selected_row_number is not None and row_number >= selected_row_number:
            break
        raw_cells = getattr(row, "raw_cells", []) or []
        first_cell = str(raw_cells[0] if raw_cells else "").strip()
        if header_rows and first_cell and not _looks_like_header_first_cell(first_cell):
            break
        header_rows.append(row)
    return header_rows


def _looks_like_header_first_cell(value: str) -> bool:
    tokens = set(normalize_header_tokens(value))
    return bool(tokens & {"DESCRIPTION", "CODE", "ORDER", "DIGIT", "POSITION", "VOLTAGE", "UNIT", "WHERE", "USED"})


def _candidate_token_groups(raw_parts: list[str]) -> list[set[str]]:
    if not raw_parts:
        return []
    segment_groups = [_segments_for_part(part) for part in raw_parts]
    groups: list[set[str]] = []
    for combination in itertools.product(*segment_groups):
        tokens: set[str] = set()
        for segment in combination:
            tokens.update(segment)
        if tokens and tokens not in groups:
            groups.append(tokens)
    return groups


def _segments_for_part(part: str) -> list[set[str]]:
    segments: list[set[str]] = []
    for segment in re.split(r"[\r\n]+", str(part or "")):
        tokens = set(normalize_header_tokens(segment))
        if tokens and tokens not in segments:
            segments.append(tokens)
    return segments or [set()]


def _candidate_with_matches(
    candidate: ColumnCandidate,
    keys: tuple[str, ...],
    criterion_alternatives: dict[str, list[set[str]]],
) -> ColumnCandidate:
    token_groups = candidate.token_groups or [set(candidate.normalized_tokens)]
    best_matched_keys: list[str] = []
    for token_set in token_groups:
        matched_keys = [
            key
            for key in keys
            if any(alternative and alternative.issubset(token_set) for alternative in criterion_alternatives.get(key, []))
        ]
        if len(matched_keys) > len(best_matched_keys):
            best_matched_keys = matched_keys
        if set(keys).issubset(matched_keys):
            break
    return ColumnCandidate(candidate.column_index, candidate.raw_parts, candidate.normalized_tokens, candidate.token_groups, best_matched_keys)


def _result(
    success: bool,
    column_index: int | None,
    configured_keys: list[str],
    catalog_values: dict[str, str],
    matched_keys: list[str],
    matched_header_parts: list[str],
    match_level: str | None,
    confidence: str,
    candidate_columns: list[ColumnCandidate],
    diagnostic: str | None,
    reason: str,
) -> PriceColumnResolution:
    return PriceColumnResolution(success, column_index, configured_keys, catalog_values, matched_keys, matched_header_parts, match_level, confidence, candidate_columns, diagnostic, reason)
