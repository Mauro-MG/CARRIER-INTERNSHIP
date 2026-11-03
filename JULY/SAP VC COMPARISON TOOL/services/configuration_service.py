from __future__ import annotations

from datetime import datetime
from typing import Any

from services.configuration_validator import VALID_POSITIONS
from services.option_code_generator import OptionCodeError, generate_option_code_range, sort_option_codes
from services.search_token_resolver import CODE_BASED


SCHEMA_VERSION = 1
DEFAULT_STRUCTURE_ROWS = [
    {
        "characteristic_key": "PRODUCT_TYPE",
        "start_position": 1,
        "end_position": 4,
        "description": "Product family or type",
        "used": True,
        "specifications": [],
    },
    {
        "characteristic_key": "UNIT_TYPE",
        "start_position": 5,
        "end_position": 5,
        "description": "Product/unit design character",
        "used": True,
        "specifications": [
            {"catalog_value": "A", "label": "Std without condenser", "description": "", "allowed": True},
            {"catalog_value": "W", "label": "Std with condenser", "description": "", "allowed": True},
            {"catalog_value": "Q", "label": "Std with condenser", "description": "", "allowed": True},
        ],
    },
    {
        "characteristic_key": "TONNAGE",
        "start_position": 6,
        "end_position": 8,
        "description": "Unit size or tonnage",
        "used": True,
        "specifications": [
            {"catalog_value": "017", "label": "017", "description": "", "allowed": True},
            {"catalog_value": "021", "label": "021", "description": "", "allowed": True},
            {"catalog_value": "031", "label": "031", "description": "", "allowed": True},
            {"catalog_value": "033", "label": "033", "description": "", "allowed": True},
            {"catalog_value": "041", "label": "041", "description": "", "allowed": True},
            {"catalog_value": "046", "label": "046", "description": "", "allowed": True},
            {"catalog_value": "051", "label": "051", "description": "", "allowed": True},
            {"catalog_value": "056", "label": "056", "description": "", "allowed": True},
            {"catalog_value": "066", "label": "066", "description": "", "allowed": True},
            {"catalog_value": "080", "label": "080", "description": "", "allowed": True},
        ],
    },
    {
        "characteristic_key": "VOLTAGE",
        "start_position": 9,
        "end_position": 9,
        "description": "Voltage character",
        "used": True,
        "specifications": [
            {"catalog_value": "1", "label": "575-3-60", "description": "", "allowed": True},
            {"catalog_value": "2", "label": "380-3-60", "description": "", "allowed": True},
            {"catalog_value": "5", "label": "208/230-3-60", "description": "", "allowed": True},
            {"catalog_value": "6", "label": "460-3-60", "description": "", "allowed": True},
        ],
    },
    {
        "characteristic_key": "OPTIONS",
        "start_position": 10,
        "end_position": 19,
        "description": "Configurable option characters",
        "used": True,
        "specifications": [],
    },
]


def build_phase1_configuration(
    *,
    product_type: str,
    description: str,
    configuration_date: str,
    version: str,
    selected_positions: list[int],
    ranges_by_position: dict[int, list[dict[str, Any]]],
    existing_created_at: str | None = None,
) -> tuple[dict[str, Any], list[str]]:
    """Build a draft configuration from Phase 1 form values."""
    errors: list[str] = []
    now = datetime.now().replace(microsecond=0).isoformat()
    normalized_positions = [position for position in selected_positions if position in VALID_POSITIONS]

    configuration: dict[str, Any] = {
        "schema_version": SCHEMA_VERSION,
        "search_mode": CODE_BASED,
        "product_type": product_type.strip().upper(),
        "description": description.strip(),
        "configuration_date": configuration_date.strip(),
        "version": _parse_version(version),
        "created_at": existing_created_at or now,
        "updated_at": now,
        "structure": [dict(row) for row in DEFAULT_STRUCTURE_ROWS],
        "option_positions": {"start": 10, "end": 19},
        "base_unit_price_rule": {"enabled": False, "search_type": "range", "start_position": 1, "end_position": 1},
        "price_column_criteria": {"enabled": False, "keys": []},
        "conditional_price_rules": {"enabled": False, "positions": []},
        "configured_positions": normalized_positions,
        "positions": {},
    }

    for position in normalized_positions:
        option_ranges: list[dict[str, Any]] = []
        option_codes: list[str] = []
        for range_data in ranges_by_position.get(position, []):
            try:
                group = int(range_data["group"])
                start = str(range_data["start"]).strip().upper()
                end = str(range_data["end"]).strip().upper()
                generated = generate_option_code_range(group, start, end)
            except (KeyError, TypeError, ValueError, OptionCodeError) as exc:
                errors.append(f"Position {position}: {exc}")
                continue

            option_ranges.append({"group": group, "start": start, "end": end})
            option_codes.extend(generated)

        configuration["positions"][str(position)] = {
            "option_code_ranges": option_ranges,
            "option_codes": sort_option_codes(option_codes),
            "allowed_values_by_option_code": {},
        }

    return configuration, errors


def _parse_version(version: str) -> int | str:
    normalized = version.strip()
    if not normalized:
        return 1
    try:
        return int(normalized)
    except ValueError:
        return normalized
