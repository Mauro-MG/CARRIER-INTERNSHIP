from decimal import Decimal

from services.comparison_service import (
    AMBIGUOUS_DOCUMENT_PRICE, DOCUMENT_PRICE_NOT_FOUND, MATCH,
    NON_NUMERIC_DOCUMENT_VALUE, PRICE_DISCREPANCY, compare_prices,
)
from services.document_price_extractor import DocumentPriceResult
from services.price_parser import INCLUDED, NUMERIC_PRICE


def document_result(value: Decimal | None, confidence: str = "HIGH", value_type: str = NUMERIC_PRICE) -> DocumentPriceResult:
    return DocumentPriceResult("TEST", True, value_type, value, str(value) if value is not None else "Included", 1, confidence, 80, 1, [], "evidence")


def test_exact_match() -> None:
    assert compare_prices(Decimal("10.00"), True, document_result(Decimal("10.00")), Decimal("0.01")).status == MATCH


def test_match_with_tolerance_and_decimal_precision() -> None:
    result = compare_prices(Decimal("0.30"), True, document_result(Decimal("0.3001")), Decimal("0.001"))
    assert result.status == MATCH
    assert result.difference == Decimal("-0.0001")


def test_sap_higher() -> None:
    result = compare_prices(Decimal("12"), True, document_result(Decimal("10")), Decimal("0.01"))
    assert result.status == PRICE_DISCREPANCY
    assert result.difference == Decimal("2")


def test_sap_lower() -> None:
    result = compare_prices(Decimal("8"), True, document_result(Decimal("10")), Decimal("0.01"))
    assert result.status == PRICE_DISCREPANCY
    assert result.difference == Decimal("-2")


def test_missing_document_price() -> None:
    missing = DocumentPriceResult("TEST", False, None, None, None, None, "NOT_FOUND", None, 0, [], "none")
    assert compare_prices(Decimal("10"), True, missing, Decimal("0.01")).status == DOCUMENT_PRICE_NOT_FOUND


def test_ambiguous_document_price() -> None:
    assert compare_prices(Decimal("10"), True, document_result(Decimal("10"), "AMBIGUOUS"), Decimal("0.01")).status == AMBIGUOUS_DOCUMENT_PRICE


def test_nonnumeric_document_value() -> None:
    assert compare_prices(Decimal("10"), True, document_result(None, value_type=INCLUDED), Decimal("0.01")).status == NON_NUMERIC_DOCUMENT_VALUE
