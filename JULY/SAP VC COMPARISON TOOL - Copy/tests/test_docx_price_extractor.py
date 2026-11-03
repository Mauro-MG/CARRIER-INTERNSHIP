from __future__ import annotations

import zipfile
from decimal import Decimal
from pathlib import Path

from services.docx_price_extractor import (
    AMBIGUOUS_BASE_UNIT_MATCH,
    BASE_UNIT_NOT_FOUND,
    BASE_UNIT_PRICED,
    CHARACTER_NOT_FOUND,
    CODE_NOT_FOUND,
    CONDENSER_MISMATCH,
    STANDARD_OPTION,
    STRUCTURE_MISMATCH,
    decode_catalog_positions,
    extract_catalog_prices,
    extract_position_tables,
)
from services.sap_price_comparator import build_document_comparison_records


DOCX_PATH = Path("test_docx_price_extractor.docx")


def teardown_function() -> None:
    DOCX_PATH.unlink(missing_ok=True)


def test_extracts_same_position_docx_table_price_by_size_column() -> None:
    _write_docx(
        [
            ("p", "POSITION 10"),
            (
                "tbl",
                [
                    ["DESCRIPTION", "MASTER PRICE"],
                    ["", "017-033", "041-046"],
                    ["Height adjustment kit 2A", "30MP_SM_LEVEL_001\n2,040", "30MP_SM_LEVEL_002\n9,999"],
                ],
            ),
        ]
    )

    result = extract_catalog_prices(DOCX_PATH, "30MPW0315A", _configuration([10], {10: {"2A": ["A"]}}))

    assert result.priced_options[0].catalog_code == "2A"
    assert result.priced_options[0].price == Decimal("2040")
    assert result.priced_options[0].location.startswith("Table")


def test_extracts_voltage_specific_row() -> None:
    _write_docx(
        [
            ("p", "POSITION 14"),
            (
                "tbl",
                [
                    ["DESCRIPTION", "VOLTAGE", "MASTER PRICE"],
                    ["", "", "017", "021", "031"],
                    ["Fused Disconnect 5B", "575-3-60\n460-3-60", "3,404", "3,404", "3,404"],
                    ["", "208/230-3-60", "3,404", "3,404", "3,977"],
                ],
            ),
        ]
    )

    result = extract_catalog_prices(DOCX_PATH, "30MPW03155AAA5", _configuration([14], {14: {"5B": ["5"]}}))

    assert result.priced_options[0].catalog_code == "5B"
    assert result.priced_options[0].price == Decimal("3977")


def test_standard_and_dash_values_are_diagnostics_not_prices() -> None:
    _write_docx(
        [
            ("p", "POSITION 10"),
            (
                "tbl",
                [
                    ["DESCRIPTION", "MASTER PRICE"],
                    ["", "017-033", "041-046"],
                    ["No options (Std) 2", "Std.", "Std."],
                    ["Unavailable option 3A", "-", "-"],
                ],
            ),
        ]
    )

    result = extract_catalog_prices(DOCX_PATH, "30MPW0315A", _configuration([10], {10: {"2": ["A"], "3A": ["A"]}}))

    assert result.priced_options == []
    assert [diagnostic.status for diagnostic in result.diagnostics] == [STANDARD_OPTION, STANDARD_OPTION]


def test_structure_mismatch_is_reported() -> None:
    _write_docx(
        [
            ("p", "POSITION 16"),
            (
                "tbl",
                [
                    ["DESCRIPTION", "MASTER PRICE"],
                    ["", "017-031", "033"],
                    ["Export Crate (30MPA) 8B", "3,935", "3,935"],
                ],
            ),
        ]
    )

    result = extract_catalog_prices(DOCX_PATH, "30MPW0315AAAAAAB", _configuration([16], {16: {"8B": ["B"]}}))

    assert result.priced_options == []
    assert result.diagnostics[0].status == STRUCTURE_MISMATCH


def test_code_not_found() -> None:
    _write_docx(
        [
            ("p", "POSITION 10"),
            ("tbl", [["DESCRIPTION", "MASTER PRICE"], ["", "017-033"], ["Other 1", "1,000"]]),
        ]
    )

    result = extract_catalog_prices(DOCX_PATH, "30MPW0315A", _configuration([10], {10: {"2A": ["A"]}}))

    assert result.priced_options == []
    assert result.diagnostics[0].status == CODE_NOT_FOUND


def test_decode_catalog_positions_uses_x_axis_option_codes() -> None:
    decoded = decode_catalog_positions("30MPW0315AG", _configuration([10, 11], {10: {"2A": ["A"]}, 11: {"4A": ["G"]}}))

    assert [(item.position, item.position_value, item.catalog_code) for item in decoded] == [
        ("10", "A", "2A"),
        ("11", "G", "4A"),
    ]


def test_decode_catalog_positions_maps_hyphen_character() -> None:
    decoded = decode_catalog_positions("30MPW0315-", _configuration([10], {10: {"5B": ["-"]}}))

    assert [(item.position, item.position_value, item.catalog_code) for item in decoded] == [
        ("10", "-", "5B"),
    ]


def test_real_30mp_docx_smoke_when_available() -> None:
    real_docx = Path("30MP_SM-PPG-Test.docx")
    if not real_docx.exists():
        return

    result = extract_catalog_prices(real_docx, "30MPW03153AG557B", _real_30mp_configuration())

    extracted = {(item.position, item.catalog_code, item.price) for item in result.priced_options}
    assert ("10", "2A", Decimal("2040")) in extracted
    assert ("13", "3B", Decimal("5101")) in extracted
    assert ("14", "5B", Decimal("3977")) in extracted
    assert ("15", "4A", Decimal("3020")) in extracted
    assert any(diagnostic.status == STRUCTURE_MISMATCH and diagnostic.catalog_code == "8B" for diagnostic in result.diagnostics)


def test_extract_position_tables_reads_docx_xml_tables() -> None:
    _write_docx(
        [
            ("p", "POSITION 15"),
            ("tbl", [["DESCRIPTION", "MASTER PRICE"], ["Controls 4A", "3,020"]]),
        ]
    )

    tables = extract_position_tables(DOCX_PATH)

    assert len(tables) == 1
    assert tables[0].position == "15"
    assert tables[0].rows[1].raw_cells == ["Controls 4A", "3,020"]


def test_extracts_base_unit_price_with_range_rule() -> None:
    _write_docx(
        [
            ("p", "BASE UNIT PRICES"),
            (
                "tbl",
                [
                    ["ORDERING NUMBER", "POWER SUPPLY", "MASTER PRICE"],
                    ["30MPW0171", "460-3-60", "123,456"],
                    ["65LL-1002P--3---0", "380-3-60", "279,862"],
                ],
            ),
        ]
    )
    configuration = _configuration([], {})
    configuration["base_unit_price_rule"] = {
        "enabled": True,
        "search_type": "range",
        "start_position": 1,
        "end_position": 9,
    }

    result = extract_catalog_prices(DOCX_PATH, "30MPW0171ABCDE", configuration)

    assert result.base_unit_result is not None
    assert result.base_unit_result.status == BASE_UNIT_PRICED
    assert result.base_unit_result.search_value == "30MPW0171"
    assert result.base_unit_result.price == Decimal("123456")


def test_extracts_base_unit_price_with_full_search_template() -> None:
    _write_docx(
        [
            ("p", "BASE UNIT PRICES"),
            (
                "tbl",
                [
                    ["ORDERING NUMBER", "POWER SUPPLY", "MASTER PRICE"],
                    ["30MPW0171", "460-3-60", "123,456"],
                    ["65LL-1002P--3---0", "380-3-60", "279,862"],
                ],
            ),
        ]
    )
    configuration = _configuration([], {})
    configuration["base_unit_price_rule"] = {
        "enabled": True,
        "search_type": "full_search",
        "template": "{1:4}-{6:10}--{13}---0",
    }

    result = extract_catalog_prices(DOCX_PATH, "65LL-1002PM-3GG41", configuration)

    assert result.base_unit_result is not None
    assert result.base_unit_result.status == BASE_UNIT_PRICED
    assert result.base_unit_result.search_value == "65LL-1002P--3---0"
    assert result.base_unit_result.price == Decimal("279862")


def test_base_unit_extraction_does_not_select_voltage_as_price() -> None:
    _write_docx(
        [
            ("p", "BASE UNIT PRICES"),
            (
                "tbl",
                [
                    ["ORDERING NUMBER", "POWER SUPPLY", "MASTER PRICE"],
                    ["65LL-1002P--3---0", "380-3-60", "279,862"],
                ],
            ),
        ]
    )
    configuration = _configuration([], {})
    configuration["base_unit_price_rule"] = {
        "enabled": True,
        "search_type": "full_search",
        "template": "{1:4}-{6:10}--{13}---0",
    }

    result = extract_catalog_prices(DOCX_PATH, "65LL-1002PM-3GG41", configuration)

    assert result.base_unit_result is not None
    assert result.base_unit_result.price == Decimal("279862")
    assert result.base_unit_result.raw_value != "380-3-60"


def test_base_unit_extraction_prefers_last_table_column_for_price() -> None:
    _write_docx(
        [
            ("p", "BASE UNIT PRICES"),
            (
                "tbl",
                [
                    ["ORDERING NUMBER", "POWER SUPPLY", "MASTER PRICE", "PRICE"],
                    ["30MPW0171", "460-3-60", "1", "123,456"],
                ],
            ),
        ]
    )
    configuration = _configuration([], {})
    configuration["base_unit_price_rule"] = {
        "enabled": True,
        "search_type": "range",
        "start_position": 1,
        "end_position": 9,
    }

    result = extract_catalog_prices(DOCX_PATH, "30MPW0171ABCDE", configuration)

    assert result.base_unit_result is not None
    assert result.base_unit_result.price == Decimal("123456")
    assert result.base_unit_result.raw_value == "123,456"


def test_base_unit_not_found_does_not_block_option_extraction() -> None:
    _write_docx(
        [
            ("p", "POSITION 10"),
            (
                "tbl",
                [
                    ["DESCRIPTION", "MASTER PRICE"],
                    ["", "017-033"],
                    ["Low Sound 1", "$1,250.00"],
                ],
            ),
        ]
    )
    configuration = _configuration([10], {10: {"1": ["A"]}})
    configuration["base_unit_price_rule"] = {
        "enabled": True,
        "search_type": "range",
        "start_position": 1,
        "end_position": 9,
    }

    result = extract_catalog_prices(DOCX_PATH, "30MPW0315A", configuration)

    assert result.base_unit_result is not None
    assert result.base_unit_result.status == BASE_UNIT_NOT_FOUND
    assert result.priced_options[0].price == Decimal("1250.00")


def test_conflicting_base_unit_prices_are_ambiguous() -> None:
    _write_docx(
        [
            ("p", "BASE UNIT PRICES"),
            (
                "tbl",
                [
                    ["ORDERING NUMBER", "POWER SUPPLY", "MASTER PRICE"],
                    ["30MPW0171", "460-3-60", "123,456"],
                ],
            ),
            ("p", "BASE UNIT PRICES COPY"),
            (
                "tbl",
                [
                    ["MODEL NUMBER", "POWER SUPPLY", "MASTER PRICE"],
                    ["30MPW0171", "460-3-60", "123,999"],
                ],
            ),
        ]
    )
    configuration = _configuration([], {})
    configuration["base_unit_price_rule"] = {
        "enabled": True,
        "search_type": "range",
        "start_position": 1,
        "end_position": 9,
    }

    result = extract_catalog_prices(DOCX_PATH, "30MPW0171ABCDE", configuration)

    assert result.base_unit_result is not None
    assert result.base_unit_result.status == AMBIGUOUS_BASE_UNIT_MATCH
    assert len(result.base_unit_result.matches) == 2


def test_condenser_compatibility_selects_mpw_q_row_for_mpw_and_mpq_and_mpa_row_for_mpa() -> None:
    _write_docx(
        [
            ("p", "POSITION 14"),
            (
                "tbl",
                [
                    ["DESCRIPTION", "CONDENSER", "MASTER PRICE"],
                    ["", "", "031"],
                    ["Option A 5B", "MPW/Q", "1,250"],
                    ["Option A 5B", "MPA", "1,500"],
                ],
            ),
        ]
    )
    configuration = _configuration([14], {14: {"5B": ["A"]}})

    mpw = extract_catalog_prices(DOCX_PATH, "30MPW03100000A", configuration)
    mpq = extract_catalog_prices(DOCX_PATH, "30MPQ03100000A", configuration)
    mpa = extract_catalog_prices(DOCX_PATH, "30MPA03100000A", configuration)

    assert mpw.priced_options[0].price == Decimal("1250")
    assert mpw.priced_options[0].product_family == "MPW"
    assert mpw.priced_options[0].document_condenser_compatibility == "MPW/Q"
    assert mpw.priced_options[0].normalized_condenser_families == ["MPQ", "MPW"]
    assert mpq.priced_options[0].price == Decimal("1250")
    assert mpq.priced_options[0].product_family == "MPQ"
    assert mpa.priced_options[0].price == Decimal("1500")
    assert mpa.priced_options[0].product_family == "MPA"


def test_combined_condenser_compatibility_applies_to_all_families() -> None:
    _write_docx(
        [
            ("p", "POSITION 14"),
            (
                "tbl",
                [
                    ["DESCRIPTION", "CONDENSER", "MASTER PRICE"],
                    ["", "", "031"],
                    ["Option B 6C", "MPW/Q OR MPA", "2,000"],
                ],
            ),
        ]
    )
    configuration = _configuration([14], {14: {"6C": ["A"]}})

    for catalog in ["30MPW03100000A", "30MPQ03100000A", "30MPA03100000A"]:
        result = extract_catalog_prices(DOCX_PATH, catalog, configuration)
        assert result.priced_options[0].price == Decimal("2000")


def test_condenser_mismatch_is_reported_instead_of_code_not_found() -> None:
    _write_docx(
        [
            ("p", "POSITION 14"),
            (
                "tbl",
                [
                    ["DESCRIPTION", "CONDENSER", "MASTER PRICE"],
                    ["", "", "031"],
                    ["Option C 7D", "MPW/Q", "3,000"],
                ],
            ),
        ]
    )
    configuration = _configuration([14], {14: {"7D": ["A"]}})

    result = extract_catalog_prices(DOCX_PATH, "30MPA03100000A", configuration)

    assert result.priced_options == []
    assert result.diagnostics[0].status == CONDENSER_MISMATCH
    assert "MPW, MPQ" in result.diagnostics[0].reason
    assert result.diagnostics[0].product_family == "MPA"
    assert result.diagnostics[0].document_condenser_compatibility == "MPW/Q"


def test_multiple_compatible_components_for_same_option_code_are_preserved() -> None:
    _write_docx(
        [
            ("p", "POSITION 14"),
            (
                "tbl",
                [
                    ["DESCRIPTION", "CONDENSER", "MASTER PRICE"],
                    ["", "", "031"],
                    ["Component 1 5B", "MPW/Q", "1,250"],
                    ["Component 2 5B", "MPW/Q", "2,500"],
                ],
            ),
        ]
    )
    configuration = _configuration([14], {14: {"5B": ["A"]}})

    result = extract_catalog_prices(DOCX_PATH, "30MPW03100000A", configuration)

    assert [option.price for option in result.priced_options] == [Decimal("1250"), Decimal("2500")]


def test_option_code_matching_does_not_use_unsafe_substrings() -> None:
    _write_docx(
        [
            ("p", "POSITION 14"),
            (
                "tbl",
                [
                    ["DESCRIPTION", "CONDENSER", "MASTER PRICE"],
                    ["", "", "031"],
                    ["Wrong option 11A", "MPW/Q", "9,999"],
                    ["Correct option 1A", "MPW/Q", "1,250"],
                ],
            ),
        ]
    )
    configuration = _configuration([14], {14: {"1A": ["A"]}})

    result = extract_catalog_prices(DOCX_PATH, "30MPW03100000A", configuration)

    assert [option.price for option in result.priced_options] == [Decimal("1250")]


def test_character_based_position_table_searches_character_directly() -> None:
    _write_docx(
        [
            ("p", "POSITION 14"),
            (
                "tbl",
                [
                    ["DESCRIPTION", "CODE", "MASTER PRICE"],
                    ["", "", "031"],
                    ["No Disconnect", "-", "Std."],
                    ["Fused Disconnect", "5", "6,500"],
                    ["Wrong 5B row", "5B", "9,999"],
                    ["Disconnect + Transformer", "A", "7,200"],
                ],
            ),
        ]
    )

    result_5 = extract_catalog_prices(DOCX_PATH, "30MPW031000005", _character_configuration(14, 14))
    result_a = extract_catalog_prices(DOCX_PATH, "30MPW03100000A", _character_configuration(14, 14))

    assert result_5.priced_options[0].catalog_character == "5"
    assert result_5.priced_options[0].catalog_code == "5"
    assert result_5.priced_options[0].price == Decimal("6500")
    assert result_5.priced_options[0].search_mode == "character_based"
    assert result_a.priced_options[0].catalog_character == "A"
    assert result_a.priced_options[0].catalog_code == "A"
    assert result_a.priced_options[0].price == Decimal("7200")


def test_character_based_table_with_digit_order_code_header_does_not_need_description_column() -> None:
    _write_docx(
        [
            ("p", "POSITION 14"),
            (
                "tbl",
                [
                    ["Position 14 ELECTRICAL OPTIONS"],
                    ["14th DIGIT ORDER CODE", "POWER CONNECTION", "MASTER PRICE"],
                    ["", "", "031"],
                    ["5", "Single point", "6,500"],
                ],
            ),
        ]
    )

    result = extract_catalog_prices(DOCX_PATH, "30MPW031000005", _character_configuration(14, 14))

    assert result.priced_options[0].catalog_code == "5"
    assert result.priced_options[0].price == Decimal("6500")


def test_option_extraction_prefers_last_table_column_for_single_price_tables() -> None:
    _write_docx(
        [
            ("p", "POSITION 14"),
            (
                "tbl",
                [
                    ["DESCRIPTION", "CODE", "MASTER PRICE", "PRICE"],
                    ["Accessory", "5", "1", "6,500"],
                ],
            ),
        ]
    )

    result = extract_catalog_prices(DOCX_PATH, "30MPW031000005", _character_configuration(14, 14))

    assert result.priced_options[0].price == Decimal("6500")
    assert result.priced_options[0].raw_value == "6,500"


def test_character_based_hyphen_search_token_is_not_blank() -> None:
    _write_docx(
        [
            ("p", "POSITION 14"),
            (
                "tbl",
                [
                    ["DESCRIPTION", "CODE", "MASTER PRICE"],
                    ["", "", "031"],
                    ["No Disconnect", "-", "Std."],
                ],
            ),
        ]
    )

    result = extract_catalog_prices(DOCX_PATH, "30MPW03100000-", _character_configuration(14, 14))

    assert result.diagnostics[0].catalog_code == "-"
    assert result.diagnostics[0].status == STANDARD_OPTION


def test_character_based_combined_tokens_match_exact_logical_token() -> None:
    _write_docx(
        [
            ("p", "POSITION 14"),
            (
                "tbl",
                [
                    ["DESCRIPTION", "CODE", "MASTER PRICE"],
                    ["", "", "031"],
                    ["Combined", "3, 5, 7", "6,500"],
                ],
            ),
        ]
    )

    found = extract_catalog_prices(DOCX_PATH, "30MPW031000005", _character_configuration(14, 14))
    missing = extract_catalog_prices(DOCX_PATH, "30MPW031000006", _character_configuration(14, 14))

    assert found.priced_options[0].price == Decimal("6500")
    assert missing.priced_options == []
    assert missing.diagnostics[0].status == CHARACTER_NOT_FOUND


def test_character_based_condenser_filtering_happens_before_price_selection() -> None:
    _write_docx(
        [
            ("p", "POSITION 14"),
            (
                "tbl",
                [
                    ["DESCRIPTION", "CODE", "CONDENSER", "MASTER PRICE"],
                    ["", "", "", "031"],
                    ["Fused Disconnect", "5", "MPW/Q", "6,500"],
                    ["Fused Disconnect", "5", "MPA", "7,000"],
                ],
            ),
        ]
    )
    configuration = _character_configuration(14, 14)

    mpw = extract_catalog_prices(DOCX_PATH, "30MPW031000005", configuration)
    mpq = extract_catalog_prices(DOCX_PATH, "30MPQ031000005", configuration)
    mpa = extract_catalog_prices(DOCX_PATH, "30MPA031000005", configuration)

    assert mpw.priced_options[0].price == Decimal("6500")
    assert mpq.priced_options[0].price == Decimal("6500")
    assert mpa.priced_options[0].price == Decimal("7000")


def test_character_based_reuses_voltage_and_size_selection() -> None:
    _write_docx(
        [
            ("p", "POSITION 14"),
            (
                "tbl",
                [
                    ["DESCRIPTION", "CODE", "VOLTAGE", "MASTER PRICE"],
                    ["", "", "", "017", "031"],
                    ["Fused Disconnect", "5", "575-3-60", "1,111", "2,222"],
                    ["", "", "208/230-3-60", "3,333", "4,444"],
                ],
            ),
        ]
    )

    result = extract_catalog_prices(DOCX_PATH, "30MPW031500005", _character_configuration(14, 14))

    assert result.priced_options[0].price == Decimal("4444")


def test_character_based_conditional_rows_select_price_from_catalog_expression() -> None:
    _write_docx(
        [
            ("p", "POSITION 14"),
            (
                "tbl",
                [
                    ["14th DIGIT ORDER CODE", "AHFa", "MASTER PRICE"],
                    ["G", "{13}=3", "19,759"],
                    ["", "{13}=D", "38,826"],
                ],
            ),
        ]
    )
    configuration = _character_configuration(14, 14)
    configuration["conditional_price_rules"] = {"enabled": True, "positions": [14]}

    result_3 = extract_catalog_prices(DOCX_PATH, "30MPW03100003G", configuration)
    result_d = extract_catalog_prices(DOCX_PATH, "30MPW0310000DG", configuration)

    assert result_3.priced_options[0].catalog_character == "G"
    assert result_3.priced_options[0].price == Decimal("19759")
    assert result_d.priced_options[0].catalog_character == "G"
    assert result_d.priced_options[0].price == Decimal("38826")


def test_code_based_conditional_rows_select_price_from_catalog_expression() -> None:
    _write_docx(
        [
            ("p", "POSITION 14"),
            (
                "tbl",
                [
                    ["DESCRIPTION", "AHFa", "MASTER PRICE"],
                    ["High AHF 5B", "{13}=3", "19,759"],
                    ["", "{13}=D", "38,826"],
                ],
            ),
        ]
    )
    configuration = _configuration([14], {14: {"5B": ["G"]}})
    configuration["conditional_price_rules"] = {"enabled": True, "positions": [14]}

    result = extract_catalog_prices(DOCX_PATH, "30MPW0310000DG", configuration)

    assert result.priced_options[0].catalog_code == "5B"
    assert result.priced_options[0].price == Decimal("38826")


def test_document_comparison_records_keep_placeholder_for_failed_middle_option() -> None:
    _write_docx(
        [
            ("p", "POSITION 14"),
            ("tbl", [["DESCRIPTION", "CODE", "MASTER PRICE"], ["Wrong character", "G", "9,999"]]),
            ("p", "POSITION 15"),
            ("tbl", [["DESCRIPTION", "CODE", "MASTER PRICE"], ["Matching next option", "Y", "3,000"]]),
        ]
    )

    extraction = extract_catalog_prices(DOCX_PATH, "30MPW03100000XY", _character_configuration(14, 15))
    records = build_document_comparison_records(extraction)

    assert [(record.sequence, record.position, record.code, record.document_price, record.diagnostic) for record in records] == [
        (1, "BASE", "BASE UNIT", None, "base_unit_rule_not_configured"),
        (2, "14", "X", None, CHARACTER_NOT_FOUND),
        (3, "15", "Y", Decimal("3000.00"), None),
    ]


def test_document_comparison_records_skip_standard_options_to_preserve_sap_order() -> None:
    _write_docx(
        [
            ("p", "POSITION 13"),
            ("tbl", [["DESCRIPTION", "CODE", "MASTER PRICE"], ["Standard pump", "3", "Std."]]),
            ("p", "POSITION 14"),
            ("tbl", [["DESCRIPTION", "CODE", "MASTER PRICE"], ["Priced electrical", "D", "21,222"]]),
        ]
    )

    extraction = extract_catalog_prices(DOCX_PATH, "30MPW03100003D", _character_configuration(13, 14))
    records = build_document_comparison_records(extraction)

    assert [(record.sequence, record.position, record.code, record.document_price, record.diagnostic) for record in records] == [
        (1, "BASE", "BASE UNIT", None, "base_unit_rule_not_configured"),
        (2, "14", "D", Decimal("21222.00"), None),
    ]


def test_document_comparison_records_skip_invalid_option_prices_to_preserve_sap_order() -> None:
    _write_docx(
        [
            ("p", "POSITION 13"),
            ("tbl", [["DESCRIPTION", "CODE", "MASTER PRICE"], ["Invalid pump", "3", "Future Offering"]]),
            ("p", "POSITION 14"),
            ("tbl", [["DESCRIPTION", "CODE", "MASTER PRICE"], ["Priced electrical", "D", "21,222"]]),
        ]
    )

    extraction = extract_catalog_prices(DOCX_PATH, "30MPW03100003D", _character_configuration(13, 14))
    records = build_document_comparison_records(extraction)

    assert [(record.sequence, record.position, record.code, record.document_price, record.diagnostic) for record in records] == [
        (1, "BASE", "BASE UNIT", None, "base_unit_rule_not_configured"),
        (2, "14", "D", Decimal("21222.00"), None),
    ]


def _configuration(configured_positions: list[int], mappings: dict[int, dict[str, list[str]]] | None = None) -> dict:
    mappings = mappings or {}
    return {
        "product_type": "30MP",
        "structure": [
            {
                "characteristic_key": "CONDENSER_OPTION",
                "start_position": 3,
                "end_position": 5,
                "description": "",
                "used": True,
                "specifications": [],
            },
            {
                "characteristic_key": "TONNAGE",
                "start_position": 6,
                "end_position": 8,
                "description": "",
                "used": True,
                "specifications": [],
            },
            {
                "characteristic_key": "VOLTAGE",
                "start_position": 9,
                "end_position": 9,
                "description": "",
                "used": True,
                "specifications": [
                    {"catalog_value": "1", "label": "575-3-60", "description": "", "allowed": True},
                    {"catalog_value": "2", "label": "380-3-60", "description": "", "allowed": True},
                    {"catalog_value": "5", "label": "208/230-3-60", "description": "", "allowed": True},
                    {"catalog_value": "6", "label": "460-3-60", "description": "", "allowed": True},
                ],
            },
        ],
        "configured_positions": configured_positions,
        "positions": {
            str(position): {
                "option_codes": list((mappings.get(position) or {"1": ["0", "A", "G"]}).keys()),
                "allowed_values_by_option_code": mappings.get(position) or {"1": ["0", "A", "G"]},
            }
            for position in configured_positions
        },
    }


def _character_configuration(start_position: int, end_position: int) -> dict:
    configuration = _configuration([], {})
    configuration["search_mode"] = "character_based"
    configuration["configured_positions"] = []
    configuration["positions"] = {}
    configuration["structure"].append(
        {
            "characteristic_key": "OPTIONS",
            "start_position": start_position,
            "end_position": end_position,
            "description": "Character-based option positions",
            "used": True,
            "specifications": [],
        }
    )
    return configuration


def _real_30mp_configuration() -> dict:
    return {
        **_configuration(
            [10, 12, 13, 14, 15, 16],
            {
                10: {"2A": ["3"], "11": ["3"], "12": ["3"]},
                12: {"1D": ["G"], "6B": ["G"]},
                13: {"3B": ["5"], "7A": ["5"]},
                14: {"5B": ["5"], "19A": ["5"]},
                15: {"4A": ["7"], "18A": ["7"]},
                16: {"8B": ["B"], "15": ["B"]},
            },
        )
    }


def _write_docx(body_items: list[tuple[str, object]]) -> None:
    body_xml = []
    for kind, payload in body_items:
        if kind == "p":
            body_xml.append(_paragraph_xml(str(payload)))
        else:
            body_xml.append(_table_xml(payload))  # type: ignore[arg-type]
    document_xml = (
        '<?xml version="1.0" encoding="UTF-8" standalone="yes"?>'
        '<w:document xmlns:w="http://schemas.openxmlformats.org/wordprocessingml/2006/main">'
        f"<w:body>{''.join(body_xml)}<w:sectPr/></w:body></w:document>"
    )
    with zipfile.ZipFile(DOCX_PATH, "w") as archive:
        archive.writestr(
            "[Content_Types].xml",
            '<Types xmlns="http://schemas.openxmlformats.org/package/2006/content-types">'
            '<Default Extension="xml" ContentType="application/xml"/>'
            '<Override PartName="/word/document.xml" ContentType="application/vnd.openxmlformats-officedocument.wordprocessingml.document.main+xml"/>'
            "</Types>",
        )
        archive.writestr(
            "_rels/.rels",
            '<Relationships xmlns="http://schemas.openxmlformats.org/package/2006/relationships">'
            '<Relationship Id="rId1" Type="http://schemas.openxmlformats.org/officeDocument/2006/relationships/officeDocument" Target="word/document.xml"/>'
            "</Relationships>",
        )
        archive.writestr("word/document.xml", document_xml)


def _paragraph_xml(text: str) -> str:
    escaped = (
        text.replace("&", "&amp;")
        .replace("<", "&lt;")
        .replace(">", "&gt;")
    )
    return f"<w:p><w:r><w:t>{escaped}</w:t></w:r></w:p>"


def _table_xml(rows: list[list[str]]) -> str:
    row_xml = []
    for row in rows:
        cells = "".join(f"<w:tc>{_paragraph_xml(cell)}</w:tc>" for cell in row)
        row_xml.append(f"<w:tr>{cells}</w:tr>")
    return f"<w:tbl>{''.join(row_xml)}</w:tbl>"
