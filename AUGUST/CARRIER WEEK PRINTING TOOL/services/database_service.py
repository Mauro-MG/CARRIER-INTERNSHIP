"""Excel-backed student database with atomic updates."""

from __future__ import annotations

import json
import os
import re
import shutil
import zipfile
from xml.sax.saxutils import escape
from xml.etree import ElementTree as ET
from datetime import datetime
from pathlib import Path
from typing import Iterable

import pandas as pd
from openpyxl import Workbook
from openpyxl.styles import Font, PatternFill


COLUMNS = [
    "UniqueID", "OriginalID", "Nombre completo", "Carrera", "Semestre", "Source",
    "ImportedAt", "Printed", "PrintedAt", "PrintCount",
]


class DatabaseLockedError(OSError):
    """Raised when Excel or another process prevents a database update."""


class QueryBackedDatabaseError(OSError):
    """Raised when an import would overwrite Power Query-backed worksheets."""


class ExcelWorkbookSyncError(OSError):
    """Raised when calculated fields cannot be synchronized into Excel."""


class DatabaseService:
    def __init__(self, path: Path) -> None:
        self.path = path
        self.history_path = path.with_name("print_history.json")
        self.id_map_path = path.with_name("student_id_map.json")

    def initialize(self) -> None:
        self.path.parent.mkdir(parents=True, exist_ok=True)
        if self.path.exists():
            return
        workbook = Workbook()
        sheet = workbook.active
        sheet.title = "Students"
        sheet.append(COLUMNS)
        for cell in sheet[1]:
            cell.font = Font(bold=True, color="FFFFFF")
            cell.fill = PatternFill("solid", fgColor="2C3E50")
        sheet.freeze_panes = "A2"
        workbook.save(self.path)
        workbook.close()

    def load(self) -> pd.DataFrame:
        self.initialize()
        try:
            sheets = pd.read_excel(self.path, sheet_name=None, dtype=object)
        except PermissionError as exc:
            raise DatabaseLockedError from exc
        id_map = self._read_id_map()
        changed = self._seed_id_map(sheets, id_map)
        frames = []
        for name, sheet in sheets.items():
            normalized, assigned = self._normalize_sheet(name, sheet, id_map)
            frames.append(normalized)
            changed = changed or assigned
        if changed:
            self._write_json_atomic(self.id_map_path, id_map)
        frames = [frame for frame in frames if not frame.empty]
        frame = pd.concat(frames, ignore_index=True) if frames else pd.DataFrame(columns=COLUMNS)
        frame = frame.drop_duplicates(subset="UniqueID", keep="last")
        self._apply_print_history(frame)
        if self._has_query_tables():
            self._sync_query_workbook(sheets, frame)
        return frame[COLUMNS].fillna("")

    def _has_query_tables(self) -> bool:
        """Return whether the workbook contains an Excel query table."""
        try:
            with zipfile.ZipFile(self.path) as archive:
                return any(name.startswith("xl/queryTables/") for name in archive.namelist())
        except (OSError, zipfile.BadZipFile):
            return False

    def _sync_query_workbook(
        self, sheets: dict[str, pd.DataFrame], combined: pd.DataFrame
    ) -> None:
        """Persist calculated fields while preserving every Power Query part."""
        updates = self._query_sheet_updates(sheets, combined)
        if not updates:
            return
        backup = self.path.with_name(f"{self.path.stem}.backup-before-sync{self.path.suffix}")
        if not backup.exists():
            try:
                shutil.copy2(self.path, backup)
            except OSError as exc:
                raise ExcelWorkbookSyncError("Unable to create the database safety backup.") from exc
        temporary = self.path.with_name(f".{self.path.stem}.sync.tmp.xlsx")
        try:
            sheet_parts = self._worksheet_parts()
            with zipfile.ZipFile(self.path, "r") as source, zipfile.ZipFile(temporary, "w") as destination:
                for info in source.infolist():
                    data = source.read(info.filename)
                    sheet_name = next(
                        (name for name, part in sheet_parts.items() if part == info.filename), None
                    )
                    if sheet_name in updates:
                        data = self._patch_worksheet_xml(
                            data, updates[sheet_name], list(sheets[sheet_name].columns)
                        )
                    destination.writestr(info, data)
            os.replace(temporary, self.path)
        except (PermissionError, OSError, KeyError, ValueError, zipfile.BadZipFile, ET.ParseError) as exc:
            temporary.unlink(missing_ok=True)
            raise ExcelWorkbookSyncError(
                "Unable to update UniqueID and print information in students.xlsx. "
                "Close the workbook in Excel and try Refresh Database again."
            ) from exc

    def _worksheet_parts(self) -> dict[str, str]:
        main_ns = "http://schemas.openxmlformats.org/spreadsheetml/2006/main"
        rel_ns = "http://schemas.openxmlformats.org/officeDocument/2006/relationships"
        package_ns = "http://schemas.openxmlformats.org/package/2006/relationships"
        with zipfile.ZipFile(self.path, "r") as archive:
            workbook = ET.fromstring(archive.read("xl/workbook.xml"))
            relationships = ET.fromstring(archive.read("xl/_rels/workbook.xml.rels"))
        targets = {
            relation.attrib["Id"]: relation.attrib["Target"]
            for relation in relationships.findall(f"{{{package_ns}}}Relationship")
        }
        return {
            sheet.attrib["name"]: "xl/" + targets[sheet.attrib[f"{{{rel_ns}}}id"]].lstrip("/")
            for sheet in workbook.findall(f"{{{main_ns}}}sheets/{{{main_ns}}}sheet")
        }

    @staticmethod
    def _patch_worksheet_xml(
        xml_data: bytes,
        updates: list[tuple[int, dict[str, object]]],
        existing_columns: list[object],
    ) -> bytes:
        """Replace only target cell elements, preserving Excel's XML verbatim."""
        xml_text = xml_data.decode("utf-8")
        columns = {str(name): index + 1 for index, name in enumerate(existing_columns)}
        for field in ("UniqueID", "Printed", "PrintedAt", "PrintCount"):
            if field not in columns:
                raise ValueError(f"Required database column is missing: {field}")
        for row_number, values in updates:
            for field, value in values.items():
                reference = f"{DatabaseService._column_letters(columns[field])}{row_number}"
                xml_text = DatabaseService._replace_xml_cell(
                    xml_text, reference, value
                )
        return xml_text.encode("utf-8")

    @staticmethod
    def _replace_xml_cell(xml_text: str, reference: str, value: object) -> str:
        """Replace one cell without reserializing its worksheet document."""
        cell_pattern = re.compile(
            rf'<c\b(?=[^>]*\br="{re.escape(reference)}")([^>]*)'
            rf'(?:\s*/>|>.*?</c>)',
            re.DOTALL,
        )
        match = cell_pattern.search(xml_text)
        if match is not None:
            attributes = re.sub(r'\s+t="[^"]*"', "", match.group(1)).rstrip()
            replacement = DatabaseService._xml_cell(reference, value, attributes)
            return xml_text[:match.start()] + replacement + xml_text[match.end():]

        row_number_match = re.search(r"(\d+)$", reference)
        if row_number_match is None:
            raise ValueError(f"Invalid worksheet cell reference: {reference}")
        row_number = row_number_match.group(1)
        row_pattern = re.compile(
            rf'(<row\b(?=[^>]*\br="{row_number}")[^>]*>)(.*?)(</row>)',
            re.DOTALL,
        )
        row_match = row_pattern.search(xml_text)
        if row_match is None:
            raise ValueError(f"Worksheet row is missing: {row_number}")
        style_match = re.search(
            rf'<c\b(?=[^>]*\br="{re.escape(re.sub(r"\d+$", "", reference))}\d+")'
            rf'[^>]*\bs="([^"]+)"',
            xml_text,
        )
        attributes = f' r="{reference}"' + (f' s="{style_match.group(1)}"' if style_match else "")
        new_cell = DatabaseService._xml_cell(reference, value, attributes)
        row_body = row_match.group(2)
        target_column = DatabaseService._column_number(reference)
        insert_at = len(row_body)
        existing_cells = re.compile(
            r'<c\b(?=[^>]*\br="([A-Z]+)\d+")[^>]*(?:\s*/>|>.*?</c>)',
            re.DOTALL,
        )
        for existing in existing_cells.finditer(row_body):
            if DatabaseService._column_number(existing.group(1)) > target_column:
                insert_at = existing.start()
                break
        updated_body = row_body[:insert_at] + new_cell + row_body[insert_at:]
        replacement_row = row_match.group(1) + updated_body + row_match.group(3)
        return xml_text[:row_match.start()] + replacement_row + xml_text[row_match.end():]

    @staticmethod
    def _xml_cell(reference: str, value: object, attributes: str) -> str:
        if not re.search(r'\br="', attributes):
            attributes = f' r="{reference}"' + attributes
        if isinstance(value, (int, float)) and not isinstance(value, bool):
            return f'<c{attributes}><v>{value}</v></c>'
        return f'<c{attributes} t="inlineStr"><is><t>{escape(str(value))}</t></is></c>'

    @staticmethod
    def _column_letters(number: int) -> str:
        result = ""
        while number:
            number, remainder = divmod(number - 1, 26)
            result = chr(65 + remainder) + result
        return result

    @staticmethod
    def _column_number(reference: str) -> int:
        number = 0
        for character in reference:
            if not character.isalpha():
                break
            number = number * 26 + ord(character.upper()) - 64
        return number

    def _query_sheet_updates(
        self, sheets: dict[str, pd.DataFrame], combined: pd.DataFrame
    ) -> dict[str, list[tuple[int, dict[str, object]]]]:
        """Build the minimal cell updates needed by query-backed worksheets."""
        lookup = {
            (str(row["Source"]), self._identifier(row["OriginalID"])): row
            for _, row in combined.iterrows()
            if self._identifier(row["OriginalID"])
        }
        result: dict[str, list[tuple[int, dict[str, object]]]] = {}
        for sheet_name, raw in sheets.items():
            name_key = sheet_name.casefold()
            source = "Carrier Day" if "carrier day" in name_key else "Carrier Week" if "carrier week" in name_key else ""
            original_column = "OriginalID" if "OriginalID" in raw else "Id" if "Id" in raw else None
            if not source or original_column is None:
                continue
            rows: list[tuple[int, dict[str, object]]] = []
            for position, (_, raw_row) in enumerate(raw.iterrows(), start=2):
                original_id = self._identifier(raw_row.get(original_column, ""))
                normalized = lookup.get((source, original_id))
                if normalized is None:
                    continue
                desired = {
                    "UniqueID": str(normalized["UniqueID"]),
                    "Printed": str(normalized["Printed"] or "No"),
                    "PrintedAt": str(normalized["PrintedAt"] or ""),
                    "PrintCount": int(normalized["PrintCount"] or 0),
                }
                changed = {
                    field: value
                    for field, value in desired.items()
                    if self._cell_value(raw_row.get(field, "")) != self._cell_value(value)
                }
                if changed:
                    rows.append((position, changed))
            if rows:
                result[sheet_name] = rows
        return result

    @staticmethod
    def _cell_value(value: object) -> str:
        if pd.isna(value) or value is None:
            return ""
        if isinstance(value, float) and value.is_integer():
            return str(int(value))
        return str(value).strip()

    def _normalize_sheet(
        self, sheet_name: str, frame: pd.DataFrame, id_map: dict[str, dict[str, int]]
    ) -> tuple[pd.DataFrame, bool]:
        if "Nombre completo" not in frame and "Nombre" in frame:
            frame["Nombre completo"] = frame["Nombre"]
        if "OriginalID" not in frame and "Id" in frame:
            frame["OriginalID"] = frame["Id"]

        source = ""
        name_key = sheet_name.casefold()
        if "carrier day" in name_key:
            source = "Carrier Day"
        elif "carrier week" in name_key:
            source = "Carrier Week"
        if "Source" not in frame:
            frame["Source"] = source
        elif source:
            frame["Source"] = frame["Source"].fillna("").replace("", source)

        required = {"OriginalID", "Nombre completo", "Carrera", "Semestre"}
        if not required.issubset(frame.columns):
            return pd.DataFrame(columns=COLUMNS), False
        frame = frame.copy()
        frame["OriginalID"] = frame["OriginalID"].map(DatabaseService._identifier)
        frame["Source"] = frame["Source"].fillna("").astype(str).str.strip()
        changed = False
        if source and "Id" in frame.columns:
            source_map = id_map.setdefault(source, {})
            next_id = max(source_map.values(), default=0) + 1
            unique_ids = []
            for original_id in frame["OriginalID"]:
                if not original_id:
                    unique_ids.append("")
                    continue
                if original_id not in source_map:
                    source_map[original_id] = next_id
                    next_id += 1
                    changed = True
                unique_ids.append(f"{source_map[original_id]} - {source}")
            frame["UniqueID"] = unique_ids
        elif "UniqueID" not in frame:
            frame["UniqueID"] = frame["OriginalID"] + " - " + frame["Source"]
        if "Nombre completo" not in frame and "Nombre" in frame:
            frame["Nombre completo"] = frame["Nombre"]
        for column in COLUMNS:
            if column not in frame:
                frame[column] = ""
        frame = frame[COLUMNS].fillna("")
        frame["Printed"] = frame["Printed"].astype(str).str.strip().replace("", "No")
        frame["PrintCount"] = pd.to_numeric(frame["PrintCount"], errors="coerce").fillna(0).astype(int)
        return frame, changed

    def _read_id_map(self) -> dict[str, dict[str, int]]:
        try:
            data = json.loads(self.id_map_path.read_text(encoding="utf-8"))
            if not isinstance(data, dict):
                return {}
            return {
                str(source): {str(key): int(value) for key, value in values.items()}
                for source, values in data.items()
                if isinstance(values, dict)
            }
        except (OSError, ValueError, TypeError, json.JSONDecodeError):
            return {}

    def _seed_id_map(
        self, sheets: dict[str, pd.DataFrame], id_map: dict[str, dict[str, int]]
    ) -> bool:
        changed = False
        for sheet_name, frame in sheets.items():
            name_key = sheet_name.casefold()
            source = "Carrier Day" if "carrier day" in name_key else "Carrier Week" if "carrier week" in name_key else ""
            original_column = "OriginalID" if "OriginalID" in frame else "Id" if "Id" in frame else None
            if not source or original_column is None or "UniqueID" not in frame:
                continue
            source_map = id_map.setdefault(source, {})
            used = set(source_map.values())
            for original, unique in zip(frame[original_column], frame["UniqueID"]):
                original_id = self._identifier(original)
                text = "" if pd.isna(unique) else str(unique).strip()
                prefix, separator, suffix = text.partition(" - ")
                if not original_id or not separator or suffix != source or not prefix.isdigit():
                    continue
                sequence = int(prefix)
                if original_id not in source_map and sequence not in used:
                    source_map[original_id] = sequence
                    used.add(sequence)
                    changed = True
        return changed

    @staticmethod
    def _write_json_atomic(path: Path, data: object) -> None:
        temporary = path.with_suffix(".json.tmp")
        try:
            temporary.write_text(json.dumps(data, indent=2, ensure_ascii=False), encoding="utf-8")
            os.replace(temporary, path)
        except (PermissionError, OSError) as exc:
            temporary.unlink(missing_ok=True)
            raise DatabaseLockedError(f"Unable to update {path.name}.") from exc

    @staticmethod
    def _identifier(value: object) -> str:
        if pd.isna(value):
            return ""
        text = str(value).strip()
        if text.endswith(".0") and text[:-2].lstrip("+-").isdigit():
            return text[:-2]
        return text

    def _read_print_history(self) -> dict[str, dict[str, object]]:
        try:
            data = json.loads(self.history_path.read_text(encoding="utf-8"))
            return data if isinstance(data, dict) else {}
        except (OSError, json.JSONDecodeError):
            return {}

    def _apply_print_history(self, frame: pd.DataFrame) -> None:
        history = self._read_print_history()
        for idx, unique_id in frame["UniqueID"].astype(str).items():
            entry = history.get(unique_id)
            if not isinstance(entry, dict):
                continue
            frame.at[idx, "Printed"] = "Yes"
            frame.at[idx, "PrintedAt"] = str(entry.get("PrintedAt", ""))
            frame.at[idx, "PrintCount"] = int(entry.get("PrintCount", 0) or 0)

    def _save(self, frame: pd.DataFrame) -> None:
        try:
            if self.path.exists():
                with pd.ExcelFile(self.path) as workbook:
                    sheet_names = workbook.sheet_names
                    standard_schema = all(
                        set(COLUMNS).issubset(workbook.parse(name, nrows=0).columns)
                        for name in sheet_names
                    )
            else:
                sheet_names = []
                standard_schema = True
        except Exception:
            sheet_names = []
            standard_schema = True
        if len(sheet_names) > 1 or not standard_schema:
            raise QueryBackedDatabaseError(
                "This database is connected to OneDrive and cannot be overwritten by Import Responses Excel. "
                "Update the OneDrive source and use Refresh Database instead."
            )
        temporary = self.path.with_name(f".{self.path.stem}.tmp.xlsx")
        try:
            with pd.ExcelWriter(temporary, engine="openpyxl") as writer:
                frame[COLUMNS].to_excel(writer, index=False, sheet_name="Students - Carrier Day")
                sheet = writer.book["Students - Carrier Day"]
                for cell in sheet[1]:
                    cell.font = Font(bold=True, color="FFFFFF")
                    cell.fill = PatternFill("solid", fgColor="2C3E50")
                sheet.freeze_panes = "A2"
                widths = {"A": 28, "B": 14, "C": 34, "D": 25, "E": 12, "F": 18, "G": 20, "H": 12, "I": 20, "J": 12}
                for column, width in widths.items():
                    sheet.column_dimensions[column].width = width
            os.replace(temporary, self.path)
        except (PermissionError, OSError) as exc:
            temporary.unlink(missing_ok=True)
            raise DatabaseLockedError(
                "Unable to update the student database. Please close students.xlsx in Excel and try again."
            ) from exc

    def upsert(self, records: Iterable[dict[str, str]]) -> tuple[int, int, int]:
        frame = self.load()
        index_by_id = {str(value): idx for idx, value in frame["UniqueID"].items()}
        inserted = updated = 0
        now = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
        for record in records:
            unique_id = record["UniqueID"]
            if unique_id in index_by_id:
                idx = index_by_id[unique_id]
                for column in ("OriginalID", "Nombre completo", "Carrera", "Semestre", "Source"):
                    frame.at[idx, column] = record[column]
                frame.at[idx, "ImportedAt"] = now
                updated += 1
            else:
                row = {column: "" for column in COLUMNS}
                row.update(record)
                row.update({"ImportedAt": now, "Printed": "No", "PrintedAt": "", "PrintCount": 0})
                frame = pd.concat([frame, pd.DataFrame([row])], ignore_index=True)
                index_by_id[unique_id] = len(frame) - 1
                inserted += 1
        self._save(frame)
        return inserted, updated, len(frame)

    def mark_printed(self, unique_id: str) -> None:
        frame = self.load()
        matches = frame.index[frame["UniqueID"].astype(str) == unique_id].tolist()
        if not matches:
            raise KeyError(f"Student not found: {unique_id}")
        idx = matches[0]
        history = self._read_print_history()
        history[unique_id] = {
            "PrintedAt": datetime.now().strftime("%Y-%m-%d %H:%M:%S"),
            "PrintCount": int(frame.at[idx, "PrintCount"] or 0) + 1,
        }
        self._write_json_atomic(self.history_path, history)
        if self._has_query_tables():
            self.load()
