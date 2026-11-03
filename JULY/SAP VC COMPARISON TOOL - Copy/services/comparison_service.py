from __future__ import annotations

from dataclasses import dataclass
from decimal import Decimal

from .document_price_extractor import DocumentPriceResult
from .price_parser import NUMERIC_PRICE

MATCH = "MATCH"
PRICE_DISCREPANCY = "PRICE_DISCREPANCY"
DOCUMENT_PRICE_NOT_FOUND = "DOCUMENT_PRICE_NOT_FOUND"
AMBIGUOUS_DOCUMENT_PRICE = "AMBIGUOUS_DOCUMENT_PRICE"
LOW_CONFIDENCE_DOCUMENT_PRICE = "LOW_CONFIDENCE_DOCUMENT_PRICE"
NON_NUMERIC_DOCUMENT_VALUE = "NON_NUMERIC_DOCUMENT_VALUE"
CATALOG_NOT_FOUND = "CATALOG_NOT_FOUND"
INVALID_SAP_PRICE = "INVALID_SAP_PRICE"


@dataclass(frozen=True)
class ComparisonResult:
    sap_price: Decimal | None
    document_price: Decimal | None
    difference: Decimal | None
    absolute_difference: Decimal | None
    status: str


def compare_prices(
    sap_price: Decimal | None,
    catalog_found: bool,
    document_result: DocumentPriceResult | None,
    tolerance: Decimal,
) -> ComparisonResult:
    if sap_price is None:
        return ComparisonResult(None, None, None, None, INVALID_SAP_PRICE)
    if not catalog_found:
        return ComparisonResult(sap_price, None, None, None, CATALOG_NOT_FOUND)
    if document_result is None or not document_result.found:
        return ComparisonResult(sap_price, None, None, None, DOCUMENT_PRICE_NOT_FOUND)
    if document_result.confidence == "AMBIGUOUS":
        return ComparisonResult(sap_price, document_result.document_price, None, None, AMBIGUOUS_DOCUMENT_PRICE)
    if document_result.confidence == "LOW":
        return ComparisonResult(sap_price, document_result.document_price, None, None, LOW_CONFIDENCE_DOCUMENT_PRICE)
    if document_result.document_value_type != NUMERIC_PRICE or document_result.document_price is None:
        return ComparisonResult(sap_price, None, None, None, NON_NUMERIC_DOCUMENT_VALUE)

    difference = sap_price - document_result.document_price
    absolute_difference = abs(difference)
    status = MATCH if absolute_difference <= tolerance else PRICE_DISCREPANCY
    return ComparisonResult(sap_price, document_result.document_price, difference, absolute_difference, status)
