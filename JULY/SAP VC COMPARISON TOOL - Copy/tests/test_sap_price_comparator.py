from __future__ import annotations

from decimal import Decimal

from services.sap_input_parser import SAPPriceRecord
from services.sap_price_comparator import (
    DOC_PRICE_MISSING,
    DOC_VALUE_NOT_NUMERIC,
    MATCH,
    MISMATCH,
    SAP_PRICE_MISSING,
    DocumentComparisonRecord,
    compare_sap_prices,
)


def test_exact_match() -> None:
    result = compare_sap_prices([_sap(1, "BASE", "100.00")], [_doc(1, "BASE", "BASE UNIT", "100.00")])

    assert result.rows[0].difference == Decimal("0.00")
    assert result.rows[0].result == MATCH
    assert result.all_match is True


def test_one_cent_positive_difference_is_mismatch() -> None:
    result = compare_sap_prices([_sap(1, "BASE", "100.01")], [_doc(1, "BASE", "BASE UNIT", "100.00")])

    assert result.rows[0].difference == Decimal("0.01")
    assert result.rows[0].result == MISMATCH


def test_one_cent_negative_difference_is_mismatch() -> None:
    result = compare_sap_prices([_sap(1, "BASE", "99.99")], [_doc(1, "BASE", "BASE UNIT", "100.00")])

    assert result.rows[0].difference == Decimal("-0.01")
    assert result.rows[0].result == MISMATCH


def test_positive_difference() -> None:
    result = compare_sap_prices([_sap(1, "BASE", "110")], [_doc(1, "BASE", "BASE UNIT", "100")])

    assert result.rows[0].difference == Decimal("10.00")
    assert result.rows[0].result == MISMATCH


def test_negative_exact_match() -> None:
    result = compare_sap_prices([_sap(1, "CREDIT", "-1984")], [_doc(1, "14", "5B", "-1984")])

    assert result.rows[0].difference == Decimal("0.00")
    assert result.rows[0].result == MATCH


def test_order_integrity_does_not_reorder_to_force_matches() -> None:
    sap_records = [_sap(1, "BASE", "100000"), _sap(2, "TAG_A", "2000"), _sap(3, "TAG_B", "3000")]
    document_records = [_doc(1, "BASE", "BASE UNIT", "100000"), _doc(2, "11", "OPT_A", "3000"), _doc(3, "12", "OPT_B", "2000")]

    result = compare_sap_prices(sap_records, document_records)

    assert [row.result for row in result.rows] == [MATCH, MISMATCH, MISMATCH]
    assert result.rows[1].tag == "TAG_A"
    assert result.rows[1].code == "OPT_A"
    assert result.rows[2].tag == "TAG_B"
    assert result.rows[2].code == "OPT_B"


def test_base_plus_multiple_component_rows_all_match() -> None:
    sap_records = [
        _sap(1, "BASE_TAG", "100000"),
        _sap(2, "TAG_1A", "2000"),
        _sap(3, "TAG_1D", "500"),
        _sap(4, "TAG_6B", "1250"),
        _sap(5, "TAG_5B", "3000"),
    ]
    document_records = [
        _doc(1, "BASE", "BASE UNIT", "100000"),
        _doc(2, "11", "1A", "2000"),
        _doc(3, "12", "1D", "500"),
        _doc(4, "12", "6B", "1250"),
        _doc(5, "14", "5B", "3000"),
    ]

    result = compare_sap_prices(sap_records, document_records)

    assert result.match_count == 5
    assert [row.result for row in result.rows] == [MATCH] * 5


def test_failed_middle_document_option_preserves_sequence_alignment() -> None:
    sap_records = [
        _sap(1, "BASE_TAG", "100000"),
        _sap(2, "TAG_1A", "2000"),
        _sap(3, "TAG_1D", "500"),
        _sap(4, "TAG_5B", "2500"),
        _sap(5, "TAG_7A", "3000"),
    ]
    document_records = [
        _doc(1, "BASE", "BASE UNIT", "100000"),
        _doc(2, "11", "1A", "2000"),
        _doc(3, "12", "1D", "500"),
        _doc(4, "14", "5B", None),
        _doc(5, "15", "7A", "3000"),
    ]

    result = compare_sap_prices(sap_records, document_records)

    assert [(row.code, row.result) for row in result.rows] == [
        ("BASE UNIT", MATCH),
        ("1A", MATCH),
        ("1D", MATCH),
        ("5B", DOC_PRICE_MISSING),
        ("7A", MATCH),
    ]


def test_extra_sap_rows_are_displayed() -> None:
    result = compare_sap_prices([_sap(1, "BASE", "100"), _sap(2, "EXTRA", "50")], [_doc(1, "BASE", "BASE UNIT", "100")])

    assert [row.result for row in result.rows] == [MATCH, DOC_PRICE_MISSING]
    assert result.rows[1].tag == "EXTRA"


def test_extra_document_rows_are_displayed() -> None:
    result = compare_sap_prices([_sap(1, "BASE", "100")], [_doc(1, "BASE", "BASE UNIT", "100"), _doc(2, "11", "1A", "50")])

    assert [row.result for row in result.rows] == [MATCH, SAP_PRICE_MISSING]
    assert result.rows[1].code == "1A"


def test_nonnumeric_document_value_is_not_converted_to_zero() -> None:
    result = compare_sap_prices([_sap(1, "STD_TAG", "0")], [_doc(1, "11", "1A", None, raw_document_price="Std.")])

    assert result.rows[0].result == DOC_VALUE_NOT_NUMERIC
    assert result.rows[0].document_price is None


def test_code_based_record_representation() -> None:
    result = compare_sap_prices([_sap(1, "TAG_5B", "6500")], [_doc(1, "14", "5B", "6500", catalog_character="G")])

    assert result.rows[0].position == "14"
    assert result.rows[0].code == "5B"
    assert result.rows[0].catalog_character == "G"
    assert result.rows[0].result == MATCH


def test_character_based_record_representation() -> None:
    result = compare_sap_prices([_sap(1, "TAG_5", "6500")], [_doc(1, "14", "5", "6500", catalog_character="5")])

    assert result.rows[0].position == "14"
    assert result.rows[0].code == "5"
    assert result.rows[0].catalog_character == "5"
    assert result.rows[0].result == MATCH


def _sap(sequence: int, tag: str, price: str) -> SAPPriceRecord:
    return SAPPriceRecord(sequence=sequence, tag=tag, raw_price=price, price=Decimal(price).quantize(Decimal("0.01")), source_row=sequence)


def _doc(
    sequence: int,
    position: str,
    code: str,
    price: str | None,
    *,
    raw_document_price: str | None = None,
    catalog_character: str | None = None,
) -> DocumentComparisonRecord:
    return DocumentComparisonRecord(
        sequence=sequence,
        record_type="BASE_UNIT" if position == "BASE" else "OPTION",
        position=position,
        code=code,
        catalog_character=catalog_character,
        document_price=Decimal(price).quantize(Decimal("0.01")) if price is not None else None,
        raw_document_price=raw_document_price or price,
    )
