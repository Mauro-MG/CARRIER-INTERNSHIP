from decimal import Decimal

from services.sap_input_parser import parse_ordered_sap_prices, parse_sap_input


def test_standard_input() -> None:
    result = parse_sap_input("30RC-2522S-1-----\t398043\n30RC_LG_CONDFAN_001\t15436")
    assert len(result.records) == 2
    assert result.records[0]["sap_price"] == Decimal("398043")
    assert not result.errors


def test_optional_header_is_ignored() -> None:
    result = parse_sap_input("Catalog Number\tSAP Master Price\nABC-1\t12.50")
    assert len(result.records) == 1
    assert result.records[0]["source_row"] == 2


def test_currency_formatting() -> None:
    result = parse_sap_input("ABC-1\t $1,234.56 ")
    assert result.records[0]["sap_price"] == Decimal("1234.56")
    assert result.records[0]["original_price_text"] == "$1,234.56"


def test_parentheses_are_negative() -> None:
    result = parse_sap_input("ABC-1\t($1,234.50)")
    assert result.records[0]["sap_price"] == Decimal("-1234.50")


def test_invalid_price_is_row_error() -> None:
    result = parse_sap_input("ABC-1\tnot money")
    assert not result.records
    assert "valid number" in str(result.errors[0]["message"])


def test_blank_catalog_is_row_error() -> None:
    result = parse_sap_input("\t123.45")
    assert not result.records
    assert result.errors[0]["message"] == "Catalog Number is blank."


def test_duplicate_is_reported_and_not_repeated() -> None:
    result = parse_sap_input("abc-1\t10\n ABC-1 \t20")
    assert len(result.records) == 1
    assert len(result.duplicates) == 1
    assert result.duplicates[0]["first_row"] == 1
    assert "Duplicate" in str(result.errors[0]["message"])


def test_extra_blank_rows_are_ignored() -> None:
    result = parse_sap_input("\n\nABC-1\t10\n   \nXYZ-2\t20\n")
    assert len(result.records) == 2
    assert not result.errors


def test_requires_two_tab_separated_columns() -> None:
    result = parse_sap_input("ABC-1 123")
    assert not result.records
    assert "two tab-separated" in str(result.errors[0]["message"])


def test_ordered_sap_price_rows_preserve_input_order_and_parse_formats() -> None:
    result = parse_ordered_sap_prices("TAG1\t1000\nTAG2\t2,500\nTAG3\t$3,750.50\nTAG4\t(1,984)")

    assert [record.sequence for record in result.records] == [1, 2, 3, 4]
    assert [record.tag for record in result.records] == ["TAG1", "TAG2", "TAG3", "TAG4"]
    assert [record.price for record in result.records] == [
        Decimal("1000.00"),
        Decimal("2500.00"),
        Decimal("3750.50"),
        Decimal("-1984.00"),
    ]
    assert not result.errors


def test_ordered_sap_price_rows_ignore_header_blank_rows_and_allow_duplicates() -> None:
    result = parse_ordered_sap_prices("TAG\tPRICE\n\nDUP\t100\n  DUP  \t200\n")

    assert [(record.sequence, record.tag, record.price) for record in result.records] == [
        (1, "DUP", Decimal("100.00")),
        (2, "DUP", Decimal("200.00")),
    ]
    assert not result.errors


def test_ordered_sap_price_rows_report_missing_and_invalid_values() -> None:
    result = parse_ordered_sap_prices("\t100\nTAG2\t\nTAG3\tnot money\nTAG4\t400")

    assert [(record.sequence, record.tag, record.price) for record in result.records] == [
        (1, "TAG4", Decimal("400.00")),
    ]
    assert [error["row"] for error in result.errors] == [1, 2, 3]
