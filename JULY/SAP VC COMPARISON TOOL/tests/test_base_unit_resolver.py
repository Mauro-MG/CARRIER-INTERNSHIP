from __future__ import annotations

from services.base_unit_resolver import resolve_base_unit_search, validate_base_unit_rule


def test_range_search_resolves_one_based_inclusive_positions() -> None:
    result = resolve_base_unit_search(
        "30MPW0171ABCDE",
        {"enabled": True, "search_type": "range", "start_position": 1, "end_position": 9},
    )

    assert result.success is True
    assert result.search_value == "30MPW0171"


def test_full_search_resolves_template_exactly() -> None:
    result = resolve_base_unit_search(
        "65LL-1002PM-3GG41",
        {"enabled": True, "search_type": "full_search", "template": "{1:4}-{6:10}--{13}---0"},
    )

    assert result.success is True
    assert result.search_value == "65LL-1002P--3---0"


def test_full_search_supports_single_position_ranges_literals_and_final_position() -> None:
    result = resolve_base_unit_search(
        "ABCDE9",
        {"enabled": True, "search_type": "full_search", "template": "{1}-{2:4}-0-{6}"},
    )

    assert result.success is True
    assert result.search_value == "A-BCD-0-9"


def test_disabled_rule_is_controlled_failure() -> None:
    result = resolve_base_unit_search("30MPW0171ABCDE", {"enabled": False})

    assert result.success is False
    assert result.search_value is None


def test_missing_rule_is_controlled_failure() -> None:
    result = resolve_base_unit_search("30MPW0171ABCDE", None)

    assert result.success is False
    assert result.search_value is None


def test_range_rejects_invalid_zero_position() -> None:
    errors = validate_base_unit_rule({"enabled": True, "search_type": "range", "start_position": 0, "end_position": 9})

    assert errors


def test_range_rejects_reversed_position() -> None:
    errors = validate_base_unit_rule({"enabled": True, "search_type": "range", "start_position": 9, "end_position": 1})

    assert errors


def test_template_rejects_invalid_zero_position() -> None:
    errors = validate_base_unit_rule({"enabled": True, "search_type": "full_search", "template": "{0:4}"})

    assert errors


def test_template_rejects_reversed_range() -> None:
    errors = validate_base_unit_rule({"enabled": True, "search_type": "full_search", "template": "{10:4}"})

    assert errors


def test_template_rejects_malformed_placeholder() -> None:
    errors = validate_base_unit_rule({"enabled": True, "search_type": "full_search", "template": "{ABC}"})

    assert errors


def test_template_rejects_requested_position_beyond_source_length_at_resolution_time() -> None:
    result = resolve_base_unit_search(
        "ABCDE",
        {"enabled": True, "search_type": "full_search", "template": "{1:6}"},
    )

    assert result.success is False
    assert "position 6" in (result.error or "")
