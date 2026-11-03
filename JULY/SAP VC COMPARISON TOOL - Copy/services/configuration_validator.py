from __future__ import annotations

import re
from datetime import date
from typing import Any

from services.base_unit_resolver import validate_base_unit_rule
from services.option_code_generator import OptionCodeError, parse_option_code
from services.option_code_generator import generate_option_code_range, sort_option_codes
from services.search_token_resolver import CHARACTER_BASED, CODE_BASED, VALID_SEARCH_MODES, get_search_mode
from services.search_token_resolver import option_positions_for_character_mode


VALID_POSITIONS = set(range(10, 20))
MATRIX_ROW_VALUES = tuple("-0123456789ABCDEFGHIJKLMNOPQRSTUVWXYZ")
CHARACTERISTIC_KEY_PATTERN = re.compile(r"^[A-Z][A-Z0-9_]*$")


def validate_configuration(configuration: dict[str, Any], *, require_matrix: bool = False) -> list[str]:
    """Validate a product configuration draft or completed configuration."""
    errors: list[str] = []

    product_type = str(configuration.get("product_type", "")).strip()
    if not product_type:
        errors.append("Product type is required.")

    search_mode = get_search_mode(configuration)
    if search_mode not in VALID_SEARCH_MODES:
        errors.append("Search mode must be code_based or character_based.")
        search_mode = CODE_BASED

    configuration_date = str(configuration.get("configuration_date", "")).strip()
    try:
        date.fromisoformat(configuration_date)
    except ValueError:
        errors.append("Configuration date must use YYYY-MM-DD format.")

    _validate_structure(configuration.get("structure"), errors)
    _validate_option_positions(configuration.get("option_positions"), errors)
    _validate_conditional_price_rules(configuration.get("conditional_price_rules"), errors)
    errors.extend(validate_base_unit_rule(configuration.get("base_unit_price_rule")))

    if search_mode == CHARACTER_BASED:
        option_positions = option_positions_for_character_mode(configuration)
        if not option_positions:
            errors.append("Character-based configurations must define option positions in option_positions or an OPTIONS structure row.")
        return errors

    configured_positions = configuration.get("configured_positions")
    if not isinstance(configured_positions, list) or not configured_positions:
        errors.append("Select at least one configurable position from 10 through 19.")
        configured_positions = []

    normalized_positions: list[int] = []
    for raw_position in configured_positions:
        try:
            position = int(raw_position)
        except (TypeError, ValueError):
            errors.append(f"Invalid position {raw_position!r}; positions must be between 10 and 19.")
            continue
        if position not in VALID_POSITIONS:
            errors.append(f"Position {position} is invalid; positions must be between 10 and 19.")
            continue
        normalized_positions.append(position)

    if len(normalized_positions) != len(set(normalized_positions)):
        errors.append("Configured positions cannot contain duplicates.")

    positions = configuration.get("positions", {})
    if not isinstance(positions, dict):
        errors.append("Positions must be stored as an object keyed by position number.")
        positions = {}

    for position in normalized_positions:
        position_key = str(position)
        position_data = positions.get(position_key)
        if not isinstance(position_data, dict):
            errors.append(f"Position {position} is missing its configuration details.")
            continue
        _validate_position(position, position_data, errors, require_matrix=require_matrix)

    return errors


def _validate_structure(structure: Any, errors: list[str]) -> None:
    if structure is None:
        errors.append("Catalog structure must include at least one characteristic row.")
        return
    if not isinstance(structure, list) or not structure:
        errors.append("Catalog structure must include at least one characteristic row.")
        return

    seen_keys: set[str] = set()
    for index, item in enumerate(structure, start=1):
        if not isinstance(item, dict):
            errors.append(f"Structure row {index} must be an object.")
            continue

        key = str(item.get("characteristic_key", "")).strip().upper()
        if not key:
            errors.append(f"Structure row {index} must include a characteristic key.")
        elif not CHARACTERISTIC_KEY_PATTERN.fullmatch(key):
            errors.append(
                f"Structure row {index} key {key!r} is invalid; use letters, numbers, and underscores, starting with a letter."
            )
        elif key in seen_keys:
            errors.append(f"Structure row {index} duplicates characteristic key {key}.")
        else:
            seen_keys.add(key)

        try:
            start_position = int(item.get("start_position"))
            end_position = int(item.get("end_position"))
        except (TypeError, ValueError):
            errors.append(f"Structure row {index} must include numeric start and end positions.")
            continue

        if start_position < 1 or end_position < 1:
            errors.append(f"Structure row {index} positions must be 1 or greater.")
        if start_position > end_position:
            errors.append(f"Structure row {index} start position cannot come after end position.")

        if "used" in item and not isinstance(item.get("used"), bool):
            errors.append(f"Structure row {index} used flag must be true or false.")

        _validate_structure_specifications(index, item, errors)


def _validate_structure_specifications(row_index: int, item: dict[str, Any], errors: list[str]) -> None:
    specifications = item.get("specifications", [])
    if specifications is None:
        return
    if not isinstance(specifications, list):
        errors.append(f"Structure row {row_index} specifications must be a list.")
        return

    try:
        expected_length = int(item.get("end_position")) - int(item.get("start_position")) + 1
    except (TypeError, ValueError):
        expected_length = None

    seen_values: set[str] = set()
    for spec_index, spec in enumerate(specifications, start=1):
        if not isinstance(spec, dict):
            errors.append(f"Structure row {row_index} specification {spec_index} must be an object.")
            continue

        catalog_value = str(spec.get("catalog_value", "")).strip().upper()
        if not catalog_value:
            errors.append(f"Structure row {row_index} specification {spec_index} must include a catalog value.")
        elif not re.fullmatch(r"[A-Z0-9_-]+", catalog_value):
            errors.append(
                f"Structure row {row_index} specification {spec_index} catalog value {catalog_value!r} is invalid."
            )
        elif expected_length is not None and len(catalog_value) != expected_length:
            errors.append(
                f"Structure row {row_index} specification {spec_index} value {catalog_value!r} must be {expected_length} character(s)."
            )
        elif catalog_value in seen_values:
            errors.append(f"Structure row {row_index} specification {spec_index} duplicates value {catalog_value}.")
        else:
            seen_values.add(catalog_value)

        label = str(spec.get("label", "")).strip()
        if not label:
            errors.append(f"Structure row {row_index} specification {spec_index} must include a label.")

        if "allowed" in spec and not isinstance(spec.get("allowed"), bool):
            errors.append(f"Structure row {row_index} specification {spec_index} allowed flag must be true or false.")


def _validate_option_positions(option_positions: Any, errors: list[str]) -> None:
    if option_positions is None:
        return
    if not isinstance(option_positions, dict):
        errors.append("Available DOCX search positions must be stored as an object with start and end values.")
        return
    try:
        start_position = int(option_positions.get("start"))
        end_position = int(option_positions.get("end"))
    except (TypeError, ValueError):
        errors.append("Available DOCX search positions must include numeric start and end values.")
        return
    if start_position < 1 or end_position < 1:
        errors.append("Available DOCX search positions must be 1 or greater.")
    if start_position > end_position:
        errors.append("Available DOCX search position start cannot come after end.")


def _validate_conditional_price_rules(rules: Any, errors: list[str]) -> None:
    if rules is None:
        return
    if not isinstance(rules, dict):
        errors.append("Conditional price rules must be stored as an object.")
        return
    if not rules.get("enabled"):
        return

    raw_positions = rules.get("positions", [])
    if isinstance(raw_positions, dict):
        iterable_positions = [position for position, enabled in raw_positions.items() if enabled]
    elif isinstance(raw_positions, list):
        iterable_positions = raw_positions
    else:
        errors.append("Conditional price rule positions must be a list of catalog positions.")
        return

    if not iterable_positions:
        errors.append("Conditional price rules are enabled, but no positions were selected.")
        return

    seen_positions: set[int] = set()
    for raw_position in iterable_positions:
        try:
            position = int(raw_position)
        except (TypeError, ValueError):
            errors.append(f"Conditional price rule position {raw_position!r} must be numeric.")
            continue
        if position < 1:
            errors.append("Conditional price rule positions must be 1 or greater.")
        elif position in seen_positions:
            errors.append(f"Conditional price rule position {position} is duplicated.")
        else:
            seen_positions.add(position)


def _validate_position(
    position: int,
    position_data: dict[str, Any],
    errors: list[str],
    *,
    require_matrix: bool,
) -> None:
    expected_option_codes: list[str] = []
    option_ranges = position_data.get("option_code_ranges")
    if not isinstance(option_ranges, list) or not option_ranges:
        errors.append(f"Position {position} must include at least one option-code range.")
    else:
        for index, range_data in enumerate(option_ranges, start=1):
            _validate_range(position, index, range_data, errors)
            if isinstance(range_data, dict):
                try:
                    expected_option_codes.extend(
                        generate_option_code_range(
                            int(range_data.get("group")),
                            str(range_data.get("start", "")).strip().upper(),
                            str(range_data.get("end", "")).strip().upper(),
                        )
                    )
                except (TypeError, ValueError, OptionCodeError):
                    pass

    option_codes = position_data.get("option_codes")
    if not isinstance(option_codes, list) or not option_codes:
        errors.append(f"Position {position} must generate at least one option code.")
        option_codes = []
    else:
        normalized_codes: list[str] = []
        for code in option_codes:
            try:
                parse_option_code(str(code))
                normalized_codes.append(str(code).strip().upper())
            except OptionCodeError:
                errors.append(f"Position {position} contains invalid option code {code!r}.")
        if len(normalized_codes) != len(set(normalized_codes)):
            errors.append(f"Position {position} generated duplicate option codes.")
        expected_sorted_codes = sort_option_codes(list(dict.fromkeys(expected_option_codes)))
        if expected_sorted_codes and normalized_codes != expected_sorted_codes:
            errors.append(f"Position {position} option-code columns do not match the selected ranges.")

    allowed_values = position_data.get("allowed_values_by_option_code", {})
    if allowed_values is None:
        allowed_values = {}
    if not isinstance(allowed_values, dict):
        errors.append(f"Position {position} matrix selections must be stored as an object.")
        return

    excluded_characters = position_data.get("excluded_characters", [])
    if excluded_characters is None:
        excluded_characters = []
    if not isinstance(excluded_characters, list):
        errors.append(f"Position {position} excluded characters must be stored as a list.")
        excluded_characters = []
    valid_excluded_characters: set[str] = set()
    for character in excluded_characters:
        if character not in MATRIX_ROW_VALUES:
            errors.append(f"Position {position} contains invalid excluded character {character!r}.")
        elif character in valid_excluded_characters:
            errors.append(f"Position {position} contains duplicate excluded character {character!r}.")
        else:
            valid_excluded_characters.add(character)

    selected_cells = 0
    for option_code, row_values in allowed_values.items():
        normalized_option_code = str(option_code).strip().upper()
        if option_codes and normalized_option_code not in [str(code).strip().upper() for code in option_codes]:
            errors.append(f"Position {position} has selections for unknown option code {option_code}.")
        if not isinstance(row_values, list):
            errors.append(f"Position {position} option code {option_code} must store row values as a list.")
            continue
        for row_value in row_values:
            if row_value not in MATRIX_ROW_VALUES:
                errors.append(f"Position {position} option code {option_code} contains invalid row value {row_value!r}.")
            elif row_value in valid_excluded_characters:
                errors.append(
                    f"Position {position} option code {option_code} cannot select excluded character {row_value!r}."
                )
            else:
                selected_cells += 1

    if require_matrix and selected_cells == 0:
        errors.append(f"Position {position} cannot be saved because no valid characters have been selected.")


def _validate_range(position: int, index: int, range_data: Any, errors: list[str]) -> None:
    if not isinstance(range_data, dict):
        errors.append(f"Position {position} range {index} must be an object.")
        return

    try:
        group = int(range_data.get("group"))
    except (TypeError, ValueError):
        errors.append(f"Position {position} range {index} must include a numeric group from 1 through 20.")
        return

    start = str(range_data.get("start", "")).strip().upper()
    end = str(range_data.get("end", "")).strip().upper()
    try:
        start_group, start_letter = parse_option_code(start)
        end_group, end_letter = parse_option_code(end)
    except OptionCodeError as exc:
        errors.append(f"Position {position} range {index}: {exc}")
        return

    if group < 1 or group > 20:
        errors.append(f"Position {position} range {index} group must be between 1 and 20.")
    if start_group != group or end_group != group:
        errors.append(f"Position {position} range {index} must stay inside option-code group {group}.")

    start_order = 0 if start_letter is None else ord(start_letter) - ord("A") + 1
    end_order = 0 if end_letter is None else ord(end_letter) - ord("A") + 1
    if start_order > end_order:
        errors.append(f"Position {position} range {index} start cannot come after its end.")
