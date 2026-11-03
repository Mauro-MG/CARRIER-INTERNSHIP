from __future__ import annotations

from dataclasses import dataclass
from typing import Any


CODE_BASED = "code_based"
CHARACTER_BASED = "character_based"
VALID_SEARCH_MODES = {CODE_BASED, CHARACTER_BASED}


@dataclass(frozen=True)
class PositionSearchToken:
    position: int
    catalog_character: str
    search_token: str
    source_mode: str


def get_search_mode(configuration: dict[str, Any]) -> str:
    """Return the explicit configuration search mode, defaulting old JSON to code-based."""
    raw_mode = str(configuration.get("search_mode", CODE_BASED) or CODE_BASED).strip().lower()
    return raw_mode if raw_mode in VALID_SEARCH_MODES else raw_mode


def search_mode_label(search_mode: str | None) -> str:
    mode = str(search_mode or CODE_BASED).strip().lower()
    if mode == CHARACTER_BASED:
        return "Character Based"
    return "Code Based"


def resolve_position_search_tokens(catalog_number: str, configuration: dict[str, Any]) -> list[PositionSearchToken]:
    search_mode = get_search_mode(configuration)
    if search_mode == CHARACTER_BASED:
        return _resolve_character_based_tokens(catalog_number, configuration)
    return _resolve_code_based_tokens(catalog_number, configuration)


def option_positions_for_character_mode(configuration: dict[str, Any]) -> list[int]:
    configured_search_positions = option_search_positions(configuration)
    if configured_search_positions:
        return configured_search_positions

    positions: set[int] = set()
    for row in configuration.get("structure", []) or []:
        if not isinstance(row, dict):
            continue
        characteristic_key = str(row.get("characteristic_key", "")).strip().upper()
        if characteristic_key not in {"OPTIONS", "OPTION", "OPTION_POSITIONS", "CONFIGURABLE_OPTIONS"}:
            continue
        for position in _positions_from_start_end(row.get("start_position"), row.get("end_position")):
            positions.add(position)
    if positions:
        return sorted(positions)

    configured_positions = configuration.get("configured_positions", [])
    return sorted({int(position) for position in configured_positions or [] if _is_positive_int(position)})


def option_search_positions(configuration: dict[str, Any]) -> list[int]:
    option_positions = configuration.get("option_positions")
    if isinstance(option_positions, dict):
        positions = _positions_from_start_end(option_positions.get("start"), option_positions.get("end"))
        if positions:
            return positions
    return []


def _resolve_code_based_tokens(catalog_number: str, configuration: dict[str, Any]) -> list[PositionSearchToken]:
    catalog = str(catalog_number or "").strip().upper()
    tokens: list[PositionSearchToken] = []
    position_configs = configuration.get("positions", {})
    allowed_positions = set(option_search_positions(configuration))

    for position in _coerce_positions(configuration.get("configured_positions", [])):
        if allowed_positions and position not in allowed_positions:
            continue
        if position > len(catalog):
            continue
        catalog_character = catalog[position - 1 : position]
        mapped_tokens = _mapped_option_codes_for_position(position_configs.get(str(position), {}), catalog_character)
        if not mapped_tokens:
            tokens.append(PositionSearchToken(position, catalog_character, "", CODE_BASED))
            continue
        for search_token in mapped_tokens:
            tokens.append(PositionSearchToken(position, catalog_character, search_token, CODE_BASED))
    return tokens


def _resolve_character_based_tokens(catalog_number: str, configuration: dict[str, Any]) -> list[PositionSearchToken]:
    catalog = str(catalog_number or "").strip().upper()
    tokens: list[PositionSearchToken] = []
    for position in option_positions_for_character_mode(configuration):
        if position > len(catalog):
            continue
        catalog_character = catalog[position - 1 : position]
        tokens.append(PositionSearchToken(position, catalog_character, catalog_character, CHARACTER_BASED))
    return tokens


def _mapped_option_codes_for_position(position_config: dict[str, Any], catalog_character: str) -> list[str]:
    wanted_value = _normalize_search_token(catalog_character)
    allowed_values_by_code = position_config.get("allowed_values_by_option_code") or {}
    normalized_allowed_values: dict[str, set[str]] = {}

    for raw_option_code, raw_allowed_values in allowed_values_by_code.items():
        option_code = _normalize_search_token(raw_option_code)
        if not option_code:
            continue
        normalized_allowed_values[option_code] = {
            _normalize_search_token(value) for value in raw_allowed_values or [] if _normalize_search_token(value)
        }

    configured_option_codes = position_config.get("option_codes") or list(allowed_values_by_code.keys())
    mapped_codes: list[str] = []
    seen: set[str] = set()
    for raw_option_code in configured_option_codes:
        option_code = _normalize_search_token(raw_option_code)
        if not option_code or option_code in seen:
            continue
        if wanted_value in normalized_allowed_values.get(option_code, set()):
            mapped_codes.append(option_code)
            seen.add(option_code)
    return mapped_codes


def _coerce_positions(raw_positions: Any) -> list[int]:
    positions: list[int] = []
    for raw_position in raw_positions or []:
        try:
            position = int(raw_position)
        except (TypeError, ValueError):
            continue
        if position > 0:
            positions.append(position)
    return sorted(set(positions))


def _positions_from_start_end(start: Any, end: Any) -> list[int]:
    try:
        start_position = int(start)
        end_position = int(end)
    except (TypeError, ValueError):
        return []
    if start_position < 1 or end_position < start_position:
        return []
    return list(range(start_position, end_position + 1))


def _is_positive_int(value: Any) -> bool:
    try:
        return int(value) > 0
    except (TypeError, ValueError):
        return False


def _normalize_search_token(value: Any) -> str:
    return "".join(str(value or "").strip().upper().split())
