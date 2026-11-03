"""Read and normalize Microsoft Forms response workbooks."""

from __future__ import annotations

import re
import unicodedata
from dataclasses import dataclass
from pathlib import Path

import pandas as pd


class ImportValidationError(ValueError):
    """Raised when a response workbook cannot be safely imported."""


@dataclass(frozen=True)
class ImportResult:
    source: str
    records: list[dict[str, str]]
    rows_read: int
    skipped_rows: int
    column_mapping: dict[str, str]
    warnings: list[str]


ALIASES = {
    "ID": {"id", "response id"},
    "Nombre completo": {"nombre", "nombre completo", "full name", "name"},
    "Carrera": {"carrera", "career", "programa", "programa academico"},
    "Semestre": {"semestre", "semester"},
}


def search_key(value: object) -> str:
    text = unicodedata.normalize("NFKD", str(value))
    text = "".join(char for char in text if not unicodedata.combining(char))
    return re.sub(r"\s+", " ", text.strip().lower())


def normalize_text(value: object) -> str:
    if pd.isna(value):
        return ""
    return re.sub(r"\s+", " ", str(value).strip())


def normalize_numberlike(value: object) -> str:
    text = normalize_text(value)
    if re.fullmatch(r"[+-]?\d+\.0+", text):
        return text.split(".", 1)[0]
    return text


class ExcelImporter:
    """Parse response files without modifying the master database."""

    @staticmethod
    def detect_source(path: Path) -> str:
        key = path.name.casefold()
        if "carrier week" in key:
            return "Carrier Week"
        if "carrier day" in key:
            return "Carrier Day"
        raise ImportValidationError(
            "Unable to determine the source of this Excel file.\n\n"
            "The filename must contain either:\n- Carrier Week\n- Carrier Day"
        )

    def read(self, path: Path) -> ImportResult:
        if path.suffix.lower() not in {".xlsx", ".xls"}:
            raise ImportValidationError("Unsupported file format. Select an .xlsx or .xls file.")
        source = self.detect_source(path)
        try:
            frame = pd.read_excel(path, dtype=object)
        except Exception as exc:
            raise ImportValidationError(f"Unable to read the selected Excel file.\n\n{exc}") from exc

        normalized_headers = {search_key(column): str(column) for column in frame.columns}
        mapping: dict[str, str] = {}
        for field, aliases in ALIASES.items():
            match = next((normalized_headers[a] for a in aliases if a in normalized_headers), None)
            if match is None:
                raise ImportValidationError(
                    f"Required field not found: {field}\n\n"
                    f"Available columns: {', '.join(map(str, frame.columns))}"
                )
            mapping[field] = match

        records: list[dict[str, str]] = []
        warnings: list[str] = []
        skipped = 0
        for row_number, (_, row) in enumerate(frame.iterrows(), start=2):
            original_id = normalize_numberlike(row[mapping["ID"]])
            name = normalize_text(row[mapping["Nombre completo"]])
            if not original_id or not name:
                skipped += 1
                warnings.append(f"Row {row_number}: missing ID or Nombre; row skipped.")
                continue
            career = normalize_text(row[mapping["Carrera"]])
            semester = normalize_numberlike(row[mapping["Semestre"]])
            if not career or not semester:
                warnings.append(f"Row {row_number}: Carrera or Semestre is blank.")
            records.append(
                {
                    "UniqueID": f"{original_id} - {source}",
                    "OriginalID": original_id,
                    "Nombre completo": name,
                    "Carrera": career,
                    "Semestre": semester,
                    "Source": source,
                }
            )
        return ImportResult(source, records, len(frame), skipped, mapping, warnings)
