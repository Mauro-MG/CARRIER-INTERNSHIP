from __future__ import annotations

from dataclasses import dataclass, field
from decimal import Decimal
from typing import Any

from services.docx_price_extractor import (
    BASE_UNIT_PRICED,
    INVALID_PRICE,
    NUMERIC_PRICE,
    STANDARD_OPTION,
    CatalogPriceExtractionResult,
    DecodedCatalogPosition,
    PriceExtractionDiagnostic,
    PricedOption,
)
from services.sap_input_parser import SAPPriceRecord


BASE_UNIT = "BASE_UNIT"
OPTION = "OPTION"

MATCH = "MATCH"
MISMATCH = "MISMATCH"
SAP_PRICE_MISSING = "SAP PRICE MISSING"
DOC_PRICE_MISSING = "DOC PRICE MISSING"
DOC_VALUE_NOT_NUMERIC = "DOC VALUE NOT NUMERIC"

ALL_PRICES_MATCH = "ALL PRICES MATCH"
PRICE_DIFFERENCES_FOUND = "PRICE DIFFERENCES FOUND"
REVIEW_REQUIRED = "REVIEW REQUIRED"

_CENT = Decimal("0.01")
_SKIPPED_OPTION_DIAGNOSTICS = {STANDARD_OPTION, INVALID_PRICE}


@dataclass(frozen=True)
class DocumentComparisonRecord:
    sequence: int
    record_type: str
    position: str
    code: str
    catalog_character: str | None = None
    description: str | None = None
    document_price: Decimal | None = None
    raw_document_price: str | None = None
    location: str | None = None
    diagnostic: str | None = None
    value_type: str | None = None


@dataclass(frozen=True)
class SAPComparisonRow:
    sequence: int
    tag: str | None
    position: str
    code: str
    sap_price: Decimal | None
    document_price: Decimal | None
    raw_document_price: str | None
    difference: Decimal | None
    result: str
    catalog_character: str | None = None
    description: str | None = None
    location: str | None = None
    diagnostic: str | None = None


@dataclass(frozen=True)
class SAPComparisonResult:
    rows: list[SAPComparisonRow]
    sap_row_count: int
    document_row_count: int
    match_count: int
    mismatch_count: int
    missing_sap_count: int
    missing_document_count: int
    nonnumeric_document_count: int
    all_match: bool
    overall_status: str


def build_document_comparison_records(
    extraction_result: CatalogPriceExtractionResult,
) -> list[DocumentComparisonRecord]:
    """Create the deterministic document sequence consumed by the SAP comparator."""
    records: list[DocumentComparisonRecord] = []
    records.append(_base_unit_record(extraction_result))

    consumed_option_indexes: set[int] = set()
    consumed_diagnostic_indexes: set[int] = set()

    for decoded in extraction_result.decoded_positions:
        option_indexes = [
            index
            for index, option in enumerate(extraction_result.priced_options)
            if index not in consumed_option_indexes and _option_matches_decoded(option, decoded)
        ]
        diagnostic_indexes = [
            index
            for index, diagnostic in enumerate(extraction_result.diagnostics)
            if index not in consumed_diagnostic_indexes and _diagnostic_matches_decoded(diagnostic, decoded)
        ]
        comparison_diagnostic_indexes = [
            index for index in diagnostic_indexes if not _skip_option_diagnostic(extraction_result.diagnostics[index])
        ]

        if option_indexes:
            for index in option_indexes:
                consumed_option_indexes.add(index)
                records.append(_option_record(extraction_result.priced_options[index]))
            consumed_diagnostic_indexes.update(diagnostic_indexes)
            for index in _document_value_diagnostic_indexes(extraction_result.diagnostics, comparison_diagnostic_indexes):
                consumed_diagnostic_indexes.add(index)
                records.append(_diagnostic_record(extraction_result.diagnostics[index], decoded))
            continue

        if diagnostic_indexes:
            consumed_diagnostic_indexes.update(diagnostic_indexes)
            selected_indexes = _document_value_diagnostic_indexes(extraction_result.diagnostics, comparison_diagnostic_indexes)
            if not selected_indexes and comparison_diagnostic_indexes:
                selected_indexes = [comparison_diagnostic_indexes[0]]
            for index in selected_indexes:
                records.append(_diagnostic_record(extraction_result.diagnostics[index], decoded))
            continue

        records.append(_missing_record(decoded, "document_price_missing"))

    return [
        DocumentComparisonRecord(
            sequence=index,
            record_type=record.record_type,
            position=record.position,
            code=record.code,
            catalog_character=record.catalog_character,
            description=record.description,
            document_price=record.document_price,
            raw_document_price=record.raw_document_price,
            location=record.location,
            diagnostic=record.diagnostic,
            value_type=record.value_type,
        )
        for index, record in enumerate(records, start=1)
    ]


def compare_sap_prices(
    sap_records: list[SAPPriceRecord],
    document_records: list[DocumentComparisonRecord],
) -> SAPComparisonResult:
    rows: list[SAPComparisonRow] = []
    max_rows = max(len(sap_records), len(document_records))

    for index in range(max_rows):
        sap_record = sap_records[index] if index < len(sap_records) else None
        document_record = document_records[index] if index < len(document_records) else None
        rows.append(_compare_row(index + 1, sap_record, document_record))

    match_count = sum(1 for row in rows if row.result == MATCH)
    mismatch_count = sum(1 for row in rows if row.result == MISMATCH)
    missing_sap_count = sum(1 for row in rows if row.result == SAP_PRICE_MISSING)
    missing_document_count = sum(1 for row in rows if row.result == DOC_PRICE_MISSING)
    nonnumeric_document_count = sum(1 for row in rows if row.result == DOC_VALUE_NOT_NUMERIC)
    structural_issue_count = missing_sap_count + missing_document_count + nonnumeric_document_count
    all_match = (
        len(sap_records) == len(document_records)
        and bool(rows)
        and match_count == len(rows)
        and structural_issue_count == 0
    )
    if all_match:
        overall_status = ALL_PRICES_MATCH
    elif mismatch_count:
        overall_status = PRICE_DIFFERENCES_FOUND
    else:
        overall_status = REVIEW_REQUIRED

    return SAPComparisonResult(
        rows=rows,
        sap_row_count=len(sap_records),
        document_row_count=len(document_records),
        match_count=match_count,
        mismatch_count=mismatch_count,
        missing_sap_count=missing_sap_count,
        missing_document_count=missing_document_count,
        nonnumeric_document_count=nonnumeric_document_count,
        all_match=all_match,
        overall_status=overall_status,
    )


def _compare_row(
    sequence: int,
    sap_record: SAPPriceRecord | None,
    document_record: DocumentComparisonRecord | None,
) -> SAPComparisonRow:
    if document_record is None:
        return SAPComparisonRow(
            sequence=sequence,
            tag=sap_record.tag if sap_record else None,
            position="",
            code="",
            sap_price=sap_record.price if sap_record else None,
            document_price=None,
            raw_document_price=None,
            difference=None,
            result=DOC_PRICE_MISSING,
        )

    if sap_record is None:
        return SAPComparisonRow(
            sequence=sequence,
            tag=None,
            position=document_record.position,
            code=document_record.code,
            sap_price=None,
            document_price=document_record.document_price,
            raw_document_price=document_record.raw_document_price,
            difference=None,
            result=SAP_PRICE_MISSING,
            catalog_character=document_record.catalog_character,
            description=document_record.description,
            location=document_record.location,
            diagnostic=document_record.diagnostic,
        )

    if document_record.document_price is None:
        result = DOC_VALUE_NOT_NUMERIC if document_record.raw_document_price else DOC_PRICE_MISSING
        return SAPComparisonRow(
            sequence=sequence,
            tag=sap_record.tag,
            position=document_record.position,
            code=document_record.code,
            sap_price=sap_record.price,
            document_price=None,
            raw_document_price=document_record.raw_document_price,
            difference=None,
            result=result,
            catalog_character=document_record.catalog_character,
            description=document_record.description,
            location=document_record.location,
            diagnostic=document_record.diagnostic,
        )

    sap_price = _money(sap_record.price)
    document_price = _money(document_record.document_price)
    difference = _money(sap_price - document_price)
    return SAPComparisonRow(
        sequence=sequence,
        tag=sap_record.tag,
        position=document_record.position,
        code=document_record.code,
        sap_price=sap_price,
        document_price=document_price,
        raw_document_price=document_record.raw_document_price,
        difference=difference,
        result=MATCH if difference == Decimal("0.00") else MISMATCH,
        catalog_character=document_record.catalog_character,
        description=document_record.description,
        location=document_record.location,
        diagnostic=document_record.diagnostic,
    )


def _base_unit_record(extraction_result: CatalogPriceExtractionResult) -> DocumentComparisonRecord:
    base = extraction_result.base_unit_result
    if base is None:
        return DocumentComparisonRecord(0, BASE_UNIT, "BASE", "BASE UNIT", diagnostic="base_unit_not_returned")
    value_type = _base_value_type(base)
    return DocumentComparisonRecord(
        sequence=0,
        record_type=BASE_UNIT,
        position="BASE",
        code="BASE UNIT",
        description=base.search_value,
        document_price=_money(base.price) if base.status == BASE_UNIT_PRICED and base.price is not None else None,
        raw_document_price=base.raw_value,
        location=base.location,
        diagnostic=None if base.status == BASE_UNIT_PRICED else base.status,
        value_type=value_type,
    )


def _option_record(option: PricedOption) -> DocumentComparisonRecord:
    return DocumentComparisonRecord(
        sequence=0,
        record_type=OPTION,
        position=str(option.position),
        code=option.search_token or option.catalog_code,
        catalog_character=option.catalog_character,
        description=option.description,
        document_price=_money(option.price),
        raw_document_price=option.raw_value,
        location=option.location,
        diagnostic=None,
        value_type=NUMERIC_PRICE,
    )


def _diagnostic_record(
    diagnostic: PriceExtractionDiagnostic,
    decoded: DecodedCatalogPosition,
) -> DocumentComparisonRecord:
    return DocumentComparisonRecord(
        sequence=0,
        record_type=OPTION,
        position=str(decoded.position),
        code=decoded.catalog_code or diagnostic.catalog_code or decoded.position_value,
        catalog_character=decoded.position_value,
        description=diagnostic.reason,
        document_price=None,
        raw_document_price=getattr(diagnostic, "raw_value", None),
        location=diagnostic.location,
        diagnostic=diagnostic.status,
        value_type=getattr(diagnostic, "value_type", None),
    )


def _missing_record(decoded: DecodedCatalogPosition, diagnostic: str) -> DocumentComparisonRecord:
    return DocumentComparisonRecord(
        sequence=0,
        record_type=OPTION,
        position=str(decoded.position),
        code=decoded.catalog_code or decoded.position_value,
        catalog_character=decoded.position_value,
        document_price=None,
        diagnostic=diagnostic,
    )


def _option_matches_decoded(option: PricedOption, decoded: DecodedCatalogPosition) -> bool:
    return (
        str(option.position) == str(decoded.position)
        and str(option.catalog_code) == str(decoded.catalog_code)
        and (option.catalog_character is None or option.catalog_character == decoded.position_value)
    )


def _diagnostic_matches_decoded(diagnostic: PriceExtractionDiagnostic, decoded: DecodedCatalogPosition) -> bool:
    return (
        str(diagnostic.position) == str(decoded.position)
        and str(diagnostic.catalog_code) == str(decoded.catalog_code)
        and (diagnostic.catalog_character is None or diagnostic.catalog_character == decoded.position_value)
    )


def _document_value_diagnostic_indexes(
    diagnostics: list[PriceExtractionDiagnostic],
    indexes: list[int],
) -> list[int]:
    return [
        index
        for index in indexes
        if getattr(diagnostics[index], "raw_value", None) or getattr(diagnostics[index], "value_type", None)
    ]


def _skip_option_diagnostic(diagnostic: PriceExtractionDiagnostic) -> bool:
    return diagnostic.status in _SKIPPED_OPTION_DIAGNOSTICS


def _base_value_type(base: Any) -> str | None:
    if base.price is not None:
        return NUMERIC_PRICE
    for match in base.matches or []:
        if match.raw_value == base.raw_value:
            return match.value_type
    return None


def _money(value: Decimal) -> Decimal:
    return Decimal(value).quantize(_CENT)
