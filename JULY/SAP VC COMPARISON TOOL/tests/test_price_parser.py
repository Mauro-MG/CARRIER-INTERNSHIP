from decimal import Decimal

import pytest

from services.price_parser import (
    DASH, INCLUDED, INVALID, NO_CHARGE, NOT_AVAILABLE, NUMERIC_PRICE, STANDARD,
    parse_document_value,
)


@pytest.mark.parametrize(("text", "value"), [
    ("274,374", Decimal("274374")),
    ("$274,374.00", Decimal("274374.00")),
    ("274374", Decimal("274374")),
    ("(1,688)", Decimal("-1688")),
    ("($1,688.00)", Decimal("-1688.00")),
])
def test_numeric_document_prices(text: str, value: Decimal) -> None:
    parsed = parse_document_value(text)
    assert parsed.value_type == NUMERIC_PRICE
    assert parsed.decimal_value == value
    assert parsed.raw_text == text


@pytest.mark.parametrize(("text", "value_type"), [
    ("Std.", STANDARD), ("NC", NO_CHARGE), ("Included", INCLUDED),
    ("N/A", NOT_AVAILABLE), ("-", DASH),
])
def test_special_values_are_not_zero(text: str, value_type: str) -> None:
    parsed = parse_document_value(text)
    assert parsed.value_type == value_type
    assert parsed.decimal_value is None


def test_invalid_document_value_is_controlled() -> None:
    parsed = parse_document_value("price pending")
    assert parsed.value_type == INVALID
    assert parsed.decimal_value is None
