from __future__ import annotations

from services.configuration_service import build_phase1_configuration
from services.configuration_validator import validate_configuration


def test_phase1_configuration_builds_json_shape_with_generated_codes() -> None:
    configuration, build_errors = build_phase1_configuration(
        product_type="30mp",
        description="30MP Product Configuration",
        configuration_date="2026-08-06",
        version="1",
        selected_positions=[10, 12],
        ranges_by_position={
            10: [{"group": 1, "start": "1", "end": "1C"}],
            12: [{"group": 4, "start": "4C", "end": "4E"}],
        },
    )

    assert build_errors == []
    assert validate_configuration(configuration, require_matrix=False) == []
    assert configuration["product_type"] == "30MP"
    assert configuration["structure"][0]["characteristic_key"] == "PRODUCT_TYPE"
    assert configuration["structure"][3]["specifications"][0]["catalog_value"] == "1"
    assert configuration["structure"][3]["specifications"][0]["label"] == "575-3-60"
    assert configuration["configured_positions"] == [10, 12]
    assert configuration["positions"]["10"]["option_codes"] == ["1", "1A", "1B", "1C"]
    assert configuration["positions"]["12"]["option_codes"] == ["4C", "4D", "4E"]
    assert configuration["positions"]["10"]["allowed_values_by_option_code"] == {}


def test_validation_requires_product_type_and_selected_position() -> None:
    configuration, build_errors = build_phase1_configuration(
        product_type="",
        description="",
        configuration_date="2026-08-06",
        version="1",
        selected_positions=[],
        ranges_by_position={},
    )

    errors = [*build_errors, *validate_configuration(configuration, require_matrix=False)]

    assert "Product type is required." in errors
    assert "Select at least one configurable position from 10 through 19." in errors


def test_validation_rejects_position_without_option_codes() -> None:
    configuration, build_errors = build_phase1_configuration(
        product_type="30MP",
        description="",
        configuration_date="2026-08-06",
        version="1",
        selected_positions=[10],
        ranges_by_position={10: []},
    )

    errors = [*build_errors, *validate_configuration(configuration, require_matrix=False)]

    assert "Position 10 must include at least one option-code range." in errors
    assert "Position 10 must generate at least one option code." in errors


def test_validation_rejects_bad_date_and_bad_row_values() -> None:
    configuration, build_errors = build_phase1_configuration(
        product_type="30MP",
        description="",
        configuration_date="08/06/2026",
        version="1",
        selected_positions=[10],
        ranges_by_position={10: [{"group": 1, "start": "1", "end": "1"}]},
    )
    configuration["positions"]["10"]["allowed_values_by_option_code"] = {"1": ["0", "?"]}

    errors = [*build_errors, *validate_configuration(configuration, require_matrix=True)]

    assert "Configuration date must use YYYY-MM-DD format." in errors
    assert "Position 10 option code 1 contains invalid row value '?'." in errors


def test_validation_requires_catalog_structure() -> None:
    configuration, build_errors = build_phase1_configuration(
        product_type="30MP",
        description="",
        configuration_date="2026-08-06",
        version="1",
        selected_positions=[10],
        ranges_by_position={10: [{"group": 1, "start": "1", "end": "1"}]},
    )
    configuration.pop("structure")

    errors = [*build_errors, *validate_configuration(configuration, require_matrix=False)]

    assert "Catalog structure must include at least one characteristic row." in errors


def test_validation_rejects_invalid_structure_range_and_used_flag() -> None:
    configuration, build_errors = build_phase1_configuration(
        product_type="30MP",
        description="",
        configuration_date="2026-08-06",
        version="1",
        selected_positions=[10],
        ranges_by_position={10: [{"group": 1, "start": "1", "end": "1"}]},
    )
    configuration["structure"] = [
        {
            "characteristic_key": "BAD KEY",
            "start_position": 4,
            "end_position": 1,
            "description": "",
            "used": True,
        },
        {
            "characteristic_key": "BAD KEY",
            "start_position": 5,
            "end_position": 5,
            "description": "",
            "used": "yes",
        },
    ]

    errors = [*build_errors, *validate_configuration(configuration, require_matrix=False)]

    assert any("key 'BAD KEY' is invalid" in error for error in errors)
    assert "Structure row 1 start position cannot come after end position." in errors
    assert "Structure row 2 used flag must be true or false." in errors


def test_validation_rejects_invalid_structure_specifications() -> None:
    configuration, build_errors = build_phase1_configuration(
        product_type="30MP",
        description="",
        configuration_date="2026-08-06",
        version="1",
        selected_positions=[10],
        ranges_by_position={10: [{"group": 1, "start": "1", "end": "1"}]},
    )
    configuration["structure"] = [
        {
            "characteristic_key": "VOLTAGE",
            "start_position": 9,
            "end_position": 9,
            "description": "",
            "used": True,
            "specifications": [
                {"catalog_value": "10", "label": "Too long", "description": "", "allowed": True},
                {"catalog_value": "?", "label": "Bad char", "description": "", "allowed": True},
                {"catalog_value": "6", "label": "", "description": "", "allowed": "yes"},
            ],
        }
    ]

    errors = [*build_errors, *validate_configuration(configuration, require_matrix=False)]

    assert "Structure row 1 specification 1 value '10' must be 1 character(s)." in errors
    assert "Structure row 1 specification 2 catalog value '?' is invalid." in errors
    assert "Structure row 1 specification 3 must include a label." in errors
    assert "Structure row 1 specification 3 allowed flag must be true or false." in errors


def test_full_validation_requires_at_least_one_matrix_selection() -> None:
    configuration, build_errors = build_phase1_configuration(
        product_type="30MP",
        description="",
        configuration_date="2026-08-06",
        version="1",
        selected_positions=[10],
        ranges_by_position={10: [{"group": 1, "start": "1", "end": "1"}]},
    )

    errors = [*build_errors, *validate_configuration(configuration, require_matrix=True)]

    assert "Position 10 cannot be saved because no valid characters have been selected." in errors


def test_hyphen_is_a_valid_matrix_character() -> None:
    configuration, build_errors = build_phase1_configuration(
        product_type="30MP",
        description="Hyphen matrix",
        configuration_date="2026-08-17",
        version="1",
        selected_positions=[10],
        ranges_by_position={10: [{"group": 5, "start": "5B", "end": "5B"}]},
    )
    configuration["positions"]["10"]["allowed_values_by_option_code"] = {"5B": ["-"]}

    assert build_errors == []
    assert validate_configuration(configuration, require_matrix=True) == []


def test_position_exclusions_are_valid_and_cannot_also_be_selected() -> None:
    configuration, build_errors = build_phase1_configuration(
        product_type="30MP",
        description="Position exclusions",
        configuration_date="2026-08-17",
        version="1",
        selected_positions=[10],
        ranges_by_position={10: [{"group": 5, "start": "5B", "end": "5B"}]},
    )
    position = configuration["positions"]["10"]
    position["excluded_characters"] = ["-", "A"]
    position["allowed_values_by_option_code"] = {"5B": ["0", "A"]}

    errors = [*build_errors, *validate_configuration(configuration, require_matrix=True)]

    assert "Position 10 option code 5B cannot select excluded character 'A'." in errors


def test_position_exclusions_reject_invalid_and_duplicate_characters() -> None:
    configuration, build_errors = build_phase1_configuration(
        product_type="30MP",
        description="Position exclusions",
        configuration_date="2026-08-17",
        version="1",
        selected_positions=[10],
        ranges_by_position={10: [{"group": 5, "start": "5B", "end": "5B"}]},
    )
    position = configuration["positions"]["10"]
    position["excluded_characters"] = ["A", "A", "?"]
    position["allowed_values_by_option_code"] = {"5B": ["0"]}

    errors = [*build_errors, *validate_configuration(configuration, require_matrix=True)]

    assert "Position 10 contains duplicate excluded character 'A'." in errors
    assert "Position 10 contains invalid excluded character '?'." in errors


def test_validation_rejects_option_codes_that_do_not_match_ranges() -> None:
    configuration, build_errors = build_phase1_configuration(
        product_type="30MP",
        description="",
        configuration_date="2026-08-06",
        version="1",
        selected_positions=[10],
        ranges_by_position={10: [{"group": 1, "start": "1", "end": "1A"}]},
    )
    configuration["positions"]["10"]["option_codes"] = ["1", "1B"]
    configuration["positions"]["10"]["allowed_values_by_option_code"] = {"1": ["0"]}

    errors = [*build_errors, *validate_configuration(configuration, require_matrix=True)]

    assert "Position 10 option-code columns do not match the selected ranges." in errors


def test_build_reports_reversed_range_with_position_context() -> None:
    configuration, build_errors = build_phase1_configuration(
        product_type="30MP",
        description="",
        configuration_date="2026-08-06",
        version="1",
        selected_positions=[10],
        ranges_by_position={10: [{"group": 1, "start": "1M", "end": "1C"}]},
    )

    errors = [*build_errors, *validate_configuration(configuration, require_matrix=False)]

    assert any("Position 10" in error and "cannot come after" in error for error in errors)


def test_conditional_price_rules_accept_enabled_position_list() -> None:
    configuration, build_errors = build_phase1_configuration(
        product_type="30MP",
        description="Test",
        configuration_date="2026-08-17",
        version="1",
        selected_positions=[10],
        ranges_by_position={10: [{"group": 1, "start": "1", "end": "1"}]},
    )
    configuration["conditional_price_rules"] = {"enabled": True, "positions": [14]}

    errors = [*build_errors, *validate_configuration(configuration, require_matrix=False)]

    assert errors == []


def test_conditional_price_rules_require_positions_when_enabled() -> None:
    configuration, build_errors = build_phase1_configuration(
        product_type="30MP",
        description="Test",
        configuration_date="2026-08-17",
        version="1",
        selected_positions=[10],
        ranges_by_position={10: [{"group": 1, "start": "1", "end": "1"}]},
    )
    configuration["conditional_price_rules"] = {"enabled": True, "positions": []}

    errors = [*build_errors, *validate_configuration(configuration, require_matrix=False)]

    assert "Conditional price rules are enabled, but no positions were selected." in errors
