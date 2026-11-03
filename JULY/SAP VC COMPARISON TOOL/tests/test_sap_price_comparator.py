from __future__ import annotations

from decimal import Decimal

from services.sap_input_parser import SAPPriceRecord
from services.sap_price_comparator import (
    DOC_VALUE_NOT_NUMERIC,
    MATCH,
    NO_DOCUMENT_MATCH,
    NO_SAP_MATCH,
    DocumentComparisonRecord,
    compare_sap_prices,
)


def test_simple_unordered_matching_including_base_unit() -> None:
    documents = [_doc(1, "BASE", "BASE UNIT", "100000"), _doc(2, "11", "1A", "2000"), _doc(3, "14", "5B", "6500"), _doc(4, "15", "7A", "3000")]
    sap = [_sap(1, "TAG_5B", "6500"), _sap(2, "TAG_BASE", "100000"), _sap(3, "TAG_7A", "3000"), _sap(4, "TAG_1A", "2000")]

    result = compare_sap_prices(sap, documents)

    assert [(row.tag, row.position, row.code, row.result) for row in result.rows] == [
        ("TAG_5B", "14", "5B", MATCH),
        ("TAG_BASE", "BASE", "BASE UNIT", MATCH),
        ("TAG_7A", "15", "7A", MATCH),
        ("TAG_1A", "11", "1A", MATCH),
    ]
    assert result.all_match is True


def test_reordering_sap_rows_does_not_change_logical_matches() -> None:
    documents = [_doc(1, "BASE", "BASE UNIT", "4000"), _doc(2, "11", "1A", "1000"), _doc(3, "12", "2B", "2000"), _doc(4, "14", "5B", "3000")]
    first = [_sap(1, "TAG_A", "1000"), _sap(2, "TAG_B", "2000"), _sap(3, "TAG_C", "3000"), _sap(4, "TAG_D", "4000")]
    reordered = [_sap(1, "TAG_D", "4000"), _sap(2, "TAG_B", "2000"), _sap(3, "TAG_A", "1000"), _sap(4, "TAG_C", "3000")]

    assert _pairs_by_tag(compare_sap_prices(first, documents).rows) == _pairs_by_tag(compare_sap_prices(reordered, documents).rows)


def test_exactly_one_cent_is_not_eligible() -> None:
    result = compare_sap_prices([_sap(1, "TAG_A", "100.01")], [_doc(1, "11", "1A", "100.00")])

    assert [row.result for row in result.rows] == [NO_DOCUMENT_MATCH, NO_SAP_MATCH]
    assert result.rows[0].difference is None


def test_less_than_one_cent_matches_and_retains_precision() -> None:
    result = compare_sap_prices([_sap(1, "TAG_A", "100.005")], [_doc(1, "11", "1A", "100.000")])

    assert result.rows[0].result == MATCH
    assert result.rows[0].difference == Decimal("0.005")
    assert result.rows[0].absolute_difference == Decimal("0.005")


def test_best_candidate_has_smallest_absolute_difference() -> None:
    result = compare_sap_prices([_sap(1, "TAG_A", "100.005")], [_doc(1, "11", "A", "100.000"), _doc(2, "12", "B", "100.004")])

    assert result.rows[0].code == "B"
    assert result.rows[0].absolute_difference == Decimal("0.001")
    assert result.rows[0].eligible_candidate_count == 2


def test_matching_maximizes_cardinality_before_difference() -> None:
    result = compare_sap_prices(
        [_sap(1, "FLEXIBLE", "100.000"), _sap(2, "RESTRICTED", "100.009")],
        [_doc(1, "11", "ONLY_FOR_RESTRICTED", "100.000"), _doc(2, "12", "ONLY_OTHER", "99.991")],
    )

    assert result.match_count == 2
    assert {row.tag: row.code for row in result.rows} == {"FLEXIBLE": "ONLY_OTHER", "RESTRICTED": "ONLY_FOR_RESTRICTED"}


def test_one_document_record_cannot_be_reused() -> None:
    result = compare_sap_prices([_sap(1, "TAG_A", "5000"), _sap(2, "TAG_B", "5000")], [_doc(1, "11", "1A", "5000")])

    assert result.match_count == 1
    assert result.no_document_match_count == 1
    assert [row.result for row in result.rows].count(MATCH) == 1


def test_duplicate_prices_on_both_sides_match_one_to_one() -> None:
    result = compare_sap_prices([_sap(1, "TAG_A", "5000"), _sap(2, "TAG_B", "5000")], [_doc(1, "11", "1A", "5000"), _doc(2, "14", "5B", "5000")])

    assert result.match_count == 2
    assert len({row.document_record_id for row in result.rows}) == 2
    assert result.ambiguous_match_count == 2


def test_duplicate_price_tie_breaking_is_stable_when_sap_rows_are_reordered() -> None:
    documents = [_doc(1, "11", "1A", "5000"), _doc(2, "14", "5B", "5000")]
    first = compare_sap_prices([_sap(1, "TAG_A", "5000"), _sap(2, "TAG_B", "5000")], documents)
    reordered = compare_sap_prices([_sap(1, "TAG_B", "5000"), _sap(2, "TAG_A", "5000")], documents)

    assert _pairs_by_tag(first.rows) == _pairs_by_tag(reordered.rows) == {
        "TAG_A": ("11", "1A"),
        "TAG_B": ("14", "5B"),
    }


def test_extra_sap_price_is_no_document_match() -> None:
    result = compare_sap_prices([_sap(1, "TAG_A", "2000"), _sap(2, "TAG_B", "4000")], [_doc(1, "11", "1A", "2000")])

    assert [(row.tag, row.result) for row in result.rows] == [("TAG_A", MATCH), ("TAG_B", NO_DOCUMENT_MATCH)]


def test_extra_document_price_is_no_sap_match() -> None:
    result = compare_sap_prices([_sap(1, "TAG_A", "2000")], [_doc(1, "11", "1A", "2000"), _doc(2, "14", "5B", "3000")])

    assert [(row.code, row.result) for row in result.rows] == [("1A", MATCH), ("5B", NO_SAP_MATCH)]


def test_failed_middle_extraction_does_not_shift_matches() -> None:
    documents = [_doc(1, "BASE", "BASE UNIT", "100000"), _doc(2, "11", "1A", "2000"), _doc(3, "14", "5B", None), _doc(4, "15", "7A", "3000")]
    sap = [_sap(1, "TAG_7A", "3000"), _sap(2, "TAG_BASE", "100000"), _sap(3, "TAG_1A", "2000")]

    result = compare_sap_prices(sap, documents)

    assert [(row.tag, row.code, row.result) for row in result.rows[:3]] == [("TAG_7A", "7A", MATCH), ("TAG_BASE", "BASE UNIT", MATCH), ("TAG_1A", "1A", MATCH)]
    assert result.rows[3].result == DOC_VALUE_NOT_NUMERIC


def test_nonnumeric_document_value_is_not_converted_to_zero() -> None:
    result = compare_sap_prices([_sap(1, "ZERO", "0")], [_doc(1, "11", "1A", None, raw_document_price="Std.")])

    assert [row.result for row in result.rows] == [NO_DOCUMENT_MATCH, DOC_VALUE_NOT_NUMERIC]


def test_negative_prices_match_with_sign_and_opposite_sign_does_not() -> None:
    matched = compare_sap_prices([_sap(1, "CREDIT", "-1984")], [_doc(1, "15", "7A", "-1984")])
    opposite = compare_sap_prices([_sap(1, "CREDIT", "-1984")], [_doc(1, "15", "7A", "1984")])

    assert matched.rows[0].result == MATCH
    assert opposite.rows[0].result == NO_DOCUMENT_MATCH


def test_code_and_character_metadata_are_preserved() -> None:
    code_based = compare_sap_prices([_sap(1, "ANY", "6500")], [_doc(1, "14", "5B", "6500", catalog_character="G")])
    character_based = compare_sap_prices([_sap(1, "OTHER", "7000")], [_doc(1, "15", "7", "7000", catalog_character="7")])

    assert (code_based.rows[0].position, code_based.rows[0].code, code_based.rows[0].catalog_character) == ("14", "5B", "G")
    assert (character_based.rows[0].position, character_based.rows[0].code, character_based.rows[0].catalog_character) == ("15", "7", "7")


def _pairs_by_tag(rows: list) -> dict[str, tuple[str, str]]:
    return {row.tag: (row.position, row.code) for row in rows if row.tag and row.result == MATCH}


def _sap(sequence: int, tag: str, price: str) -> SAPPriceRecord:
    return SAPPriceRecord(sequence=sequence, tag=tag, raw_price=price, price=Decimal(price), source_row=sequence)


def _doc(sequence: int, position: str, code: str, price: str | None, *, raw_document_price: str | None = None, catalog_character: str | None = None) -> DocumentComparisonRecord:
    return DocumentComparisonRecord(
        sequence=sequence,
        record_type="BASE_UNIT" if position == "BASE" else "OPTION",
        position=position,
        code=code,
        catalog_character=catalog_character,
        document_price=Decimal(price) if price is not None else None,
        raw_document_price=raw_document_price or price,
        record_id=f"doc-{sequence}",
    )
