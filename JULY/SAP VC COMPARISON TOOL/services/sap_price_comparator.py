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
NO_DOCUMENT_MATCH = "NO DOC MATCH"
NO_SAP_MATCH = "NO SAP MATCH"
DOC_VALUE_NOT_NUMERIC = "DOC VALUE NOT NUMERIC"

ALL_PRICES_MATCH = "ALL PRICES MATCH"
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
    record_id: str | None = None


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
    absolute_difference: Decimal | None = None
    sap_source_row: int | None = None
    document_record_id: str | None = None
    eligible_candidate_count: int = 0


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
    no_document_match_count: int = 0
    no_sap_match_count: int = 0
    ambiguous_match_count: int = 0


def build_document_comparison_records(
    extraction_result: CatalogPriceExtractionResult,
) -> list[DocumentComparisonRecord]:
    """Create stable DOC records; extraction order is metadata, not matching logic."""
    records: list[DocumentComparisonRecord] = []
    base_record = _base_unit_record(extraction_result)
    if base_record.document_price is not None or base_record.raw_document_price:
        records.append(base_record)

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
            for index in selected_indexes:
                records.append(_diagnostic_record(extraction_result.diagnostics[index], decoded))
            continue

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
            record_id=record.record_id or f"document-{index}",
        )
        for index, record in enumerate(records, start=1)
    ]


def compare_sap_prices(
    sap_records: list[SAPPriceRecord],
    document_records: list[DocumentComparisonRecord],
) -> SAPComparisonResult:
    numeric_documents = [record for record in document_records if record.document_price is not None]
    nonnumeric_documents = [record for record in document_records if record.document_price is None]
    assignments, candidate_counts = _minimum_cost_maximum_matching(sap_records, numeric_documents)
    matched_document_indexes = set(assignments.values())
    rows: list[SAPComparisonRow] = []

    # Display remains SAP-driven, but assignments were computed independently of paste order.
    for display_sequence, sap_record in enumerate(sap_records, start=1):
        sap_index = display_sequence - 1
        document_index = assignments.get(sap_index)
        if document_index is None:
            rows.append(_unmatched_sap_row(display_sequence, sap_record, candidate_counts[sap_index]))
        else:
            rows.append(
                _matched_row(
                    display_sequence,
                    sap_record,
                    numeric_documents[document_index],
                    candidate_counts[sap_index],
                )
            )

    for document_index, document_record in enumerate(numeric_documents):
        if document_index not in matched_document_indexes:
            rows.append(_unmatched_document_row(len(rows) + 1, document_record, NO_SAP_MATCH))
    for document_record in nonnumeric_documents:
        rows.append(_unmatched_document_row(len(rows) + 1, document_record, DOC_VALUE_NOT_NUMERIC))

    match_count = len(assignments)
    no_document_match_count = len(sap_records) - match_count
    no_sap_match_count = len(numeric_documents) - match_count
    nonnumeric_document_count = len(nonnumeric_documents)
    ambiguous_match_count = sum(1 for row in rows if row.result == MATCH and row.eligible_candidate_count > 1)
    all_match = bool(sap_records or numeric_documents) and no_document_match_count == 0 and no_sap_match_count == 0
    overall_status = ALL_PRICES_MATCH if all_match else REVIEW_REQUIRED

    return SAPComparisonResult(
        rows=rows,
        sap_row_count=len(sap_records),
        document_row_count=len(numeric_documents),
        match_count=match_count,
        mismatch_count=0,
        missing_sap_count=no_sap_match_count,
        missing_document_count=no_document_match_count,
        nonnumeric_document_count=nonnumeric_document_count,
        all_match=all_match,
        overall_status=overall_status,
        no_document_match_count=no_document_match_count,
        no_sap_match_count=no_sap_match_count,
        ambiguous_match_count=ambiguous_match_count,
    )


def _matched_row(
    sequence: int,
    sap_record: SAPPriceRecord,
    document_record: DocumentComparisonRecord,
    candidate_count: int,
) -> SAPComparisonRow:
    sap_price = Decimal(sap_record.price)
    document_price = Decimal(document_record.document_price)
    difference = sap_price - document_price
    return SAPComparisonRow(
        sequence=sequence,
        tag=sap_record.tag,
        position=document_record.position,
        code=document_record.code,
        sap_price=sap_price,
        document_price=document_price,
        raw_document_price=document_record.raw_document_price,
        difference=difference,
        result=MATCH,
        catalog_character=document_record.catalog_character,
        description=document_record.description,
        location=document_record.location,
        diagnostic=(
            "duplicate_price_assignment" if candidate_count > 1 else document_record.diagnostic
        ),
        absolute_difference=abs(difference),
        sap_source_row=sap_record.source_row,
        document_record_id=document_record.record_id or f"document-{document_record.sequence}",
        eligible_candidate_count=candidate_count,
    )


def _unmatched_sap_row(sequence: int, sap_record: SAPPriceRecord, candidate_count: int) -> SAPComparisonRow:
    return SAPComparisonRow(
        sequence=sequence,
        tag=sap_record.tag,
        position="",
        code="",
        sap_price=Decimal(sap_record.price),
        document_price=None,
        raw_document_price=None,
        difference=None,
        result=NO_DOCUMENT_MATCH,
        sap_source_row=sap_record.source_row,
        eligible_candidate_count=candidate_count,
    )


def _unmatched_document_row(
    sequence: int,
    document_record: DocumentComparisonRecord,
    result: str,
) -> SAPComparisonRow:
    return SAPComparisonRow(
        sequence=sequence,
        tag=None,
        position=document_record.position,
        code=document_record.code,
        sap_price=None,
        document_price=document_record.document_price,
        raw_document_price=document_record.raw_document_price,
        difference=None,
        result=result,
        catalog_character=document_record.catalog_character,
        description=document_record.description,
        location=document_record.location,
        diagnostic=document_record.diagnostic,
        document_record_id=document_record.record_id or f"document-{document_record.sequence}",
    )


@dataclass
class _FlowEdge:
    to: int
    reverse: int
    capacity: int
    cost: Decimal
    sap_index: int | None = None
    document_index: int | None = None


def _minimum_cost_maximum_matching(
    sap_records: list[SAPPriceRecord],
    document_records: list[DocumentComparisonRecord],
) -> tuple[dict[int, int], list[int]]:
    """Return a maximum-cardinality one-to-one match with minimum total difference.

    Equal-cost alternatives are deterministic: SAP nodes are ordered by stable tag/price
    identity and DOC nodes by extraction order. Tags never affect match eligibility.
    """
    candidate_counts = [
        sum(1 for document in document_records if _eligible(sap.price, document.document_price))
        for sap in sap_records
    ]
    if not sap_records or not document_records:
        return {}, candidate_counts

    sap_order = sorted(
        range(len(sap_records)),
        key=lambda index: (
            sap_records[index].tag.casefold(),
            Decimal(sap_records[index].price),
            sap_records[index].source_row,
            index,
        ),
    )
    document_order = sorted(
        range(len(document_records)),
        key=lambda index: (
            document_records[index].sequence,
            document_records[index].record_id or "",
            document_records[index].position,
            document_records[index].code,
            index,
        ),
    )
    source = 0
    sap_offset = 1
    document_offset = sap_offset + len(sap_order)
    sink = document_offset + len(document_order)
    graph: list[list[_FlowEdge]] = [[] for _ in range(sink + 1)]
    candidate_edges: list[_FlowEdge] = []

    def add_edge(
        start: int,
        end: int,
        cost: Decimal,
        *,
        sap_index: int | None = None,
        document_index: int | None = None,
    ) -> _FlowEdge:
        forward = _FlowEdge(end, len(graph[end]), 1, cost, sap_index, document_index)
        reverse = _FlowEdge(start, len(graph[start]), 0, -cost)
        graph[start].append(forward)
        graph[end].append(reverse)
        return forward

    for sap_rank, sap_index in enumerate(sap_order):
        add_edge(source, sap_offset + sap_rank, Decimal("0"))
        for document_rank, document_index in enumerate(document_order):
            absolute_difference = abs(
                Decimal(sap_records[sap_index].price) - Decimal(document_records[document_index].document_price)
            )
            if absolute_difference < _CENT:
                candidate_edges.append(
                    add_edge(
                        sap_offset + sap_rank,
                        document_offset + document_rank,
                        absolute_difference,
                        sap_index=sap_index,
                        document_index=document_index,
                    )
                )
    for document_rank in range(len(document_order)):
        add_edge(document_offset + document_rank, sink, Decimal("0"))

    # Bellman-Ford supports the negative residual edges used to improve prior choices.
    while True:
        distances: list[Decimal | None] = [None] * len(graph)
        previous: list[tuple[int, int] | None] = [None] * len(graph)
        distances[source] = Decimal("0")
        for _ in range(len(graph) - 1):
            changed = False
            for node, edges in enumerate(graph):
                if distances[node] is None:
                    continue
                for edge_index, edge in enumerate(edges):
                    if edge.capacity == 0:
                        continue
                    candidate_distance = distances[node] + edge.cost
                    if distances[edge.to] is None or candidate_distance < distances[edge.to]:
                        distances[edge.to] = candidate_distance
                        previous[edge.to] = (node, edge_index)
                        changed = True
            if not changed:
                break
        if previous[sink] is None:
            break
        node = sink
        while node != source:
            prior_node, edge_index = previous[node]
            edge = graph[prior_node][edge_index]
            edge.capacity = 0
            graph[node][edge.reverse].capacity = 1
            node = prior_node

    assignments = {
        edge.sap_index: edge.document_index
        for edge in candidate_edges
        if edge.capacity == 0 and edge.sap_index is not None and edge.document_index is not None
    }
    return assignments, candidate_counts


def _eligible(sap_price: Decimal, document_price: Decimal | None) -> bool:
    return document_price is not None and abs(Decimal(sap_price) - Decimal(document_price)) < _CENT


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
        document_price=Decimal(base.price) if base.status == BASE_UNIT_PRICED and base.price is not None else None,
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
        document_price=Decimal(option.price),
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
