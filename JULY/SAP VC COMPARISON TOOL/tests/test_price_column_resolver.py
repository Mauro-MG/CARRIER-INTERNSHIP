from __future__ import annotations

from dataclasses import dataclass

from services.price_column_resolver import (
    ALL_CRITERIA,
    AMBIGUOUS,
    AMBIGUOUS_PRICE_COLUMN,
    SINGLE_CRITERION,
    resolve_price_column,
)


@dataclass(frozen=True)
class Row:
    row_number: int
    raw_cells: list[str]


@dataclass(frozen=True)
class Table:
    rows: list[Row]


def test_full_combined_match_selects_exact_tonnage_tier_column() -> None:
    table = _table([["DESCRIPTION", "350-M", "350-H", "400-M", "400-H", "450-M", "450-H"], ["Option 5B", "1", "2", "3", "4", "5", "6"]])
    result = resolve_price_column(
        table=table,
        price_columns={1: "350-M", 2: "350-H", 3: "400-M", 4: "400-H", 5: "450-M", 6: "450-H"},
        catalog_context=_context({"TONNAGE": "400", "TIER": "M"}),
        column_criteria={"enabled": True, "keys": ["TONNAGE", "TIER"]},
        selected_row=table.rows[1],
    )

    assert result.success
    assert result.column_index == 3
    assert result.match_level == ALL_CRITERIA


def test_specification_alias_matches_mid_header() -> None:
    table = _table([["DESCRIPTION", "400-Mid", "400-High"], ["Option 5B", "3", "4"]])
    result = resolve_price_column(
        table=table,
        price_columns={1: "400-Mid", 2: "400-High"},
        catalog_context=_context({"TONNAGE": "400", "TIER": "M"}, {"TIER": ["Mid"]}),
        column_criteria={"enabled": True, "keys": ["TONNAGE", "TIER"]},
        selected_row=table.rows[1],
    )

    assert result.success
    assert result.column_index == 1


def test_fallback_to_unique_tonnage_column() -> None:
    table = _table([["DESCRIPTION", "350", "400", "450"], ["Option 5B", "1", "2", "3"]])
    result = resolve_price_column(
        table=table,
        price_columns={1: "350", 2: "400", 3: "450"},
        catalog_context=_context({"TONNAGE": "400", "TIER": "M"}, {"TIER": ["Mid"]}),
        column_criteria={"enabled": True, "keys": ["TONNAGE", "TIER"]},
        selected_row=table.rows[1],
    )

    assert result.success
    assert result.column_index == 2
    assert result.match_level == SINGLE_CRITERION
    assert result.matched_keys == ["TONNAGE"]


def test_does_not_fallback_when_full_match_exists() -> None:
    table = _table([["DESCRIPTION", "400-M", "400-H"], ["Option 5B", "1", "2"]])
    result = resolve_price_column(
        table=table,
        price_columns={1: "400-M", 2: "400-H"},
        catalog_context=_context({"TONNAGE": "400", "TIER": "M"}),
        column_criteria={"enabled": True, "keys": ["TONNAGE", "TIER"]},
        selected_row=table.rows[1],
    )

    assert result.success
    assert result.column_index == 1
    assert result.match_level == ALL_CRITERIA


def test_ambiguous_fallback_does_not_guess() -> None:
    table = _table([["DESCRIPTION", "400-A", "400-B"], ["Option 5B", "1", "2"]])
    result = resolve_price_column(
        table=table,
        price_columns={1: "400-A", 2: "400-B"},
        catalog_context=_context({"TONNAGE": "400", "TIER": ""}),
        column_criteria={"enabled": True, "keys": ["TONNAGE", "TIER"]},
        selected_row=table.rows[1],
    )

    assert not result.success
    assert result.match_level == AMBIGUOUS
    assert result.diagnostic == AMBIGUOUS_PRICE_COLUMN


def test_stacked_header_uses_all_header_parts() -> None:
    table = _table(
        [
            ["DESCRIPTION", "MID TIER", "MID TIER", "MID TIER", "HIGH TIER", "HIGH TIER", "HIGH TIER"],
            ["", "350", "400", "450", "350", "400", "450"],
            ["Option 5B", "1", "2", "3", "4", "5", "6"],
        ]
    )
    result = resolve_price_column(
        table=table,
        price_columns={1: "350", 2: "400", 3: "450", 4: "350", 5: "400", 6: "450"},
        catalog_context=_context({"TONNAGE": "400", "TIER": "M"}, {"TIER": ["Mid"]}),
        column_criteria={"enabled": True, "keys": ["TONNAGE", "TIER"]},
        selected_row=table.rows[2],
    )

    assert result.success
    assert result.column_index == 2
    assert result.matched_header_parts == ["MID TIER", "400"]


def test_multiline_header_cell_keeps_alternative_size_tier_pairs_separate() -> None:
    table = _table(
        [
            ["DESCRIPTION", "MASTER PRICE", "MASTER PRICE"],
            ["", "400-Mid", "400-High\n450-Mid"],
            ["No Pump 16", "Std.", "Std."],
            ["Low Head Pump 16A", "99,982", "99,982"],
        ]
    )
    result = resolve_price_column(
        table=table,
        price_columns={1: "400-Mid", 2: "400-High 450-Mid"},
        catalog_context=_context({"TONNAGE": "400", "TIER": "M"}, {"TIER": ["Mid", "Mid Tier"]}),
        column_criteria={"enabled": True, "keys": ["TONNAGE", "TIER"]},
        selected_row=table.rows[3],
    )

    assert result.success
    assert result.column_index == 1
    assert result.match_level == ALL_CRITERIA
    assert "Std." not in result.matched_header_parts


def test_three_criteria_prefers_full_match_then_unique_fallback() -> None:
    table = _table([["DESCRIPTION", "400-M-460", "400-M-575", "400-H-460"], ["Option 5B", "1", "2", "3"]])
    full = resolve_price_column(
        table=table,
        price_columns={1: "400-M-460", 2: "400-M-575", 3: "400-H-460"},
        catalog_context=_context({"TONNAGE": "400", "TIER": "M", "VOLTAGE": "6"}, {"VOLTAGE": ["460-3-60"]}),
        column_criteria={"enabled": True, "keys": ["TONNAGE", "TIER", "VOLTAGE"]},
        selected_row=table.rows[1],
    )
    fallback_table = _table([["DESCRIPTION", "400-M", "400-H", "450-M"], ["Option 5B", "1", "2", "3"]])
    fallback = resolve_price_column(
        table=fallback_table,
        price_columns={1: "400-M", 2: "400-H", 3: "450-M"},
        catalog_context=_context({"TONNAGE": "400", "TIER": "M", "VOLTAGE": "6"}),
        column_criteria={"enabled": True, "keys": ["TONNAGE", "TIER", "VOLTAGE"]},
        selected_row=fallback_table.rows[1],
    )

    assert full.column_index == 1
    assert full.match_level == ALL_CRITERIA
    assert fallback.column_index == 1
    assert fallback.matched_keys == ["TONNAGE", "TIER"]


def test_numeric_tokens_do_not_match_partial_numbers() -> None:
    table = _table([["DESCRIPTION", "4000", "1400", "400"], ["Option 5B", "1", "2", "3"]])
    result = resolve_price_column(
        table=table,
        price_columns={1: "4000", 2: "1400", 3: "400"},
        catalog_context=_context({"TONNAGE": "400"}),
        column_criteria={"enabled": True, "keys": ["TONNAGE"]},
        selected_row=table.rows[1],
    )

    assert result.success
    assert result.column_index == 3


def test_letter_tokens_do_not_match_words_containing_letter() -> None:
    table = _table([["DESCRIPTION", "MASTER PRICE", "MID"], ["Option 5B", "1", "2"]])
    result = resolve_price_column(
        table=table,
        price_columns={1: "MASTER PRICE", 2: "MID"},
        catalog_context=_context({"TIER": "M"}, {"TIER": ["Mid"]}),
        column_criteria={"enabled": True, "keys": ["TIER"]},
        selected_row=table.rows[1],
    )

    assert result.success
    assert result.column_index == 2


def test_only_one_price_column_does_not_need_criteria() -> None:
    table = _table([["DESCRIPTION", "MASTER PRICE"], ["Option 5B", "1"]])
    result = resolve_price_column(
        table=table,
        price_columns={1: "MASTER PRICE"},
        catalog_context=_context({}),
        column_criteria=None,
        selected_row=table.rows[1],
    )

    assert result.success
    assert result.column_index == 1


def _table(rows: list[list[str]]) -> Table:
    return Table([Row(index, row) for index, row in enumerate(rows, start=1)])


def _context(values: dict[str, str], aliases: dict[str, list[str]] | None = None) -> dict[str, object]:
    return {
        "structure_values": values,
        "structure_aliases": aliases or {},
    }
