import csv
import os
import re
import uuid
from dataclasses import dataclass
from datetime import datetime
from pathlib import Path

from django.conf import settings

from .comparison import NEEDS_TO_BE_ADDED, NEEDS_TO_BE_DELETED, NO_CHANGE
from .normalization import normalize_part_number
from .records import ComparisonItem


STATUS_LABELS = {
    NEEDS_TO_BE_ADDED: "NEEDS TO BE ADDED TO SAP",
    NEEDS_TO_BE_DELETED: "NEEDS TO BE DELETED FROM SAP",
    NO_CHANGE: "NO CHANGE NEEDED",
}
LABEL_TO_STATUS = {label: status for status, label in STATUS_LABELS.items()}
STATUS_ORDER = (NEEDS_TO_BE_ADDED, NEEDS_TO_BE_DELETED, NO_CHANGE)
CSV_FIELDS = (
    "Part Number",
    "Description",
    "Quantity",
    "Position",
    "Source",
    "Status",
    "SAP Ready Record",
    "Reason",
)
INVALID_FILENAME_CHARACTERS = re.compile(r'[<>:"/\\|?*\x00-\x1f]')
WINDOWS_RESERVED_NAMES = {
    "CON", "PRN", "AUX", "NUL",
    *(f"COM{number}" for number in range(1, 10)),
    *(f"LPT{number}" for number in range(1, 10)),
}


class CsvServiceError(Exception):
    """Base error suitable for a clear, non-technical UI message."""


class InvalidTumblingNameError(CsvServiceError):
    pass


class ResultsFileExistsError(CsvServiceError):
    def __init__(self, filename: str):
        self.filename = filename
        super().__init__(f"A saved result already exists for {filename}.")


class SavedValidationNotFoundError(CsvServiceError):
    pass


class InvalidSavedValidationError(CsvServiceError):
    pass


@dataclass(frozen=True)
class SavedValidationMetadata:
    tumbling_name: str
    filename: str
    modified: datetime
    counts: dict[str, int]
    valid: bool = True


@dataclass(frozen=True)
class LoadedValidation:
    tumbling_name: str
    filename: str
    modified: datetime
    results: dict[str, list[ComparisonItem]]

    @property
    def counts(self) -> dict[str, int]:
        return {status: len(self.results[status]) for status in STATUS_ORDER}


def sanitize_filename(tumbling_name: str) -> str:
    cleaned = (tumbling_name or "").strip()
    cleaned = INVALID_FILENAME_CHARACTERS.sub("_", cleaned).rstrip(" .")
    if not cleaned or cleaned in {".", ".."}:
        raise InvalidTumblingNameError("Unable to save results because the Tumbling name could not be identified.")
    if cleaned.upper() in WINDOWS_RESERVED_NAMES:
        cleaned = f"{cleaned}_"
    return cleaned


def result_filename(tumbling_name: str) -> str:
    return f"{sanitize_filename(tumbling_name)}.csv"


def _results_directory(directory: Path | None = None) -> Path:
    return Path(directory or settings.SAVE_RESULTS_DIR)


def _safe_path(tumbling_name: str, directory: Path | None = None, *, require_exact_name: bool = False) -> Path:
    base = _results_directory(directory).resolve()
    safe_name = sanitize_filename(tumbling_name)
    if require_exact_name and safe_name != tumbling_name:
        raise InvalidTumblingNameError("The requested saved validation name is invalid.")
    candidate = (base / f"{safe_name}.csv").resolve()
    if candidate.parent != base:
        raise InvalidTumblingNameError("The requested saved validation name is invalid.")
    return candidate


def _item_value(item, key: str, default=""):
    if isinstance(item, dict):
        return item.get(key, default)
    return getattr(item, key, default)


def build_csv_rows(comparison_results: dict[str, list[ComparisonItem]]) -> list[dict[str, str]]:
    rows = []
    for status in STATUS_ORDER:
        for item in comparison_results.get(status, []):
            values = _item_value(item, "values", {}) or {}
            sap_ready = _item_value(item, "record", "") if status in {NEEDS_TO_BE_ADDED, NEEDS_TO_BE_DELETED} else ""
            rows.append(
                {
                    "Part Number": _item_value(item, "part_number", ""),
                    "Description": values.get("description", ""),
                    "Quantity": values.get("quantity", ""),
                    "Position": values.get("item", ""),
                    "Source": values.get("source", ""),
                    "Status": STATUS_LABELS[status],
                    "SAP Ready Record": sap_ready,
                    "Reason": _item_value(item, "reason", ""),
                }
            )
    return rows


def _write_rows(path: Path, rows: list[dict[str, str]], mode: str) -> None:
    with path.open(mode, newline="", encoding="utf-8-sig") as csvfile:
        writer = csv.DictWriter(csvfile, fieldnames=CSV_FIELDS)
        writer.writeheader()
        writer.writerows(rows)


def save_results_csv(
    tumbling_name: str,
    comparison_results: dict[str, list[ComparisonItem]],
    *,
    overwrite: bool = False,
    directory: Path | None = None,
) -> Path:
    if not comparison_results:
        raise CsvServiceError("Unable to save because no completed comparison result is available.")

    target = _safe_path(tumbling_name, directory)
    try:
        target.parent.mkdir(parents=True, exist_ok=True)
        rows = build_csv_rows(comparison_results)
        if overwrite:
            temporary = target.with_name(f".{target.name}.{uuid.uuid4().hex}.tmp")
            try:
                _write_rows(temporary, rows, "w")
                os.replace(temporary, target)
            finally:
                temporary.unlink(missing_ok=True)
        else:
            try:
                _write_rows(target, rows, "x")
            except FileExistsError as error:
                raise ResultsFileExistsError(target.name) from error
        return target
    except ResultsFileExistsError:
        raise
    except OSError as error:
        if not overwrite:
            target.unlink(missing_ok=True)
        raise CsvServiceError("The CSV could not be written. Check the saved-results folder permissions and try again.") from error


def _read_rows(path: Path) -> list[dict[str, str]]:
    try:
        with path.open("r", newline="", encoding="utf-8-sig") as csvfile:
            reader = csv.DictReader(csvfile)
            if reader.fieldnames is None or not {"Part Number", "Status"}.issubset(reader.fieldnames):
                raise InvalidSavedValidationError("The saved CSV is missing required columns.")
            rows = list(reader)
    except UnicodeError as error:
        raise InvalidSavedValidationError("The saved CSV encoding is invalid.") from error
    except csv.Error as error:
        raise InvalidSavedValidationError("The saved CSV contains malformed data.") from error
    except OSError as error:
        raise CsvServiceError("The saved validation could not be read.") from error

    for row in rows:
        if None in row or not (row.get("Part Number") or "").strip() or row.get("Status") not in LABEL_TO_STATUS:
            raise InvalidSavedValidationError("The saved CSV contains an invalid or incomplete row.")
    return rows


def _group_rows(rows: list[dict[str, str]]) -> dict[str, list[ComparisonItem]]:
    grouped = {status: [] for status in STATUS_ORDER}
    for row in rows:
        status = LABEL_TO_STATUS[row["Status"]]
        part_number = row["Part Number"]
        grouped[status].append(
            ComparisonItem(
                status=status,
                normalized_part_number=normalize_part_number(part_number),
                part_number=part_number,
                record=row.get("SAP Ready Record", ""),
                dataset="saved",
                reason=row.get("Reason", "") or "Loaded from the saved validation.",
                values={
                    "description": row.get("Description", ""),
                    "quantity": row.get("Quantity", ""),
                    "item": row.get("Position", ""),
                    "source": row.get("Source", ""),
                },
            )
        )
    return grouped


def load_results_csv(tumbling_name: str, *, directory: Path | None = None) -> LoadedValidation:
    path = _safe_path(tumbling_name, directory, require_exact_name=True)
    if not path.is_file():
        raise SavedValidationNotFoundError("This saved validation could not be found. It may have been deleted or moved.")
    rows = _read_rows(path)
    return LoadedValidation(
        tumbling_name=path.stem,
        filename=path.name,
        modified=datetime.fromtimestamp(path.stat().st_mtime),
        results=_group_rows(rows),
    )


def list_saved_validations(*, directory: Path | None = None) -> list[SavedValidationMetadata]:
    base = _results_directory(directory)
    try:
        base.mkdir(parents=True, exist_ok=True)
        paths = sorted(base.glob("*.csv"), key=lambda path: path.stat().st_mtime, reverse=True)
    except OSError as error:
        raise CsvServiceError("Past validations could not be read from the saved-results folder.") from error

    validations = []
    for path in paths:
        try:
            loaded = load_results_csv(path.stem, directory=base)
            validations.append(
                SavedValidationMetadata(path.stem, path.name, loaded.modified, loaded.counts, valid=True)
            )
        except CsvServiceError:
            validations.append(
                SavedValidationMetadata(
                    path.stem,
                    path.name,
                    datetime.fromtimestamp(path.stat().st_mtime),
                    {status: 0 for status in STATUS_ORDER},
                    valid=False,
                )
            )
    return validations


def filter_saved_validations(validations: list[SavedValidationMetadata], query: str) -> list[SavedValidationMetadata]:
    normalized_query = (query or "").strip().casefold()
    if not normalized_query:
        return validations
    return [item for item in validations if normalized_query in item.tumbling_name.casefold()]
