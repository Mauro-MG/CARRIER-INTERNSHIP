from __future__ import annotations

from dataclasses import dataclass, field
from decimal import Decimal, InvalidOperation
from typing import TypedDict

from .catalog_normalizer import normalize_catalog_number


class SAPRecord(TypedDict):
    original_catalog_number: str
    normalized_catalog_number: str
    sap_price: Decimal
    original_price_text: str
    source_row: int


@dataclass
class ParseResult:
    records: list[SAPRecord] = field(default_factory=list)
    errors: list[dict[str, object]] = field(default_factory=list)
    duplicates: list[dict[str, object]] = field(default_factory=list)


@dataclass(frozen=True)
class SAPPriceRecord:
    sequence: int
    tag: str
    raw_price: str
    price: Decimal
    source_row: int


@dataclass
class SAPPriceParseResult:
    records: list[SAPPriceRecord] = field(default_factory=list)
    errors: list[dict[str, object]] = field(default_factory=list)


def parse_price(value: str) -> Decimal:
    text = value.strip()
    if not text:
        raise ValueError("SAP Master Price is blank.")
    negative = text.startswith("(") and text.endswith(")")
    if "(" in text or ")" in text:
        if not negative:
            raise ValueError("SAP Master Price has invalid parentheses.")
        text = text[1:-1].strip()
    cleaned = text.replace("$", "").replace(",", "").strip()
    if not cleaned:
        raise ValueError("SAP Master Price is blank.")
    try:
        amount = Decimal(cleaned)
    except InvalidOperation as exc:
        raise ValueError("SAP Master Price is not a valid number.") from exc
    return -amount if negative else amount


def _is_header(columns: list[str]) -> bool:
    if len(columns) < 2:
        return False
    first = " ".join(columns[0].strip().lower().replace("_", " ").split())
    second = " ".join(columns[1].strip().lower().replace("_", " ").split())
    return "catalog" in first and ("price" in second or "master" in second)


def _is_sap_price_header(columns: list[str]) -> bool:
    if len(columns) < 2:
        return False
    first = " ".join(columns[0].strip().lower().replace("_", " ").split())
    second = " ".join(columns[1].strip().lower().replace("_", " ").split())
    return first in {"tag", "catalog", "catalog number", "catalog no", "material"} and "price" in second


def parse_ordered_sap_prices(text: str) -> SAPPriceParseResult:
    """Parse ordered SAP TAG/PRICE rows for appV2 row-by-row comparison.

    Duplicate tags are intentionally allowed here because sequence, not tag text,
    controls the comparison.
    """
    result = SAPPriceParseResult()
    header_checked = False

    for row_number, raw_row in enumerate(text.splitlines(), start=1):
        if not raw_row.strip():
            continue
        columns = raw_row.split("\t")
        if not header_checked:
            header_checked = True
            if _is_sap_price_header(columns) or _is_header(columns):
                continue
        if len(columns) < 2:
            result.errors.append({"row": row_number, "message": "At least two tab-separated columns are required.", "input": raw_row})
            continue

        tag = columns[0].strip()
        raw_price = columns[1].strip()
        if not tag:
            result.errors.append({"row": row_number, "message": "SAP TAG is blank.", "input": raw_row})
            continue
        if not raw_price:
            result.errors.append({"row": row_number, "message": "SAP price is blank.", "input": raw_row})
            continue
        try:
            price = parse_price(raw_price).quantize(Decimal("0.01"))
        except ValueError as exc:
            result.errors.append({"row": row_number, "message": str(exc), "input": raw_row})
            continue

        result.records.append(
            SAPPriceRecord(
                sequence=len(result.records) + 1,
                tag=tag,
                raw_price=raw_price,
                price=price,
                source_row=row_number,
            )
        )
    return result


def parse_sap_input(text: str) -> ParseResult:
    result = ParseResult()
    seen: dict[str, int] = {}
    header_checked = False

    for row_number, raw_row in enumerate(text.splitlines(), start=1):
        if not raw_row.strip():
            continue
        columns = raw_row.split("\t")
        if not header_checked:
            header_checked = True
            if _is_header(columns):
                continue
        if len(columns) < 2:
            result.errors.append({"row": row_number, "message": "At least two tab-separated columns are required.", "input": raw_row})
            continue

        catalog = columns[0].strip()
        price_text = columns[1].strip()
        if not catalog:
            result.errors.append({"row": row_number, "message": "Catalog Number is blank.", "input": raw_row})
            continue
        try:
            normalized = normalize_catalog_number(catalog)
            price = parse_price(price_text)
        except ValueError as exc:
            result.errors.append({"row": row_number, "message": str(exc), "input": raw_row})
            continue

        if normalized in seen:
            duplicate = {"catalog_number": catalog, "normalized_catalog_number": normalized, "row": row_number, "first_row": seen[normalized]}
            result.duplicates.append(duplicate)
            result.errors.append({"row": row_number, "message": f"Duplicate catalog number; first provided on row {seen[normalized]}.", "input": raw_row})
            continue

        seen[normalized] = row_number
        result.records.append({
            "original_catalog_number": catalog,
            "normalized_catalog_number": normalized,
            "sap_price": price,
            "original_price_text": price_text,
            "source_row": row_number,
        })
    return result
