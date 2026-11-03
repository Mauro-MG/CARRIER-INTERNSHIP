from __future__ import annotations

import re
import zipfile
import xml.etree.ElementTree as ET
from dataclasses import asdict, dataclass, field
from decimal import Decimal
from pathlib import Path
from typing import Any

from services.base_unit_resolver import FULL_SEARCH, RANGE_SEARCH, resolve_base_unit_search
from services.condenser_compatibility import (
    ALL_CONDENSERS,
    format_condenser_families,
    is_condenser_compatible,
    normalize_condenser_family,
    parse_document_condenser_compatibility,
)
from services.price_parser import (
    DASH,
    INCLUDED,
    NO_CHARGE,
    NONE_VALUE,
    NOT_AVAILABLE,
    NUMERIC_PRICE,
    STANDARD,
    parse_document_value,
)
from services.search_token_resolver import CODE_BASED, CHARACTER_BASED, get_search_mode, resolve_position_search_tokens


STANDARD_OPTION = "standard_option"
POSITION_HEADING_NOT_FOUND = "position_heading_not_found"
TABLE_NOT_FOUND = "table_not_found"
CODE_NOT_FOUND = "code_not_found"
CHARACTER_NOT_FOUND = "character_not_found"
INVALID_PRICE = "invalid_price"
CONDENSER_MISMATCH = "condenser_mismatch"
STRUCTURE_MISMATCH = CONDENSER_MISMATCH
MATRIX_MAPPING_NOT_FOUND = "matrix_mapping_not_found"
BASE_UNIT_RULE_NOT_CONFIGURED = "base_unit_rule_not_configured"
BASE_UNIT_RULE_INVALID = "base_unit_rule_invalid"
BASE_UNIT_RESOLUTION_FAILED = "base_unit_resolution_failed"
BASE_UNIT_NOT_FOUND = "base_unit_not_found"
BASE_UNIT_PRICE_COLUMN_NOT_FOUND = "base_unit_price_column_not_found"
BASE_UNIT_INVALID_PRICE = "base_unit_invalid_price"
AMBIGUOUS_BASE_UNIT_MATCH = "ambiguous_base_unit_match"
BASE_UNIT_PRICED = "base_unit_priced"

_WORD_NS = {"w": "http://schemas.openxmlformats.org/wordprocessingml/2006/main"}
_POSITION_HEADING_RE = re.compile(r"\bPositions?\s+(\d{1,2})(?:\s*[-\u2013\u2014]\s*(\d{1,2}))?\b", re.IGNORECASE)
_SIZE_TOKEN_RE = re.compile(r"^(\d{3})(?:[-\u2013\u2014](\d{3}))?$")
_CATALOG_CONDITION_RE = re.compile(r"\{\s*(\d{1,3})\s*\}\s*=\s*([A-Za-z0-9_\-\u2013\u2014]+)", re.IGNORECASE)


@dataclass(frozen=True)
class DecodedCatalogPosition:
    position: str
    start_position: int
    end_position: int
    position_value: str
    catalog_code: str
    source_mode: str = CODE_BASED


@dataclass(frozen=True)
class ExtractedDocxTableRow:
    row_number: int
    raw_cells: list[str]
    normalized_cells: list[str]


@dataclass(frozen=True)
class DocxPositionTable:
    table_number: int
    heading: str
    position: str
    start_position: int
    end_position: int
    rows: list[ExtractedDocxTableRow]


@dataclass(frozen=True)
class ExtractedDocxTable:
    table_number: int
    heading: str
    rows: list[ExtractedDocxTableRow]


@dataclass(frozen=True)
class PricedOption:
    position: str
    catalog_code: str
    description: str
    price: Decimal
    location: str
    table_heading: str
    condenser_type: str | None
    raw_value: str
    catalog_character: str | None = None
    search_mode: str = CODE_BASED
    search_token: str | None = None
    product_family: str | None = None
    document_condenser_compatibility: str | None = None
    normalized_condenser_families: list[str] = field(default_factory=list)

    def to_dict(self) -> dict[str, Any]:
        result = asdict(self)
        result["price"] = str(self.price)
        return result


@dataclass(frozen=True)
class PriceExtractionDiagnostic:
    position: str
    catalog_code: str
    status: str
    reason: str
    location: str | None = None
    table_heading: str | None = None
    catalog_character: str | None = None
    search_mode: str = CODE_BASED
    search_token: str | None = None
    product_family: str | None = None
    document_condenser_compatibility: str | None = None
    normalized_condenser_families: list[str] = field(default_factory=list)
    raw_value: str | None = None
    value_type: str | None = None


@dataclass(frozen=True)
class BaseUnitPriceMatch:
    table_number: int
    row_number: int
    cell_number: int
    table_heading: str
    raw_value: str
    value_type: str
    price: Decimal | None
    master_price_column: int | None
    row_text: str
    reason: str

    def to_dict(self) -> dict[str, Any]:
        result = asdict(self)
        result["price"] = str(self.price) if self.price is not None else None
        return result


@dataclass(frozen=True)
class BaseUnitPriceResult:
    enabled: bool
    source_catalog_number: str
    search_type: str | None
    configured_range: str | None
    template: str | None
    search_value: str | None
    found: bool
    status: str
    reason: str
    price: Decimal | None
    raw_value: str | None
    location: str | None
    table_heading: str | None
    table_number: int | None
    row_number: int | None
    cell_number: int | None
    tables_searched: int
    matching_tables: int
    matches: list[BaseUnitPriceMatch]

    def to_dict(self) -> dict[str, Any]:
        result = asdict(self)
        result["price"] = str(self.price) if self.price is not None else None
        result["matches"] = [match.to_dict() for match in self.matches]
        return result


@dataclass(frozen=True)
class CatalogPriceExtractionResult:
    priced_options: list[PricedOption]
    diagnostics: list[PriceExtractionDiagnostic]
    decoded_positions: list[DecodedCatalogPosition]
    tables: list[DocxPositionTable]
    search_mode: str = CODE_BASED
    base_unit_result: BaseUnitPriceResult | None = None

    def to_dict(self) -> dict[str, Any]:
        return {
            "priced_options": [item.to_dict() for item in self.priced_options],
            "diagnostics": [asdict(item) for item in self.diagnostics],
            "decoded_positions": [asdict(item) for item in self.decoded_positions],
            "search_mode": self.search_mode,
            "tables": [
                {
                    "table_number": table.table_number,
                    "heading": table.heading,
                    "position": table.position,
                    "start_position": table.start_position,
                    "end_position": table.end_position,
                    "rows": [asdict(row) for row in table.rows],
                }
                for table in self.tables
            ],
            "base_unit_result": self.base_unit_result.to_dict() if self.base_unit_result else None,
        }


@dataclass(frozen=True)
class _Heading:
    heading: str
    start_position: int
    end_position: int


@dataclass(frozen=True)
class _ColumnLayout:
    description_column: int
    token_column: int
    voltage_column: int | None
    condenser_column: int | None
    price_columns: dict[int, str]


@dataclass(frozen=True)
class _MatchedValue:
    table: DocxPositionTable
    row: ExtractedDocxTableRow
    catalog_code: str
    description: str
    raw_value: str
    value_type: str
    decimal_value: Decimal | None
    product_family: str | None
    raw_condenser_compatibility: str | None
    normalized_condenser_families: list[str]
    condenser_compatible: bool


@dataclass(frozen=True)
class _CondenserCompatibility:
    raw_value: str
    families: set[str]


@dataclass(frozen=True)
class _CatalogCondition:
    source_text: str
    position: int
    expected_value: str


def extract_catalog_prices(
    docx_path: str | Path,
    catalog_number: str,
    configuration: dict[str, Any],
) -> CatalogPriceExtractionResult:
    base_unit_result = extract_base_unit_price(docx_path, catalog_number, configuration)
    search_mode = get_search_mode(configuration)
    tables = extract_position_tables(docx_path)
    heading_ranges = {(table.start_position, table.end_position) for table in tables}
    decoded_positions = decode_catalog_positions(catalog_number, configuration)
    product_context = _build_product_context(catalog_number, configuration)
    conditional_price_rules = configuration.get("conditional_price_rules")

    priced_options: list[PricedOption] = []
    diagnostics: list[PriceExtractionDiagnostic] = []

    for decoded in decoded_positions:
        if not decoded.catalog_code:
            diagnostics.append(
                PriceExtractionDiagnostic(
                    position=decoded.position,
                    catalog_code=decoded.position_value,
                    status=MATRIX_MAPPING_NOT_FOUND,
                    reason=(
                        f"Catalog character {decoded.position_value!r} at Position {decoded.position} is not assigned "
                        "to any option-code column in the saved matrix."
                    ),
                    catalog_character=decoded.position_value,
                    search_mode=decoded.source_mode,
                )
            )
            continue

        position_tables = _tables_for_decoded_position(decoded, tables)
        if not position_tables:
            status = TABLE_NOT_FOUND if _has_covering_heading(decoded, heading_ranges) else POSITION_HEADING_NOT_FOUND
            diagnostics.append(
                PriceExtractionDiagnostic(
                    position=decoded.position,
                    catalog_code=decoded.catalog_code,
                    status=status,
                    reason=f"No DOCX pricing table was found covering Position {decoded.position}.",
                    catalog_character=decoded.position_value,
                    search_mode=decoded.source_mode,
                    search_token=decoded.catalog_code,
                )
            )
            continue

        matches = find_option_values(
            position_tables,
            decoded.catalog_code,
            product_context,
            current_position=decoded.start_position,
            conditional_price_rules=conditional_price_rules,
        )
        if not matches:
            status = CHARACTER_NOT_FOUND if decoded.source_mode == CHARACTER_BASED else CODE_NOT_FOUND
            reason = (
                f"Character {decoded.catalog_code!r} was not found as an exact option token in the DOCX Position {decoded.position} table."
                if decoded.source_mode == CHARACTER_BASED
                else f"No exact option-code match was found in the DOCX Position {decoded.position} table."
            )
            diagnostics.append(
                PriceExtractionDiagnostic(
                    position=decoded.position,
                    catalog_code=decoded.catalog_code,
                    status=status,
                    reason=reason,
                    location=_table_location(position_tables[0]),
                    table_heading=position_tables[0].heading,
                    catalog_character=decoded.position_value,
                    search_mode=decoded.source_mode,
                    search_token=decoded.catalog_code,
                )
            )
            continue

        compatible_matches = [match for match in matches if match.condenser_compatible]
        if not compatible_matches:
            first = matches[0]
            diagnostics.append(
                PriceExtractionDiagnostic(
                    position=decoded.position,
                    catalog_code=decoded.catalog_code,
                    status=CONDENSER_MISMATCH,
                    reason=(
                        f"Option code {decoded.catalog_code} was found, but this row applies to "
                        f"{format_condenser_families(set(first.normalized_condenser_families))} and the analyzed "
                        f"product is {product_context.get('product_family') or 'unknown'}."
                    ),
                    location=_table_location(first.table),
                    table_heading=first.table.heading,
                    catalog_character=decoded.position_value,
                    search_mode=decoded.source_mode,
                    search_token=decoded.catalog_code,
                    product_family=product_context.get("product_family"),
                    document_condenser_compatibility=first.raw_condenser_compatibility,
                    normalized_condenser_families=first.normalized_condenser_families,
                )
            )
            continue

        for match in compatible_matches:
            if match.value_type == NUMERIC_PRICE and match.decimal_value is not None:
                priced_options.append(
                    PricedOption(
                        position=decoded.position,
                        catalog_code=decoded.catalog_code,
                        description=match.description,
                        price=match.decimal_value,
                        location=_table_location(match.table),
                        table_heading=match.table.heading,
                        condenser_type=product_context.get("product_family"),
                        raw_value=match.raw_value,
                        catalog_character=decoded.position_value,
                        search_mode=decoded.source_mode,
                        search_token=decoded.catalog_code,
                        product_family=product_context.get("product_family"),
                        document_condenser_compatibility=match.raw_condenser_compatibility,
                        normalized_condenser_families=match.normalized_condenser_families,
                    )
                )
            elif match.value_type in {STANDARD, INCLUDED, NO_CHARGE, NOT_AVAILABLE, NONE_VALUE, DASH}:
                diagnostics.append(
                    PriceExtractionDiagnostic(
                        position=decoded.position,
                        catalog_code=decoded.catalog_code,
                        status=STANDARD_OPTION,
                        reason=f"The matching DOCX row contains {match.raw_value or 'a nonnumeric standard/included value'}.",
                        location=_table_location(match.table),
                        table_heading=match.table.heading,
                        catalog_character=decoded.position_value,
                        search_mode=decoded.source_mode,
                        search_token=decoded.catalog_code,
                        product_family=product_context.get("product_family"),
                        document_condenser_compatibility=match.raw_condenser_compatibility,
                        normalized_condenser_families=match.normalized_condenser_families,
                        raw_value=match.raw_value,
                        value_type=match.value_type,
                    )
                )
            else:
                diagnostics.append(
                    PriceExtractionDiagnostic(
                        position=decoded.position,
                        catalog_code=decoded.catalog_code,
                        status=INVALID_PRICE,
                        reason=f"The matching DOCX row does not contain a valid document value: {match.raw_value!r}.",
                        location=_table_location(match.table),
                        table_heading=match.table.heading,
                        catalog_character=decoded.position_value,
                        search_mode=decoded.source_mode,
                        search_token=decoded.catalog_code,
                        product_family=product_context.get("product_family"),
                        document_condenser_compatibility=match.raw_condenser_compatibility,
                        normalized_condenser_families=match.normalized_condenser_families,
                        raw_value=match.raw_value,
                        value_type=match.value_type,
                    )
                )

    return CatalogPriceExtractionResult(priced_options, diagnostics, decoded_positions, tables, search_mode, base_unit_result)


def extract_base_unit_price(
    docx_path: str | Path,
    catalog_number: str,
    configuration: dict[str, Any],
) -> BaseUnitPriceResult:
    rule = configuration.get("base_unit_price_rule")
    source_catalog = str(catalog_number or "").strip().upper()
    if not isinstance(rule, dict) or not rule.get("enabled"):
        return _base_unit_result(
            enabled=False,
            source_catalog_number=source_catalog,
            search_type=None,
            rule=rule if isinstance(rule, dict) else None,
            status=BASE_UNIT_RULE_NOT_CONFIGURED,
            reason="Base Unit Master Price extraction is not enabled for this product configuration.",
        )

    resolution = resolve_base_unit_search(source_catalog, rule)
    if not resolution.success or not resolution.search_value:
        status = BASE_UNIT_RULE_INVALID if "must" in (resolution.error or "").lower() else BASE_UNIT_RESOLUTION_FAILED
        return _base_unit_result(
            enabled=True,
            source_catalog_number=source_catalog,
            search_type=resolution.search_type,
            rule=rule,
            status=status,
            reason=resolution.error or "Base unit search value could not be resolved.",
        )

    tables = extract_all_docx_tables(docx_path)
    search_value = resolution.search_value
    matches: list[BaseUnitPriceMatch] = []
    search_rows_found = 0
    matched_table_numbers: set[int] = set()

    for table in tables:
        price_column = _find_master_price_column(table)
        for row in table.rows:
            cell_index = _find_exact_base_unit_cell(row.raw_cells, search_value)
            if cell_index is None:
                continue
            search_rows_found += 1
            matched_table_numbers.add(table.table_number)
            if price_column is None:
                continue
            raw_value = _document_value_from_cell(_cell_at(row.raw_cells, price_column))
            parsed = parse_document_value(raw_value)
            matches.append(
                BaseUnitPriceMatch(
                    table_number=table.table_number,
                    row_number=row.row_number,
                    cell_number=cell_index + 1,
                    table_heading=table.heading,
                    raw_value=raw_value,
                    value_type=parsed.value_type,
                    price=parsed.decimal_value,
                    master_price_column=price_column + 1,
                    row_text=_normalize_cell_text(" | ".join(row.raw_cells)),
                    reason="Exact base-unit value found in a table row with a detected Master Price column.",
                )
            )

    matching_tables = len(matched_table_numbers)
    if not search_rows_found:
        return _base_unit_result(
            enabled=True,
            source_catalog_number=source_catalog,
            search_type=resolution.search_type,
            rule=rule,
            search_value=search_value,
            status=BASE_UNIT_NOT_FOUND,
            reason=f'Derived base-unit search value "{search_value}" was not found in any DOCX table.',
            tables_searched=len(tables),
        )

    if not matches:
        return _base_unit_result(
            enabled=True,
            source_catalog_number=source_catalog,
            search_type=resolution.search_type,
            rule=rule,
            search_value=search_value,
            status=BASE_UNIT_PRICE_COLUMN_NOT_FOUND,
            reason=f'Derived base-unit search value "{search_value}" was found, but no Master Price column was detected in the matching table(s).',
            tables_searched=len(tables),
            matching_tables=matching_tables,
        )

    numeric_matches = [match for match in matches if match.value_type == NUMERIC_PRICE and match.price is not None]
    if not numeric_matches:
        first = matches[0]
        return _base_unit_result(
            enabled=True,
            source_catalog_number=source_catalog,
            search_type=resolution.search_type,
            rule=rule,
            search_value=search_value,
            status=BASE_UNIT_INVALID_PRICE,
            reason=f'The base-unit row was found, but the Master Price value {first.raw_value!r} is not numeric.',
            tables_searched=len(tables),
            matching_tables=matching_tables,
            matches=matches,
            selected=first,
        )

    distinct_prices = {match.price for match in numeric_matches}
    if len(distinct_prices) > 1:
        return _base_unit_result(
            enabled=True,
            source_catalog_number=source_catalog,
            search_type=resolution.search_type,
            rule=rule,
            search_value=search_value,
            status=AMBIGUOUS_BASE_UNIT_MATCH,
            reason=f'Derived base-unit search value "{search_value}" matched multiple credible Master Price values.',
            tables_searched=len(tables),
            matching_tables=matching_tables,
            matches=matches,
            selected=numeric_matches[0],
        )

    selected = numeric_matches[0]
    return _base_unit_result(
        enabled=True,
        source_catalog_number=source_catalog,
        search_type=resolution.search_type,
        rule=rule,
        search_value=search_value,
        status=BASE_UNIT_PRICED,
        reason=f'Derived base-unit search value "{search_value}" matched a DOCX row with a Master Price column.',
        tables_searched=len(tables),
        matching_tables=matching_tables,
        matches=matches,
        selected=selected,
    )


def decode_catalog_positions(catalog_number: str, configuration: dict[str, Any]) -> list[DecodedCatalogPosition]:
    decoded: list[DecodedCatalogPosition] = []

    for token in resolve_position_search_tokens(catalog_number, configuration):
        decoded.append(
            DecodedCatalogPosition(
                position=str(token.position),
                start_position=token.position,
                end_position=token.position,
                position_value=token.catalog_character,
                catalog_code=token.search_token,
                source_mode=token.source_mode,
            )
        )
    return decoded


def extract_position_tables(docx_path: str | Path) -> list[DocxPositionTable]:
    body = _load_document_body(docx_path)
    active_heading: _Heading | None = None
    tables_since_heading = 0
    tables: list[DocxPositionTable] = []
    table_number = 0

    for child in list(body):
        tag_name = _local_name(child.tag)
        if tag_name == "p":
            text = _paragraph_text(child)
            heading = _heading_from_text(text)
            if heading:
                active_heading = heading
                tables_since_heading = 0
            elif text and tables_since_heading > 0:
                active_heading = None
                tables_since_heading = 0
            continue
        if tag_name != "tbl":
            continue

        table_number += 1
        if active_heading is None:
            continue
        rows = _extract_rows(child)
        if not rows or not _looks_like_pricing_table(rows):
            continue
        tables_since_heading += 1
        tables.append(
            DocxPositionTable(
                table_number=table_number,
                heading=active_heading.heading,
                position=_position_key(active_heading.start_position, active_heading.end_position),
                start_position=active_heading.start_position,
                end_position=active_heading.end_position,
                rows=rows,
            )
        )
    return tables


def extract_all_docx_tables(docx_path: str | Path) -> list[ExtractedDocxTable]:
    body = _load_document_body(docx_path)
    tables: list[ExtractedDocxTable] = []
    table_number = 0
    current_heading = ""

    for child in list(body):
        tag_name = _local_name(child.tag)
        if tag_name == "p":
            text = _paragraph_text(child)
            if text:
                current_heading = text
            continue
        if tag_name != "tbl":
            continue

        table_number += 1
        rows = _extract_rows(child)
        if rows:
            tables.append(ExtractedDocxTable(table_number=table_number, heading=current_heading, rows=rows))
    return tables


def find_option_values(
    position_tables: list[DocxPositionTable],
    option_code: str,
    product_context: dict[str, Any],
    *,
    current_position: int | None = None,
    conditional_price_rules: Any = None,
) -> list[_MatchedValue]:
    normalized_code = normalize_option_code(option_code)
    matches: list[_MatchedValue] = []
    product_family = product_context.get("product_family") or product_context.get("condenser_type")
    catalog_number = str(product_context.get("catalog_number") or "")
    use_catalog_conditions = _conditional_price_rules_enabled(conditional_price_rules, current_position)

    for table in position_tables:
        layout = _infer_column_layout(table)
        if layout is None:
            continue

        row_index = 0
        while row_index < len(table.rows):
            row = table.rows[row_index]
            search_text = _cell_at(row.raw_cells, layout.token_column)
            if not _cell_has_exact_option_code(search_text, normalized_code):
                row_index += 1
                continue

            grouped_rows = _row_group_for_option(table.rows, row_index, layout, include_catalog_conditions=use_catalog_conditions)
            compatibility = _condenser_compatibility_for_group(grouped_rows, layout)
            if not is_condenser_compatible(product_family, compatibility.raw_value):
                matches.append(
                    _MatchedValue(
                        table=table,
                        row=grouped_rows[0],
                        catalog_code=option_code,
                        description=_group_description(grouped_rows, layout),
                        raw_value="",
                        value_type="",
                        decimal_value=None,
                        product_family=normalize_condenser_family(product_family or ""),
                        raw_condenser_compatibility=compatibility.raw_value,
                        normalized_condenser_families=sorted(compatibility.families),
                        condenser_compatible=False,
                    )
                )
                row_index += max(1, len(grouped_rows))
                continue

            candidate_rows = (
                _select_rows_for_catalog_conditions(grouped_rows, catalog_number)
                if use_catalog_conditions
                else grouped_rows
            )
            if not candidate_rows:
                row_index += max(1, len(grouped_rows))
                continue

            selected_row = _select_row_for_voltage(candidate_rows, layout, product_context.get("voltage_label"))
            size_column = _select_size_column(layout.price_columns, product_context.get("size_code"))
            if size_column is None:
                row_index += max(1, len(grouped_rows))
                continue
            raw_value = _document_value_from_cell(_cell_at(selected_row.raw_cells, size_column))
            parsed = parse_document_value(raw_value)
            matches.append(
                _MatchedValue(
                    table=table,
                    row=selected_row,
                    catalog_code=option_code,
                    description=_group_description(grouped_rows, layout),
                    raw_value=raw_value,
                    value_type=parsed.value_type,
                    decimal_value=parsed.decimal_value,
                    product_family=normalize_condenser_family(product_family or ""),
                    raw_condenser_compatibility=compatibility.raw_value,
                    normalized_condenser_families=sorted(compatibility.families),
                    condenser_compatible=True,
                )
            )
            row_index += max(1, len(grouped_rows))
    return matches


def normalize_option_code(value: str) -> str:
    return re.sub(r"\s+", "", str(value or "").strip().upper())


def validate_condenser_structure(row: ExtractedDocxTableRow, required_structure: str | None) -> bool:
    return is_condenser_compatible(required_structure, " ".join(row.normalized_cells))


def _load_document_body(docx_path: str | Path) -> ET.Element:
    try:
        with zipfile.ZipFile(docx_path) as archive:
            document_xml = archive.read("word/document.xml")
    except (OSError, KeyError, zipfile.BadZipFile) as exc:
        raise ValueError("The uploaded file is not a readable DOCX document.") from exc
    root = ET.fromstring(document_xml)
    body = root.find("w:body", _WORD_NS)
    if body is None:
        raise ValueError("The DOCX document body could not be found.")
    return body


def _extract_rows(table_element: ET.Element) -> list[ExtractedDocxTableRow]:
    rows: list[ExtractedDocxTableRow] = []
    for row_number, table_row in enumerate(table_element.findall("w:tr", _WORD_NS), start=1):
        raw_cells = [_cell_text(cell) for cell in table_row.findall("w:tc", _WORD_NS)]
        if any(cell.strip() for cell in raw_cells):
            rows.append(
                ExtractedDocxTableRow(
                    row_number=row_number,
                    raw_cells=raw_cells,
                    normalized_cells=[_normalize_cell_text(cell) for cell in raw_cells],
                )
            )
    return rows


def _paragraph_text(paragraph: ET.Element) -> str:
    return " ".join("".join(text.text or "" for text in paragraph.findall(".//w:t", _WORD_NS)).split())


def _cell_text(cell: ET.Element) -> str:
    paragraphs: list[str] = []
    for paragraph in cell.findall(".//w:p", _WORD_NS):
        text = _paragraph_text(paragraph)
        if text:
            paragraphs.append(text)
    return "\n".join(paragraphs)


def _heading_from_text(text: str) -> _Heading | None:
    match = _POSITION_HEADING_RE.search(text)
    if not match:
        return None
    normalized = text.strip().upper()
    if not normalized.startswith("POSITION") and not re.search(r"\(\s*POSITIONS?\s+\d{1,2}", normalized):
        return None
    start_position = int(match.group(1))
    end_position = int(match.group(2) or start_position)
    return _Heading(text, start_position, end_position)


def _looks_like_pricing_table(rows: list[ExtractedDocxTableRow]) -> bool:
    first_rows_text = " ".join(" ".join(row.normalized_cells).upper() for row in rows[:3])
    return "MASTER" in first_rows_text and "PRICE" in first_rows_text


def _infer_column_layout(table: DocxPositionTable) -> _ColumnLayout | None:
    for index, row in enumerate(table.rows[:4]):
        cells = [cell.upper() for cell in row.normalized_cells]
        description_column = _find_cell_containing(cells, "DESCRIPTION")
        token_column = _find_option_token_column(cells)
        if token_column is None:
            if description_column is None:
                continue
            token_column = description_column
        if description_column is None:
            description_column = token_column
        voltage_column = _find_cell_containing(cells, "VOLTAGE")
        condenser_column = _find_cell_containing(cells, "CONDENSER")
        price_columns: dict[int, str] = {}

        for header_row in table.rows[index : min(len(table.rows), index + 3)]:
            for cell_index, cell in enumerate(header_row.normalized_cells):
                if _cell_contains_size_header(cell):
                    price_columns[cell_index] = cell
            if price_columns:
                break

        if not price_columns:
            price_column = _last_table_column(table)
            if price_column is None:
                price_column = _find_cell_containing(cells, "MASTER PRICE")
            if price_column is None:
                price_column = len(row.raw_cells) - 1
            price_columns[price_column] = "ALL"

        return _ColumnLayout(description_column, token_column, voltage_column, condenser_column, price_columns)
    return None


def _select_size_column(price_columns: dict[int, str], size_code: str | None) -> int | None:
    if not price_columns:
        return None
    if len(price_columns) == 1:
        return next(iter(price_columns))
    if not size_code:
        return min(price_columns)
    try:
        target_size = int(size_code)
    except ValueError:
        return min(price_columns)
    for column_index, header in price_columns.items():
        if _size_header_includes(header, target_size):
            return column_index
    return None


def _cell_contains_size_header(text: str) -> bool:
    return any(_SIZE_TOKEN_RE.fullmatch(token) for token in _tokens(text))


def _size_header_includes(text: str, target_size: int) -> bool:
    for token in _tokens(text):
        match = _SIZE_TOKEN_RE.fullmatch(token)
        if not match:
            continue
        start_size = int(match.group(1))
        end_size = int(match.group(2) or match.group(1))
        if start_size <= target_size <= end_size:
            return True
    return False


def _row_group_for_option(
    rows: list[ExtractedDocxTableRow],
    row_index: int,
    layout: _ColumnLayout,
    *,
    include_catalog_conditions: bool = False,
) -> list[ExtractedDocxTableRow]:
    grouped_rows = [rows[row_index]]
    for following in rows[row_index + 1 :]:
        description = _cell_at(following.raw_cells, layout.description_column).strip()
        if description:
            break
        if layout.voltage_column is None and not (include_catalog_conditions and _row_has_catalog_condition(following)):
            break
        grouped_rows.append(following)
    return grouped_rows


def _select_rows_for_catalog_conditions(
    rows: list[ExtractedDocxTableRow],
    catalog_number: str,
) -> list[ExtractedDocxTableRow]:
    """Select continuation rows whose expressions, such as {13}=3, match the catalog."""
    row_conditions = [(row, _catalog_conditions_for_row(row)) for row in rows]
    conditional_rows = [(row, conditions) for row, conditions in row_conditions if conditions]
    if not conditional_rows:
        return rows

    matching_rows = [
        row
        for row, conditions in conditional_rows
        if all(_catalog_condition_matches(condition, catalog_number) for condition in conditions)
    ]
    if matching_rows:
        return matching_rows

    fallback_rows = [row for row, conditions in row_conditions if not conditions]
    return fallback_rows


def _row_has_catalog_condition(row: ExtractedDocxTableRow) -> bool:
    return any(_CATALOG_CONDITION_RE.search(cell) for cell in row.raw_cells)


def _catalog_conditions_for_row(row: ExtractedDocxTableRow) -> list[_CatalogCondition]:
    conditions: list[_CatalogCondition] = []
    for cell in row.raw_cells:
        for match in _CATALOG_CONDITION_RE.finditer(cell):
            try:
                position = int(match.group(1))
            except ValueError:
                continue
            conditions.append(
                _CatalogCondition(
                    source_text=match.group(0),
                    position=position,
                    expected_value=normalize_option_code(match.group(2).replace("\u2013", "-").replace("\u2014", "-")),
                )
            )
    return conditions


def _catalog_condition_matches(condition: _CatalogCondition, catalog_number: str) -> bool:
    if condition.position < 1 or condition.position > len(catalog_number):
        return False
    actual = normalize_option_code(catalog_number[condition.position - 1])
    return actual == condition.expected_value


def _conditional_price_rules_enabled(rules: Any, current_position: int | None) -> bool:
    if current_position is None or not isinstance(rules, dict) or not rules.get("enabled"):
        return False
    return current_position in _conditional_price_positions(rules.get("positions"))


def _conditional_price_positions(raw_positions: Any) -> set[int]:
    if isinstance(raw_positions, dict):
        return {
            int(position)
            for position, enabled in raw_positions.items()
            if enabled and str(position).strip().isdigit() and int(position) > 0
        }
    if isinstance(raw_positions, str):
        raw_positions = re.split(r"[\s,;]+", raw_positions)
    positions: set[int] = set()
    for raw_position in raw_positions or []:
        try:
            position = int(raw_position)
        except (TypeError, ValueError):
            continue
        if position > 0:
            positions.add(position)
    return positions


def _select_row_for_voltage(
    rows: list[ExtractedDocxTableRow],
    layout: _ColumnLayout,
    voltage_label: str | None,
) -> ExtractedDocxTableRow:
    if layout.voltage_column is None or not voltage_label:
        return rows[0]
    normalized_voltage = normalize_option_code(voltage_label)
    for row in rows:
        voltage_text = normalize_option_code(_cell_at(row.raw_cells, layout.voltage_column))
        if voltage_text == "ALL" or normalized_voltage in voltage_text:
            return row
    return rows[0]


def _condenser_compatibility_for_group(
    rows: list[ExtractedDocxTableRow],
    layout: _ColumnLayout,
) -> _CondenserCompatibility:
    if layout.condenser_column is not None:
        raw_values = [
            _cell_at(row.raw_cells, layout.condenser_column).strip()
            for row in rows
            if _cell_at(row.raw_cells, layout.condenser_column).strip()
        ]
        raw_value = " ".join(raw_values)
    else:
        raw_values = [
            cell.strip()
            for row in rows
            for cell in row.raw_cells
            if cell.strip() and parse_document_condenser_compatibility(cell)
        ]
        raw_value = " ".join(raw_values)

    families = parse_document_condenser_compatibility(raw_value)
    if ALL_CONDENSERS in families:
        families = {ALL_CONDENSERS}
    return _CondenserCompatibility(raw_value=_normalize_cell_text(raw_value), families=families)


def _document_value_from_cell(cell_text: str) -> str:
    lines = [line.strip() for line in str(cell_text or "").splitlines() if line.strip()]
    candidates = lines or [str(cell_text or "").strip()]
    for candidate in reversed(candidates):
        parsed = parse_document_value(candidate)
        if parsed.value_type != "INVALID":
            return candidate
    for token in reversed(re.findall(r"\(?\$?\d[\d,]*(?:\.\d+)?\)?|Std\.?|Standard|Included|N/?A|N/?C|None|[-\u2013\u2014]", str(cell_text or ""), re.IGNORECASE)):
        parsed = parse_document_value(token)
        if parsed.value_type != "INVALID":
            return token
    return candidates[-1] if candidates else ""


def _base_unit_result(
    *,
    enabled: bool,
    source_catalog_number: str,
    search_type: str | None,
    rule: dict[str, Any] | None,
    status: str,
    reason: str,
    search_value: str | None = None,
    tables_searched: int = 0,
    matching_tables: int = 0,
    matches: list[BaseUnitPriceMatch] | None = None,
    selected: BaseUnitPriceMatch | None = None,
) -> BaseUnitPriceResult:
    configured_range = None
    template = None
    if isinstance(rule, dict):
        if search_type == RANGE_SEARCH or str(rule.get("search_type", "")).strip().lower() == RANGE_SEARCH:
            start_position = rule.get("start_position")
            end_position = rule.get("end_position")
            if start_position is not None and end_position is not None:
                configured_range = f"{start_position}-{end_position}"
        if search_type == FULL_SEARCH or str(rule.get("search_type", "")).strip().lower() == FULL_SEARCH:
            template = str(rule.get("template", "")).strip() or None

    return BaseUnitPriceResult(
        enabled=enabled,
        source_catalog_number=source_catalog_number,
        search_type=search_type,
        configured_range=configured_range,
        template=template,
        search_value=search_value,
        found=status == BASE_UNIT_PRICED,
        status=status,
        reason=reason,
        price=selected.price if selected else None,
        raw_value=selected.raw_value if selected else None,
        location=f"Table {selected.table_number}, row {selected.row_number}" if selected else None,
        table_heading=selected.table_heading if selected else None,
        table_number=selected.table_number if selected else None,
        row_number=selected.row_number if selected else None,
        cell_number=selected.cell_number if selected else None,
        tables_searched=tables_searched,
        matching_tables=matching_tables,
        matches=matches or [],
    )


def _find_master_price_column(table: ExtractedDocxTable) -> int | None:
    last_column = _last_table_column(table)
    if last_column is not None:
        return last_column
    best: tuple[int, int] | None = None
    for row in table.rows[:5]:
        for index, cell in enumerate(row.normalized_cells):
            normalized = _normalize_cell_text(cell).upper()
            compact = normalize_option_code(normalized)
            score = 0
            if "MASTER PRICE" in normalized or "MASTERPRICE" in compact:
                score = 100
            elif "LIST PRICE" in normalized or "LISTPRICE" in compact:
                score = 80
            elif "MASTER" in normalized and "PRICE" in normalized:
                score = 75
            elif normalized in {"PRICE", "MASTER"}:
                score = 45

            if any(label in normalized for label in {"POWER", "SUPPLY", "VOLTAGE", "SIZE", "TONNAGE", "QTY", "QUANTITY", "POSITION"}):
                score -= 100
            if last_column is not None and index == last_column:
                score += 25
            if score > 0 and (best is None or score > best[0]):
                best = (score, index)
    if best:
        return best[1]
    return last_column


def _last_table_column(table: DocxPositionTable | ExtractedDocxTable) -> int | None:
    last_column: int | None = None
    for row in table.rows:
        for index in range(len(row.raw_cells) - 1, -1, -1):
            if _normalize_cell_text(row.raw_cells[index]):
                if last_column is None or index > last_column:
                    last_column = index
                break
    return last_column


def _find_exact_base_unit_cell(cells: list[str], search_value: str) -> int | None:
    normalized_search = normalize_option_code(search_value)
    for index, cell in enumerate(cells):
        normalized_cell = normalize_option_code(cell)
        if normalized_cell == normalized_search:
            return index
        if normalized_search in {normalize_option_code(token) for token in _tokens(cell)}:
            return index
    return None


def _group_description(rows: list[ExtractedDocxTableRow], layout: _ColumnLayout) -> str:
    parts: list[str] = []
    for row in rows:
        description = _cell_at(row.raw_cells, layout.description_column)
        voltage = _cell_at(row.raw_cells, layout.voltage_column) if layout.voltage_column is not None else ""
        combined = " ".join(part for part in [_normalize_cell_text(description), _normalize_cell_text(voltage)] if part)
        if combined:
            parts.append(combined)
    return " | ".join(parts)


def _cell_has_exact_option_code(cell_text: str, normalized_code: str) -> bool:
    return normalized_code in {normalize_option_code(token) for token in _tokens(cell_text)}


def _tokens(text: str) -> list[str]:
    return re.findall(r"[A-Za-z0-9]+(?:[-_/][A-Za-z0-9]+)*|[-\u2013\u2014]", str(text or ""))


def _find_cell_containing(cells: list[str], text: str) -> int | None:
    normalized_text = _normalize_cell_text(text).upper()
    for index, cell in enumerate(cells):
        if normalized_text in _normalize_cell_text(cell).upper():
            return index
    return None


def _find_option_token_column(cells: list[str]) -> int | None:
    rejected = {"MASTER", "PRICE", "VOLTAGE", "CONDENSER", "SIZE", "TONNAGE", "QTY", "QUANTITY"}
    for index, cell in enumerate(cells):
        normalized = _normalize_cell_text(cell).upper()
        tokens = set(_tokens(normalized))
        if tokens & rejected:
            continue
        if "OPTION CODE" in normalized or "CODE" in tokens or "OPTION" in tokens or "CHARACTER" in tokens:
            return index
    return None


def _coerce_configured_positions(raw_positions: Any) -> list[int]:
    positions: list[int] = []
    for raw_position in raw_positions or []:
        try:
            position = int(raw_position)
        except (TypeError, ValueError):
            continue
        if position > 0:
            positions.append(position)
    return sorted(set(positions))


def _mapped_option_codes_for_position(position_config: dict[str, Any], position_value: str) -> list[str]:
    wanted_value = normalize_option_code(position_value)
    allowed_values_by_code = position_config.get("allowed_values_by_option_code") or {}
    normalized_allowed_values: dict[str, set[str]] = {}

    for raw_option_code, raw_allowed_values in allowed_values_by_code.items():
        option_code = normalize_option_code(raw_option_code)
        if not option_code:
            continue
        normalized_allowed_values[option_code] = {
            normalize_option_code(value) for value in raw_allowed_values or [] if normalize_option_code(value)
        }

    configured_option_codes = position_config.get("option_codes") or list(allowed_values_by_code.keys())
    mapped_codes: list[str] = []
    seen: set[str] = set()
    for raw_option_code in configured_option_codes:
        option_code = normalize_option_code(raw_option_code)
        if not option_code or option_code in seen:
            continue
        if wanted_value in normalized_allowed_values.get(option_code, set()):
            mapped_codes.append(option_code)
            seen.add(option_code)
    return mapped_codes


def _tables_for_decoded_position(decoded: DecodedCatalogPosition, tables: list[DocxPositionTable]) -> list[DocxPositionTable]:
    exact_tables = [
        table
        for table in tables
        if table.start_position == decoded.start_position and table.end_position == decoded.end_position
    ]
    if exact_tables:
        return exact_tables
    return [
        table
        for table in tables
        if table.start_position <= decoded.start_position and decoded.end_position <= table.end_position
    ]


def _has_covering_heading(decoded: DecodedCatalogPosition, heading_ranges: set[tuple[int, int]]) -> bool:
    return any(
        start_position <= decoded.start_position and decoded.end_position <= end_position
        for start_position, end_position in heading_ranges
    )


def _build_product_context(catalog_number: str, configuration: dict[str, Any]) -> dict[str, str | None]:
    catalog = str(catalog_number).strip().upper()
    product_family = normalize_condenser_family(str(configuration.get("product_family", "")).strip())
    if product_family is None:
        product_family = normalize_condenser_family(str(configuration.get("condenser_family", "")).strip())
    size_code = None
    voltage_label = None
    unit_type_row = next(
        (
            row
            for row in configuration.get("structure", [])
            if str(row.get("characteristic_key", "")).strip().upper()
            in {"UNIT_TYPE", "CONDENSER_TYPE", "CONDENSER", "CONDENSER_OPTION"}
        ),
        None,
    )
    if product_family is None and unit_type_row:
        try:
            start_position = int(unit_type_row.get("start_position"))
            end_position = int(unit_type_row.get("end_position"))
            unit_code = catalog[start_position - 1 : end_position]
        except (TypeError, ValueError):
            unit_code = ""
        product_family = normalize_condenser_family(unit_code)
    if product_family is None:
        product_family = normalize_condenser_family(catalog)

    for row in configuration.get("structure", []):
        characteristic_key = str(row.get("characteristic_key", "")).strip().upper()
        try:
            start_position = int(row.get("start_position"))
            end_position = int(row.get("end_position"))
        except (TypeError, ValueError):
            continue
        value = catalog[start_position - 1 : end_position] if end_position <= len(catalog) else ""
        if characteristic_key in {"TONNAGE", "SIZE", "UNIT_SIZE"} and value:
            size_code = value
        if characteristic_key == "VOLTAGE" and value:
            voltage_label = _specification_label_for_value(row, value)

    return {
        "catalog_number": catalog,
        "product_family": product_family,
        "condenser_type": product_family,
        "size_code": size_code,
        "voltage_label": voltage_label,
    }


def _specification_label_for_value(structure_row: dict[str, Any], catalog_value: str) -> str | None:
    normalized_value = normalize_option_code(catalog_value)
    for specification in structure_row.get("specifications", []) or []:
        if normalize_option_code(str(specification.get("catalog_value", ""))) == normalized_value:
            label = str(specification.get("label", "")).strip()
            return label or catalog_value
    return catalog_value


def _cell_at(cells: list[str], index: int | None) -> str:
    if index is None or index < 0 or index >= len(cells):
        return ""
    return cells[index]


def _normalize_cell_text(value: str) -> str:
    return " ".join(str(value or "").replace("\n", " ").split()).strip()


def _position_key(start_position: int, end_position: int) -> str:
    return str(start_position) if start_position == end_position else f"{start_position}-{end_position}"


def _table_location(table: DocxPositionTable) -> str:
    return f"Table {table.table_number}"


def _local_name(tag: str) -> str:
    return tag.rsplit("}", 1)[-1]
