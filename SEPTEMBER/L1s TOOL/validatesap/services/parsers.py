import csv
import re
from dataclasses import dataclass
from io import StringIO

from .normalization import clean_cell, normalize_header, normalize_part_number, parse_quantity
from .records import ParseResult, PasteRecord, ValidationMessage


HEADER_ALIASES = {
    "level": {"level", "lvl"},
    "item": {"item", "itemnumber", "itm"},
    "part_number": {"partnumber", "partno", "pn", "component", "material"},
    "description": {"description", "desc", "materialdescription"},
    "quantity": {"quantity", "qty", "componentquantity"},
    "unit": {"unit", "uom", "un"},
    "pgr": {"pgr", "purchasinggroup", "purchgroup"},
    "source_code_1": {"sourcecode1", "sc1", "specialprocurement"},
    "source_code_2": {"sourcecode2", "sc2", "procurementtype"},
    "source": {"source", "sourcing"},
}


@dataclass(frozen=True)
class DatasetSpec:
    fields: tuple[str, ...]
    required_fields: tuple[str, ...]
    min_columns: int


SPECS = {
    "tumbling": DatasetSpec(("part_number",), ("part_number",), 1),
    "adds": DatasetSpec(("item", "part_number", "quantity", "source"), ("part_number", "quantity", "source"), 4),
    "deletes": DatasetSpec(("item", "part_number", "quantity"), ("item", "part_number", "quantity"), 3),
    "standard": DatasetSpec(("level", "item", "part_number", "description", "quantity"), ("item", "part_number", "quantity"), 5),
    "sap": DatasetSpec(
        ("level", "item", "part_number", "description", "quantity", "unit", "pgr", "source_code_1", "source_code_2"),
        ("item", "part_number", "quantity"),
        9,
    ),
}


def _delimiter_for(text: str) -> str | None:
    sample = next((line for line in text.splitlines() if line.strip()), "")
    if "\t" in sample:
        return "\t"
    if "," in sample:
        return ","
    if ";" in sample:
        return ";"
    return None


def _rows(text: str) -> list[tuple[int, list[str], str]]:
    normalized = text.replace("\r\n", "\n").replace("\r", "\n")
    delimiter = _delimiter_for(normalized)
    output = []
    for row_number, raw_line in enumerate(normalized.split("\n"), start=1):
        if not raw_line.strip():
            continue
        if delimiter:
            parsed = next(csv.reader(StringIO(raw_line), delimiter=delimiter))
        else:
            parsed = [raw_line]
        output.append((row_number, [clean_cell(value) for value in parsed], raw_line))
    return output


def _header_mapping(row: list[str]) -> dict[str, int]:
    aliases = {alias: field for field, values in HEADER_ALIASES.items() for alias in values}
    mapping = {}
    for index, value in enumerate(row):
        field = aliases.get(normalize_header(value))
        if field:
            mapping[field] = index
    return mapping if "part_number" in mapping else {}


def parse_dataset(dataset: str, text: str) -> ParseResult:
    spec = SPECS[dataset]
    result = ParseResult(dataset=dataset)
    rows = _rows(text)
    if not rows:
        return result

    header_map = _header_mapping(rows[0][1])
    if header_map:
        result.header_detected = True
        rows = rows[1:]

    for row_number, row, original_line in rows:
        if not header_map and len(row) < spec.min_columns:
            result.messages.append(
                ValidationMessage(
                    dataset=dataset,
                    row_number=row_number,
                    message=f"Expected at least {spec.min_columns} columns but found {len(row)}.",
                    code="malformed_row",
                )
            )

        values = {}
        for fallback_index, field in enumerate(spec.fields):
            source_index = header_map.get(field, fallback_index) if header_map else fallback_index
            values[field] = row[source_index] if source_index < len(row) else ""
        for index in range(len(spec.fields), len(row)):
            values[f"extra_{index - len(spec.fields) + 1}"] = row[index]

        normalized_pn = normalize_part_number(values.get("part_number"))
        result.records.append(
            PasteRecord(
                dataset=dataset,
                row_number=row_number,
                values=values,
                original_line=original_line,
                normalized_part_number=normalized_pn,
                quantity=parse_quantity(values.get("quantity")),
            )
        )
    return result


def parse_all(payload: dict[str, str]) -> dict[str, ParseResult]:
    return {name: parse_dataset(name, payload.get(name, "")) for name in SPECS}


def extract_tumbling_name(text: str, parsed: ParseResult | None = None) -> str:
    """Extract the Tumbling identifier without changing meaningful characters."""
    rows = _rows(text)
    label_pattern = re.compile(r"^\s*tumbling\s*name\s*(?::|=)\s*(.*?)\s*$", re.IGNORECASE)

    for row_index, (_row_number, cells, raw_line) in enumerate(rows):
        match = label_pattern.match(raw_line)
        if match and match.group(1).strip():
            return match.group(1).strip()

        if cells and normalize_header(cells[0]) == "tumblingname":
            if len(cells) > 1 and cells[1].strip():
                return cells[1].strip()
            if row_index + 1 < len(rows) and rows[row_index + 1][1]:
                return rows[row_index + 1][1][0].strip()

    parsed = parsed or parse_dataset("tumbling", text)
    if parsed.records:
        return parsed.records[0].part_number.strip()
    return ""
