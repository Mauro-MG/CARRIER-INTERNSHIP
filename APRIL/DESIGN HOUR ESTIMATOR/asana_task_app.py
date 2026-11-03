"""Desktop Asana CSV generator for design-hour project files.

The app loads one project file, generates task rows with the existing qBOM
estimation logic, lets users edit Asana fields, and exports the selected table
as a CSV using the requested Asana-compatible headers.
"""

from __future__ import annotations

import csv
import copy
import hashlib
import json
import math
import queue
import re
import sys
import threading
import tkinter as tk
from dataclasses import dataclass, field
from datetime import date, datetime, timedelta, timezone
from pathlib import Path
from tkinter import filedialog, messagebox
from typing import Callable

import pandas as pd
import ttkbootstrap as ttk
from ttkbootstrap.constants import BOTH, DISABLED, END, LEFT, NORMAL, RIGHT, X
from ttkbootstrap.widgets import DateEntry
from asana_task_widgets import RowEditorDialog, TaskField, fit_dialog
from asana_user_lookup import (
    AssigneeNotFoundError,
    lookup_workspace_user_by_email,
)
from asana_api import (
    AsanaApiClient,
    upload_preview,
    write_upload_report,
)
from asana_upload import (
    UploadPreviewError,
    build_upload_preview,
    cache_workspace_user,
    load_discovery,
    load_upload_settings,
    options_from_discovery,
    write_upload_preview,
)

from estimation_rules import PRIMARY_L1_WEIGHT, SECONDARY_L1_WEIGHT, TERTIARY_L1_WEIGHT
from generate_estimated_tasks import (
    RAW_ESTIMATED_TIME_COLUMN,
    SCHEDULE_GROUP_COLUMN,
    GenerationError,
    build_tasks,
    load_project,
)


def app_storage_dir() -> Path:
    if getattr(sys, "frozen", False):
        return Path(sys.executable).resolve().parent
    return Path(__file__).resolve().parent


APP_DIR = app_storage_dir()
ASANA_UPLOAD_DIR = APP_DIR / "ASANA-UPLOADS"
OPTIONS_PATH = APP_DIR / "asana_task_options.json"
UPLOAD_JOURNAL_PATH = ASANA_UPLOAD_DIR / "asana_upload_journal.json"


@dataclass(frozen=True)
class AsanaFieldSpec:
    """One canonical definition for every field sent to Asana."""

    name: str
    field_type: str
    required: bool = False


ASANA_FIELD_SCHEMA = (
    AsanaFieldSpec("Name", "task_name", required=True),
    AsanaFieldSpec("Description", "long_text"),
    AsanaFieldSpec("Assignee", "user_email"),
    AsanaFieldSpec("Due Date", "date"),
    AsanaFieldSpec("Priority", "enum"),
    AsanaFieldSpec("Project", "enum"),
    AsanaFieldSpec("Status", "enum"),
    AsanaFieldSpec("Labels", "enum"),
    AsanaFieldSpec("Estimated Time", "number"),
    AsanaFieldSpec("ECN", "text"),
    AsanaFieldSpec("Task Type", "multi_enum"),
)
ASANA_EXPORT_COLUMNS = [spec.name for spec in ASANA_FIELD_SCHEMA]
ASANA_SCHEMA_BY_NAME = {spec.name: spec for spec in ASANA_FIELD_SCHEMA}

DISPLAY_COLUMNS = [
    "Name", "Estimated Time", "Labels", "Assignee", "Priority", "Due Date",
    "Status", "Product", "Project", "Task Type", "ECN", "Description",
]

# Product remains visible as generated reference data, but Asana owns the value.
# It is intentionally excluded from CSV/API writes and from task editing.
REFERENCE_ONLY_FIELDS = ["Product"]

EDITABLE_FIELDS = ASANA_EXPORT_COLUMNS.copy()
DROPDOWN_FIELDS = {spec.name for spec in ASANA_FIELD_SCHEMA if spec.field_type == "enum"}
MULTI_VALUE_FIELDS = {spec.name for spec in ASANA_FIELD_SCHEMA if spec.field_type == "multi_enum"}
DATE_FIELDS = {spec.name for spec in ASANA_FIELD_SCHEMA if spec.field_type == "date"}
NUMBER_FIELDS = {spec.name for spec in ASANA_FIELD_SCHEMA if spec.field_type == "number"}
CRUD_OPTION_GROUPS = ["Assignee", "Project", "Priority", "Status", "Labels", "Task Type"]
BULK_SCOPES = ["Selected rows", "Visible rows", "All tasks"]
INTERNAL_TASK_FIELDS = [SCHEDULE_GROUP_COLUMN, RAW_ESTIMATED_TIME_COLUMN]
DRAFT_TASK_COLUMNS = ASANA_EXPORT_COLUMNS + REFERENCE_ONLY_FIELDS + INTERNAL_TASK_FIELDS
WORKDAY_CAPACITY_HOURS = 6.0
DRAFT_FORMAT = "asana-task-builder-draft"
DRAFT_VERSION = 1
MANIFEST_FORMAT = "asana-task-export-manifest"
MANIFEST_VERSION = 1

FIELD_HELP = {
    "Name": "Asana task name. Required for reliable imports.",
    "Assignee": "Asana assignee. Use the user's email address.",
    "Priority": "Custom single-select field. Header must match the Asana field name.",
    "Due Date": "Asana due date. Generated qBOM tasks are scheduled automatically; exported as MM/DD/YYYY.",
    "Project": "Custom single-select field. The value must match one enabled Asana option.",
    "Status": "Custom single-select field. Header must match the Asana field name.",
    "Labels": "Custom single-select field. BOM and WTPART are separate label options.",
    "Estimated Time": "Hours in the app/CSV. API upload converts the value to ceiling whole minutes.",
    "ECN": "Custom text field.",
    "Task Type": "Custom multi-select field. Use Choose to select one or more enabled options.",
    "Description": "Asana task description.",
}

DEFAULT_OPTIONS = {
    "Assignee": [
        "JessicaJanett.Gonzalez@carrier.com",
        "Eduardo.Solano@carrier.com",
        "LuisDaniel.Aguirre@carrier.com",
        "Rodrigo.Moreno@carrier.com",
        "JoseHugo.MartinezVillarreal@carrier.com",
        "Kevin.Perez@carrier.com",
    ],
    "Project": [
        "No BU",
        "AHU",
        "Breeze",
        "VAR",
        "DOAS",
        "DW 27-35",
        "DW All",
        "XR",
        "TechDev",
        "B&I",
        "30CF",
        "CLT",
        "ART",
    ],
    "Labels": [
        "All", "ASSY-DRW", "L1-DRW", "DRW-C", "DRW-S", "WTPART",
        "BOM", "PRT", "ASSY", "GRAL", "SWI",
    ],
    "Task Type": [
        "Rework",
        "Rework Ext",
        "Task",
        "Attachments",
        "Support",
        "Meeting",
        "Training",
        "Review",
        "Audit",
        "SW",
    ],
    "Priority": ["Low", "Normal", "High", "Urgent"],
    "Status": ["Pending", "On Hold", "In Progress", "Done", "Backlog"],
}

REQUIRED_STATUS_OPTIONS = tuple(DEFAULT_OPTIONS["Status"])
LEGACY_LABEL_ALIASES = {"BOM/WT": "WTPART"}
LEGACY_VALUE_ALIASES = {
    "Labels": LEGACY_LABEL_ALIASES,
    "Project": {"DW ALL": "DW All", "30 CF": "30CF"},
    "Status": {"Completed": "Done"},
}
REMOVED_LEGACY_OPTIONS = {"Status": {"Blocked"}}
DEFAULT_ROW_VALUES = {
    "Name": "",
    "Assignee": "",
    "Product": "",
    "Priority": "Normal",
    "Due Date": "",
    "Project": "DOAS",
    "Status": "Pending",
    "Labels": "",
    "Estimated Time": "",
    "ECN": "",
    "Task Type": "SW",
    "Description": "",
}


def clean_options(raw_options: object) -> dict[str, list[str]]:
    options = {key: value.copy() for key, value in DEFAULT_OPTIONS.items()}
    if not isinstance(raw_options, dict):
        return options
    for group in CRUD_OPTION_GROUPS:
        values = raw_options.get(group)
        if isinstance(values, list):
            cleaned = [str(value).strip() for value in values if str(value).strip()]
            aliases = LEGACY_VALUE_ALIASES.get(group, {})
            cleaned = [aliases.get(value, value) for value in cleaned]
            cleaned = [
                value for value in cleaned
                if value not in REMOVED_LEGACY_OPTIONS.get(group, set())
            ]
            if group == "Status":
                cleaned.extend(value for value in REQUIRED_STATUS_OPTIONS if value not in cleaned)
            options[group] = list(dict.fromkeys(cleaned))
    return options


def load_saved_options(path: Path | None = None) -> dict[str, list[str]]:
    path = path or OPTIONS_PATH
    try:
        with path.open("r", encoding="utf-8") as options_file:
            return clean_options(json.load(options_file))
    except (FileNotFoundError, json.JSONDecodeError, OSError):
        return clean_options({})


def save_options(options: dict[str, list[str]], path: Path | None = None) -> None:
    path = path or OPTIONS_PATH
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open("w", encoding="utf-8") as options_file:
        json.dump(clean_options(options), options_file, indent=2)
        options_file.write("\n")


class DraftFormatError(ValueError):
    """Raised when a saved task draft is missing or uses an unsupported format."""


def utc_timestamp() -> str:
    return datetime.now(timezone.utc).isoformat(timespec="seconds")


def file_sha256(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as source_file:
        for chunk in iter(lambda: source_file.read(1024 * 1024), b""):
            digest.update(chunk)
    return digest.hexdigest()


def source_trace_for_project(project_path: Path | None) -> dict[str, object]:
    if project_path is None:
        return {}
    trace: dict[str, object] = {
        "path": str(project_path),
        "name": project_path.name,
    }
    if not project_path.is_file():
        trace["available"] = False
        return trace
    trace["available"] = True
    trace["sha256"] = file_sha256(project_path)
    project_excel = None
    try:
        project, project_excel = load_project(project_path)
        references = [
            str(value).strip()
            for value in project.get("QBomSaved", pd.Series(dtype=object)).tolist()
            if not pd.isna(value) and str(value).strip()
        ]
        trace["qbom_references"] = list(dict.fromkeys(references))
    except (GenerationError, OSError, ValueError, pd.errors.ParserError):
        trace["qbom_references"] = []
    finally:
        if project_excel is not None:
            project_excel.close()
    return trace


def schema_snapshot() -> list[dict[str, object]]:
    return [
        {"name": spec.name, "type": spec.field_type, "required": spec.required}
        for spec in ASANA_FIELD_SCHEMA
    ]


def build_draft_document(
    records: list[dict[str, str]],
    options: dict[str, list[str]],
    source_trace: dict[str, object] | None = None,
    schedule: dict[str, object] | None = None,
    history_actions: list[str] | None = None,
) -> dict[str, object]:
    return {
        "format": DRAFT_FORMAT,
        "version": DRAFT_VERSION,
        "saved_at": utc_timestamp(),
        "schema": schema_snapshot(),
        "source": copy.deepcopy(source_trace or {}),
        "schedule": copy.deepcopy(schedule or {}),
        "options": clean_options(options),
        "tasks": [
            {column: str(record.get(column, "") or "") for column in DRAFT_TASK_COLUMNS}
            for record in records
        ],
        "history_actions": list(history_actions or []),
    }


def parse_draft_document(
    document: object,
) -> tuple[list[dict[str, str]], dict[str, list[str]], dict[str, object], dict[str, object]]:
    if not isinstance(document, dict) or document.get("format") != DRAFT_FORMAT:
        raise DraftFormatError("This is not an Asana task builder draft.")
    if document.get("version") != DRAFT_VERSION:
        raise DraftFormatError(
            f"Draft version {document.get('version')!r} is not supported; expected version {DRAFT_VERSION}."
        )
    raw_tasks = document.get("tasks")
    if not isinstance(raw_tasks, list):
        raise DraftFormatError("The draft does not contain a valid task list.")
    tasks = []
    for index, raw_task in enumerate(raw_tasks, start=1):
        if not isinstance(raw_task, dict):
            raise DraftFormatError(f"Task {index} is not a valid object.")
        tasks.append({
            column: str(raw_task.get(column, "") or "")
            for column in DRAFT_TASK_COLUMNS
        })
    source = document.get("source")
    schedule = document.get("schedule")
    return (
        tasks,
        clean_options(document.get("options")),
        copy.deepcopy(source if isinstance(source, dict) else {}),
        copy.deepcopy(schedule if isinstance(schedule, dict) else {}),
    )


def write_json_document(path: Path, document: dict[str, object]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open("w", encoding="utf-8") as output_file:
        json.dump(document, output_file, indent=2, ensure_ascii=False)
        output_file.write("\n")


def load_draft_document(
    path: Path,
) -> tuple[list[dict[str, str]], dict[str, list[str]], dict[str, object], dict[str, object]]:
    try:
        with path.open("r", encoding="utf-8") as draft_file:
            document = json.load(draft_file)
    except json.JSONDecodeError as error:
        raise DraftFormatError(f"The draft contains invalid JSON: {error}") from error
    return parse_draft_document(document)


def build_export_manifest(
    csv_path: Path,
    records: list[dict[str, str]],
    scope: str,
    source_trace: dict[str, object] | None = None,
    draft_path: Path | None = None,
    schedule: dict[str, object] | None = None,
) -> dict[str, object]:
    estimated_time_total = sum(
        asana_duration_hours(record.get("Estimated Time", ""))
        for record in records
    )
    return {
        "format": MANIFEST_FORMAT,
        "version": MANIFEST_VERSION,
        "exported_at": utc_timestamp(),
        "csv_file": csv_path.name,
        "csv_sha256": file_sha256(csv_path),
        "task_count": len(records),
        "estimated_time_total": estimated_time_total,
        "scope": scope,
        "estimation_weights": {
            "primary": PRIMARY_L1_WEIGHT,
            "secondary": SECONDARY_L1_WEIGHT,
            "tertiary": TERTIARY_L1_WEIGHT,
        },
        "schema": schema_snapshot(),
        "source": copy.deepcopy(source_trace or {}),
        "schedule": copy.deepcopy(schedule or {}),
        "draft_path": str(draft_path) if draft_path else "",
    }


@dataclass
class TaskRow:
    row_id: int
    values: dict[str, str] = field(default_factory=dict)

    def get(self, column: str) -> str:
        return str(self.values.get(column, "") or "")

    def set(self, column: str, value: object) -> None:
        text = "" if value is None else str(value)
        self.values[column] = LEGACY_VALUE_ALIASES.get(column, {}).get(text.strip(), text)


class TaskTableModel:
    def __init__(self) -> None:
        self._rows: list[TaskRow] = []
        self._next_id = 1

    @property
    def rows(self) -> list[TaskRow]:
        return self._rows

    def clear(self) -> None:
        self._rows.clear()
        self._next_id = 1

    def add(self, values: dict[str, object] | None = None) -> TaskRow:
        merged = {column: "" for column in DISPLAY_COLUMNS}
        merged.update(DEFAULT_ROW_VALUES)
        merged.update({column: "" for column in INTERNAL_TASK_FIELDS})
        if values:
            for key, value in values.items():
                if key in DISPLAY_COLUMNS or key in INTERNAL_TASK_FIELDS:
                    text = "" if value is None else str(value)
                    merged[key] = LEGACY_VALUE_ALIASES.get(key, {}).get(text.strip(), text)

        row = TaskRow(self._next_id, {key: str(value or "") for key, value in merged.items()})
        self._next_id += 1
        self._rows.append(row)
        return row

    def remove(self, row_ids: set[int]) -> None:
        self._rows = [row for row in self._rows if row.row_id not in row_ids]

    def by_id(self, row_id: int) -> TaskRow | None:
        return next((row for row in self._rows if row.row_id == row_id), None)

    def selected_rows(self, item_ids: tuple[str, ...]) -> list[TaskRow]:
        selected = []
        for item_id in item_ids:
            try:
                row_id = int(item_id)
            except ValueError:
                continue
            row = self.by_id(row_id)
            if row:
                selected.append(row)
        return selected

    def to_export_records(self, rows: list[TaskRow] | None = None) -> list[dict[str, str]]:
        source = rows if rows is not None else self._rows
        return [
            {
                column: export_estimated_time(row) if column == "Estimated Time" else row.get(column)
                for column in ASANA_EXPORT_COLUMNS
            }
            for row in source
        ]

    def to_draft_records(self) -> list[dict[str, str]]:
        return [
            {column: row.get(column) for column in DRAFT_TASK_COLUMNS}
            for row in self._rows
        ]


def roll_forward_to_workday(value: date) -> date:
    while value.weekday() >= 5:
        value += timedelta(days=1)
    return value


def add_workdays(start_date: date, offset: int) -> date:
    current = roll_forward_to_workday(start_date)
    remaining = max(0, int(offset))
    while remaining:
        current += timedelta(days=1)
        if current.weekday() < 5:
            remaining -= 1
    return current


def parse_schedule_date(value: object) -> date | None:
    parsed = pd.to_datetime(str(value or "").strip(), errors="coerce")
    return None if pd.isna(parsed) else parsed.date()


def calculate_qbom_schedule(
    rows: list[TaskRow],
    start_date: date,
) -> tuple[dict[int, str], date | None, dict[str, float]]:
    """Schedule each qBOM independently with six hours of weekday capacity."""
    effective_start = roll_forward_to_workday(start_date)
    cumulative_by_group: dict[str, float] = {}
    due_dates: dict[int, str] = {}
    target_date: date | None = None
    for row in rows:
        group = row.get(SCHEDULE_GROUP_COLUMN).strip()
        if not group:
            continue
        estimated_time = finite_number(row.get("Estimated Time"))
        if estimated_time is None or estimated_time < 0:
            due_dates[row.row_id] = ""
            continue
        duration_hours = estimated_time
        if estimated_time == 0:
            fallback_minutes = rounded_fallback_minutes(row)
            if fallback_minutes is not None:
                duration_hours = fallback_minutes / 60
        cumulative = cumulative_by_group.get(group, 0.0) + duration_hours
        cumulative_by_group[group] = cumulative
        workday_offset = max(0, math.ceil(cumulative / WORKDAY_CAPACITY_HOURS) - 1)
        due_date = add_workdays(effective_start, workday_offset)
        due_dates[row.row_id] = due_date.strftime("%m/%d/%Y")
        target_date = due_date if target_date is None else max(target_date, due_date)
    return due_dates, target_date, cumulative_by_group


def normalize_date_entry(value: str) -> str:
    return value.strip()


def format_asana_date(value: object) -> str:
    text = str(value or "").strip()
    if not text:
        return ""
    parsed = pd.to_datetime(text, errors="coerce")
    if pd.isna(parsed):
        return text
    return parsed.strftime("%m/%d/%Y")


def format_asana_number(value: object) -> str:
    text = str(value or "").strip()
    if not text:
        return ""
    number = pd.to_numeric(pd.Series([text]), errors="coerce").iloc[0]
    if pd.isna(number):
        return text
    return f"{float(number):g}"


def format_export_value(column: str, value: object) -> str:
    if column in DATE_FIELDS:
        return format_asana_date(value)
    if column in NUMBER_FIELDS:
        return format_asana_number(value)
    text = str(value or "").strip()
    return LEGACY_VALUE_ALIASES.get(column, {}).get(text, text)


def generated_task_to_ui_row(task: pd.Series) -> dict[str, object]:
    """Map generator output columns into the desktop table column names."""
    return {
        "Name": task.get("Name", ""),
        "Assignee": task.get("Assignee", ""),
        "Product": task.get("Product", DEFAULT_ROW_VALUES["Product"]),
        "Priority": task.get("Priority", DEFAULT_ROW_VALUES["Priority"]),
        "Due Date": task.get("Due date", ""),
        "Project": task.get("Project", DEFAULT_ROW_VALUES["Project"]),
        "Status": task.get("Status", DEFAULT_ROW_VALUES["Status"]),
        "Labels": format_export_value("Labels", task.get("Labels", "")),
        "Estimated Time": task.get("Estimated time", ""),
        "ECN": task.get("ECN", ""),
        "Task Type": task.get("Task Type", DEFAULT_ROW_VALUES["Task Type"]),
        "Description": task.get("Description", ""),
        SCHEDULE_GROUP_COLUMN: task.get(SCHEDULE_GROUP_COLUMN, ""),
        RAW_ESTIMATED_TIME_COLUMN: task.get(RAW_ESTIMATED_TIME_COLUMN, ""),
    }


def generate_rows_from_project(project_path: Path) -> list[dict[str, object]]:
    project, project_excel = load_project(project_path)
    tasks, _, _ = build_tasks(project, project_path, project_excel)
    return [generated_task_to_ui_row(task) for _, task in tasks.iterrows()]


def export_csv(path: Path, records: list[dict[str, str]]) -> None:
    with path.open("w", newline="", encoding="utf-8-sig") as csv_file:
        writer = csv.DictWriter(csv_file, fieldnames=ASANA_EXPORT_COLUMNS, extrasaction="ignore")
        writer.writeheader()
        for record in records:
            writer.writerow({
                column: format_export_value(column, record.get(column, ""))
                for column in ASANA_EXPORT_COLUMNS
            })


def safe_filename_stem(value: str) -> str:
    stem = re.sub(r'[<>:"/\\|?*\x00-\x1f]+', "_", value).strip(" ._")
    return stem or "asana_tasks"


def next_available_path(path: Path) -> Path:
    if not path.exists():
        return path
    for number in range(2, 10000):
        candidate = path.with_name(f"{path.stem}_{number}{path.suffix}")
        if not candidate.exists():
            return candidate
    raise OSError(f"Could not find an available filename for {path.name}")


def automatic_export_path(project_path: Path | None, selected_only: bool) -> Path:
    stem = safe_filename_stem(project_path.stem if project_path else "asana_tasks")
    suffix = "_selected_asana_tasks.csv" if selected_only else "_asana_tasks.csv"
    if stem == "asana_tasks":
        suffix = "_selected.csv" if selected_only else ".csv"
    return next_available_path(ASANA_UPLOAD_DIR / f"{stem}{suffix}")


def automatic_upload_preview_path(project_path: Path | None, selected_only: bool) -> Path:
    stem = safe_filename_stem(project_path.stem if project_path else "asana_tasks")
    suffix = "_selected_asana_api_preview.json" if selected_only else "_asana_api_preview.json"
    return next_available_path(ASANA_UPLOAD_DIR / f"{stem}{suffix}")


def automatic_upload_report_path(project_path: Path | None, selected_only: bool) -> Path:
    stem = safe_filename_stem(project_path.stem if project_path else "asana_tasks")
    suffix = "_selected_asana_upload_report.json" if selected_only else "_asana_upload_report.json"
    return next_available_path(ASANA_UPLOAD_DIR / f"{stem}{suffix}")


def finite_number(value: object) -> float | None:
    try:
        number = float(str(value).strip())
    except (ValueError, TypeError):
        return None
    return number if math.isfinite(number) else None


def rounded_fallback_minutes(row: TaskRow | dict[str, str]) -> int | None:
    """Return whole fallback minutes only for a generated estimate reconciled to zero."""
    estimated_time = finite_number(row.get("Estimated Time"))
    raw_estimate = finite_number(row.get(RAW_ESTIMATED_TIME_COLUMN))
    if estimated_time == 0 and raw_estimate is not None and 0 < raw_estimate < 1:
        return math.ceil(raw_estimate * 60)
    return None


def export_estimated_time(row: TaskRow) -> str:
    fallback_minutes = rounded_fallback_minutes(row)
    return f"{fallback_minutes} min" if fallback_minutes is not None else row.get("Estimated Time")


def asana_duration_hours(value: object) -> float:
    """Convert an exported Asana hour or minute duration into hours for audit totals."""
    text = str(value or "").strip()
    minute_match = re.fullmatch(r"(\d+)\s*(?:m|min)", text, flags=re.IGNORECASE)
    if minute_match:
        return int(minute_match.group(1)) / 60
    return finite_number(text) or 0.0


def field_errors(
    values: dict[str, str],
    options: dict[str, list[str]] | None = None,
) -> list[str]:
    """Validate entered fields without recalculating or adjusting estimates."""
    errors = []
    options = options or DEFAULT_OPTIONS
    if "Name" in values and not str(values["Name"]).strip():
        errors.append("Name is required.")
    for spec in ASANA_FIELD_SCHEMA:
        if spec.name not in values or spec.field_type not in {"enum", "multi_enum"}:
            continue
        raw_value = str(values.get(spec.name, "")).strip()
        if spec.required and not raw_value:
            errors.append(f"{spec.name} is required.")
            continue
        selected = (
            [part.strip() for part in raw_value.split(",") if part.strip()]
            if spec.field_type == "multi_enum" else ([raw_value] if raw_value else [])
        )
        available = options.get(spec.name, [])
        for value in selected:
            canonical = LEGACY_VALUE_ALIASES.get(spec.name, {}).get(value, value)
            if canonical not in available:
                errors.append(f"{spec.name} '{canonical}' is not an available Asana option.")
    for name in DATE_FIELDS:
        value = values.get(name, "").strip()
        if value and pd.isna(pd.to_datetime(value, errors="coerce")):
            errors.append(f"{name}: use a valid date, such as 09/14/2026.")
    value = values.get("Estimated Time", "").strip()
    if value and (finite_number(value) is None or finite_number(value) < 0):
        errors.append("Estimated Time must be a finite, non-negative number.")
    return errors


def review_notes(
    values: dict[str, str],
    options: dict[str, list[str]] | None = None,
) -> list[str]:
    notes = field_errors(values, options)
    value = values.get("Estimated Time", "").strip()
    number = finite_number(value)
    if not value:
        notes.append("No estimated time.")
    elif number == 0:
        fallback_minutes = rounded_fallback_minutes(values)
        raw_estimate = finite_number(values.get(RAW_ESTIMATED_TIME_COLUMN, ""))
        if fallback_minutes is not None and raw_estimate is not None:
            notes.append(
                f"Decimal estimate {raw_estimate:g} h becomes {fallback_minutes} min in Asana "
                "and in the schedule."
            )
        else:
            notes.append("0 hours: the source total is zero. Verify the source.")
    elif number is not None and number > 0 and (number > 40 or not number.is_integer()):
        notes.append("Manual estimate is outside the generated whole-hour / 40-hour rule.")
    return notes


def merge_values(existing: str, new: str, mode: str) -> str:
    old_values = [part.strip() for part in existing.split(",") if part.strip()]
    new_values = [part.strip() for part in new.split(",") if part.strip()]
    if mode == "Add values":
        values = old_values + new_values
    elif mode == "Remove values":
        values = [part for part in old_values if part not in new_values]
    else:
        values = new_values
    return ", ".join(dict.fromkeys(values))


def table_sort_key(column: str, value: str) -> tuple:
    if column in NUMBER_FIELDS:
        number = finite_number(value)
        return (number is None, number or 0)
    if column in DATE_FIELDS:
        date = pd.to_datetime(value, errors="coerce")
        return (pd.isna(date), 0 if pd.isna(date) else date.value)
    return (not value, value.casefold())


class OptionManagerDialog(ttk.Toplevel):
    def __init__(
        self,
        parent: ttk.Window,
        options: dict[str, list[str]],
        on_change: Callable[[], None],
        assignee_lookup: Callable[[str], object] | None = None,
    ) -> None:
        super().__init__(parent)
        self.title("Manage dropdown options")
        fit_dialog(self, parent, 780, 520)
        self.minsize(660, 450)
        self.resizable(True, True)
        self.transient(parent)
        self.grab_set()

        self.options = options
        self.on_change = on_change
        self.assignee_lookup = assignee_lookup
        self._lookup_queue: queue.Queue = queue.Queue()
        self._lookup_running = False
        self.current_group = ttk.StringVar(value=CRUD_OPTION_GROUPS[0])
        self.input_value = ttk.StringVar()

        shell = ttk.Frame(self, padding=16)
        shell.pack(fill=BOTH, expand=True)
        shell.columnconfigure(1, weight=1)
        shell.rowconfigure(0, weight=1)

        group_frame = ttk.Labelframe(shell, text="Dropdown", padding=8)
        group_frame.grid(row=0, column=0, sticky="ns", padx=(0, 12))
        for group in CRUD_OPTION_GROUPS:
            ttk.Radiobutton(
                group_frame,
                text=group,
                value=group,
                variable=self.current_group,
                command=self._refresh,
                bootstyle="toolbutton",
            ).pack(fill=X, pady=2)

        editor = ttk.Frame(shell)
        editor.grid(row=0, column=1, sticky="nsew")
        editor.rowconfigure(0, weight=1)
        editor.columnconfigure(0, weight=1)

        self.listbox = tk.Listbox(editor, height=14, exportselection=False,
                                  font="TkDefaultFont", relief="solid", borderwidth=1,
                                  selectbackground="#2c3e50", selectforeground="white")
        self.listbox.grid(row=0, column=0, sticky="nsew")
        scrollbar = ttk.Scrollbar(editor, command=self.listbox.yview)
        scrollbar.grid(row=0, column=1, sticky="ns")
        self.listbox.configure(yscrollcommand=scrollbar.set)
        self.listbox.bind("<<ListboxSelect>>", self._select_option)

        input_row = ttk.Frame(editor)
        input_row.grid(row=1, column=0, columnspan=2, sticky="ew", pady=(12, 0))
        input_row.columnconfigure(0, weight=1)
        ttk.Entry(input_row, textvariable=self.input_value).grid(row=0, column=0, sticky="ew", padx=(0, 8))
        self.add_option_button = ttk.Button(
            input_row, text="Add", command=self._add, bootstyle="success"
        )
        self.add_option_button.grid(row=0, column=1, padx=4)
        self.rename_option_button = ttk.Button(
            input_row, text="Rename", command=self._rename, bootstyle="primary"
        )
        self.rename_option_button.grid(row=0, column=2, padx=4)
        self.delete_option_button = ttk.Button(
            input_row, text="Delete", command=self._delete, bootstyle="danger"
        )
        self.delete_option_button.grid(row=0, column=3, padx=(4, 0))

        self.lookup_status = tk.StringVar()
        ttk.Label(
            editor,
            textvariable=self.lookup_status,
            bootstyle="secondary",
            wraplength=440,
        ).grid(row=2, column=0, columnspan=2, sticky="w", pady=(8, 0))

        footer = ttk.Frame(shell)
        footer.grid(row=1, column=0, columnspan=2, sticky="ew", pady=(12, 0))
        ttk.Label(
            footer,
            text="Assignee emails are verified individually in Asana. Other options are saved next to the app.",
            bootstyle="secondary",
        ).pack(side=LEFT)
        ttk.Button(footer, text="Close", command=self.destroy, bootstyle="secondary").pack(side=RIGHT)

        self._refresh()

    def _selected_index(self) -> int | None:
        selected = self.listbox.curselection()
        return int(selected[0]) if selected else None

    def _refresh(self) -> None:
        group = self.current_group.get()
        self.listbox.delete(0, END)
        for option in self.options.get(group, []):
            self.listbox.insert(END, option)
        self.input_value.set("")

    def _select_option(self, _event: object | None = None) -> None:
        index = self._selected_index()
        if index is None:
            return
        group = self.current_group.get()
        self.input_value.set(self.options[group][index])

    def _add(self) -> None:
        group = self.current_group.get()
        value = self.input_value.get().strip()
        if not value:
            return
        if value in self.options[group]:
            self._refresh()
            return
        if group == "Assignee" and self.assignee_lookup is not None:
            self._start_assignee_lookup(value, action="add")
            return
        self._commit_add(group, value)

    def _commit_add(self, group: str, value: str) -> None:
        self.master.checkpoint("add option")
        self.options[group].append(value)
        self.options[group].sort(key=str.casefold)
        self.on_change()
        self._refresh()

    def _rename(self) -> None:
        index = self._selected_index()
        value = self.input_value.get().strip()
        if index is None or not value:
            return
        group = self.current_group.get()
        old_value = self.options[group][index]
        if group == "Assignee" and self.assignee_lookup is not None and value != old_value:
            self._start_assignee_lookup(value, action="rename", index=index)
            return
        self._commit_rename(group, index, value)

    def _commit_rename(self, group: str, index: int, value: str) -> None:
        self.master.checkpoint("rename option")
        old_value = self.options[group][index]
        self.options[group][index] = value
        self.options[group] = sorted(dict.fromkeys(self.options[group]), key=str.casefold)
        self._replace_existing_values(group, old_value, value)
        self.on_change()
        self._refresh()

    def _start_assignee_lookup(self, email: str, *, action: str, index: int | None = None) -> None:
        if self._lookup_running or self.assignee_lookup is None:
            return
        self._lookup_running = True
        self.lookup_status.set(f"Checking {email} in the configured Asana workspace…")
        self._set_lookup_buttons(False)

        def worker() -> None:
            try:
                user = self.assignee_lookup(email)
                self._lookup_queue.put((action, index, user, None))
            except Exception as error:
                self._lookup_queue.put((action, index, None, error))

        threading.Thread(
            target=worker,
            daemon=True,
            name="asana-assignee-lookup",
        ).start()
        self.after(80, self._poll_assignee_lookup)

    def _poll_assignee_lookup(self) -> None:
        try:
            action, index, user, error = self._lookup_queue.get_nowait()
        except queue.Empty:
            self.after(80, self._poll_assignee_lookup)
            return
        self._lookup_running = False
        self._set_lookup_buttons(True)
        if error is not None:
            self.lookup_status.set("Assignee was not added.")
            if isinstance(error, AssigneeNotFoundError):
                messagebox.showwarning("Assignee not found", str(error), parent=self)
            else:
                messagebox.showerror("Could not validate assignee", str(error), parent=self)
            return
        canonical_email = str(getattr(user, "email", "") or "").strip()
        if not canonical_email:
            self.lookup_status.set("Assignee was not added.")
            messagebox.showerror(
                "Could not validate assignee",
                "Asana did not return a usable email address.",
                parent=self,
            )
            return
        if action == "rename" and index is not None:
            self._commit_rename("Assignee", index, canonical_email)
        elif not any(
            existing.casefold() == canonical_email.casefold()
            for existing in self.options["Assignee"]
        ):
            self._commit_add("Assignee", canonical_email)
        else:
            self._refresh()
        self.lookup_status.set(f"Verified by Asana: {canonical_email}")

    def _set_lookup_buttons(self, enabled: bool) -> None:
        state = NORMAL if enabled else DISABLED
        for button in (
            self.add_option_button,
            self.rename_option_button,
            self.delete_option_button,
        ):
            button.configure(state=state)

    def _delete(self) -> None:
        index = self._selected_index()
        if index is None:
            return
        group = self.current_group.get()
        value = self.options[group][index]
        if messagebox.askyesno("Delete option", f"Delete '{value}' from {group} options?", parent=self):
            self.master.checkpoint("delete option")
            del self.options[group][index]
            self.on_change()
            self._refresh()

    def _replace_existing_values(self, group: str, old_value: str, new_value: str) -> None:
        app = self.master
        model = getattr(app, "model", None)
        if model is None:
            return
        for row in model.rows:
            if group in MULTI_VALUE_FIELDS:
                values = [part.strip() for part in row.get(group).split(",") if part.strip()]
                row.set(group, ", ".join(dict.fromkeys(new_value if part == old_value else part for part in values)))
            elif row.get(group) == old_value:
                row.set(group, new_value)


class AsanaTaskApp(ttk.Window):
    """Task review workspace. The generator and CSV serializer remain independent."""

    OVERVIEW_COLUMNS = ["Name", "Estimated Time", "Labels", "Assignee", "Priority", "Due Date", "Status"]

    def __init__(self) -> None:
        super().__init__(themename="flatly")
        self.title("Asana task builder")
        width = min(1440, self.winfo_screenwidth() - 60)
        height = min(860, self.winfo_screenheight() - 100)
        self.geometry(f"{width}x{height}")
        self.minsize(960, 620)
        self.style.configure("Treeview", rowheight=34, font=("Segoe UI", 10))
        self.style.configure("Treeview.Heading", font=("Segoe UI", 10, "bold"))
        self.model = TaskTableModel()
        self.options = load_saved_options()
        try:
            cached_settings = load_upload_settings(APP_DIR)
            cached_options = options_from_discovery(load_discovery(cached_settings.discovery_path))
            for group, values in cached_options.items():
                if values:
                    self.options[group] = values
        except (OSError, UploadPreviewError):
            # The generator and CSV workflow remain usable without API metadata.
            pass
        self.current_project_path: Path | None = None
        self.current_draft_path: Path | None = None
        self.source_trace: dict[str, object] = {}
        self.history: list[tuple] = []
        self._exported_records: list[dict[str, str]] = []
        self._busy = False
        self._load_queue = queue.Queue()
        self._upload_queue = queue.Queue()
        self._uploading_all_rows = False
        self._search_after = None
        self._sort_column = ""
        self._sort_reverse = False
        self._issues: dict[int, list[str]] = {}
        self._drag_anchor_iid = ""
        self._drag_selecting = False
        self._scheduling = False
        self.bulk_field = tk.StringVar(value="Assignee")
        self.bulk_mode = tk.StringVar(value="Replace value")
        self.bulk_scope = tk.StringVar(value=BULK_SCOPES[0])
        default_start = roll_forward_to_workday(date.today()).strftime("%m/%d/%Y")
        self.start_date_text = tk.StringVar(value=default_start)
        self.target_date_text = tk.StringVar(value="—")
        self.search_text = tk.StringVar()
        self.review_only = tk.BooleanVar(value=False)
        self.column_view = tk.StringVar(value="Overview")
        self.export_scope = tk.StringVar(value="All tasks")
        self.status_text = tk.StringVar(value="Ready. Open a project or add your first task.")
        self.source_text = tk.StringVar(value="No project loaded")
        self.summary_text = tk.StringVar()
        self.selected_count_text = tk.StringVar(value="No tasks selected")
        self.detail_text = tk.StringVar(value="Select a task to see its full name and review notes.")
        self.bulk_help_text = tk.StringVar()
        self._build_ui()
        self.refresh_table()
        self.search_text.trace_add("write", self._schedule_search)
        self.protocol("WM_DELETE_WINDOW", self.request_close)
        self.bind("<Control-o>", lambda event: self._shortcut(event, self.load_project_file))
        self.bind("<Control-s>", lambda event: self._shortcut(event, self.export_selected_csv))
        self.bind("<Control-Shift-S>", lambda event: self._shortcut(event, self.save_draft_file))
        self.bind("<Control-n>", lambda event: self._shortcut(event, self.add_row))
        self.bind("<Control-f>", lambda event: self._shortcut(event, self.search_entry.focus_set))
        self.bind("<Control-z>", self._undo_shortcut)
        self.bind("<F1>", lambda event: self._shortcut(event, self.show_help))

    @property
    def dirty(self) -> bool:
        return self.model.to_export_records() != self._exported_records

    def _shortcut(self, event, command):
        if event.widget.winfo_toplevel() is self and not self._busy:
            command()
            return "break"

    def _undo_shortcut(self, event):
        # Keep native text undo when the cursor is inside an input.
        if event.widget.winfo_class() in {"Text", "Entry", "TEntry", "TCombobox"}:
            return None
        return self._shortcut(event, self.undo)

    def _build_ui(self) -> None:
        self.columnconfigure(0, weight=1)
        self.rowconfigure(3, weight=1)

        header = ttk.Frame(self, padding=(20, 16), bootstyle="primary")
        header.grid(row=0, column=0, sticky="ew")
        heading = ttk.Frame(header, bootstyle="primary")
        heading.pack(side=LEFT, fill=X, expand=True)
        ttk.Label(heading, text="Asana task builder", font=("Segoe UI", 21, "bold"),
                  bootstyle="inverse-primary").pack(anchor="w")
        ttk.Label(heading, text="1  Open project     /     2  Review & assign     /     3  Export or upload",
                  bootstyle="inverse-primary").pack(anchor="w", pady=(3, 0))
        self.load_button = ttk.Button(header, text="Generate from project…", command=self.load_project_file,
                                      bootstyle="light-outline")
        self.load_button.pack(side=RIGHT, padx=(16, 0))
        self.open_draft_button = ttk.Button(
            header, text="Open draft…", command=self.open_draft_file, bootstyle="light-outline"
        )
        self.open_draft_button.pack(side=RIGHT, padx=(8, 0))
        self.save_draft_button = ttk.Button(
            header, text="Save draft…", command=self.save_draft_file, bootstyle="light-outline"
        )
        self.save_draft_button.pack(side=RIGHT, padx=(8, 0))

        context = ttk.Frame(self, padding=(20, 10))
        context.grid(row=1, column=0, sticky="ew")
        context.columnconfigure(0, weight=1)
        ttk.Label(context, textvariable=self.source_text, font=("Segoe UI", 11, "bold"),
                  wraplength=680).grid(row=0, column=0, sticky="w")
        ttk.Label(context, textvariable=self.summary_text, bootstyle="secondary").grid(
            row=1, column=0, sticky="w", pady=(4, 0))
        schedule = ttk.Labelframe(context, text="Project schedule", padding=(10, 6))
        schedule.grid(row=0, column=1, rowspan=2, sticky="e", padx=(12, 0))
        ttk.Label(schedule, text="Start Date").grid(row=0, column=0, sticky="w", padx=(0, 6))
        self.start_date_entry = DateEntry(schedule, dateformat="%m/%d/%Y", bootstyle="primary", width=12)
        self.start_date_entry.grid(row=0, column=1, sticky="ew")
        self.start_date_entry.entry.delete(0, "end")
        self.start_date_entry.entry.insert(0, self.start_date_text.get())
        self.start_date_entry.bind("<<DateEntrySelected>>", self._schedule_from_ui_event)
        self.start_date_entry.entry.bind("<Return>", self._schedule_from_ui_event)
        self.start_date_entry.entry.bind("<FocusOut>", self._schedule_from_ui_event)
        ttk.Label(schedule, text="Target Date").grid(row=1, column=0, sticky="w", padx=(0, 6), pady=(5, 0))
        ttk.Label(schedule, textvariable=self.target_date_text, font=("Segoe UI", 10, "bold")).grid(
            row=1, column=1, sticky="w", pady=(5, 0)
        )
        self.schedule_button = ttk.Button(
            schedule,
            text="Recalculate",
            command=self.recalculate_schedule,
            bootstyle="secondary-outline",
        )
        self.schedule_button.grid(row=0, column=2, rowspan=2, padx=(8, 0))
        self.options_button = ttk.Button(context, text="Manage options", command=self.open_option_manager,
                                         bootstyle="secondary-outline")
        self.options_button.grid(row=0, column=2, rowspan=2, padx=(12, 0))
        ttk.Button(context, text="Help", command=self.show_help,
                   bootstyle="secondary-link").grid(row=0, column=3, rowspan=2, padx=(8, 0))

        filters = ttk.Frame(self, padding=(20, 0, 20, 10))
        filters.grid(row=2, column=0, sticky="ew")
        filters.columnconfigure(1, weight=1)
        ttk.Label(filters, text="Search").grid(row=0, column=0, padx=(0, 8))
        self.search_entry = ttk.Entry(filters, textvariable=self.search_text)
        self.search_entry.grid(row=0, column=1, sticky="ew")
        self.search_entry.bind("<Escape>", lambda _event: self.clear_filters())
        ttk.Button(filters, text="Reset", command=self.clear_filters,
                   bootstyle="secondary-link").grid(row=0, column=2, padx=(4, 12))
        ttk.Checkbutton(filters, text="Needs review", variable=self.review_only,
                        command=self.refresh_table, bootstyle="round-toggle").grid(row=0, column=3, padx=(0, 16))
        ttk.Label(filters, text="Columns").grid(row=0, column=4, padx=(0, 8))
        view = ttk.Combobox(filters, values=["Overview", "All fields"], textvariable=self.column_view,
                            state="readonly", width=12)
        view.grid(row=0, column=5)
        view.bind("<<ComboboxSelected>>", lambda _event: self._set_column_view())

        main = ttk.Panedwindow(self, orient="horizontal")
        main.grid(row=3, column=0, sticky="nsew", padx=20)
        self.main_panes = main
        self._sidebar_width = 300
        table_frame = ttk.Frame(main)
        table_frame.columnconfigure(0, weight=1)
        table_frame.rowconfigure(1, weight=1)
        main.add(table_frame, weight=4)
        row_tools = ttk.Frame(table_frame, padding=(0, 0, 0, 8))
        row_tools.grid(row=0, column=0, columnspan=2, sticky="ew")
        self.add_button = ttk.Button(row_tools, text="+ Add task", command=self.add_row,
                                     bootstyle="primary-outline")
        self.add_button.pack(side=LEFT)
        self.edit_button = ttk.Button(row_tools, text="Edit task", command=self.open_selected_row_editor,
                                      bootstyle="secondary-outline")
        self.edit_button.pack(side=LEFT, padx=6)
        self.delete_button = ttk.Button(row_tools, text="Delete", command=self.delete_selected,
                                        bootstyle="danger-outline")
        self.delete_button.pack(side=LEFT)
        self.undo_button = ttk.Button(row_tools, text="Undo", command=self.undo, bootstyle="secondary-outline")
        self.undo_button.pack(side=LEFT, padx=6)
        self.selection_group = ttk.Labelframe(
            row_tools,
            text="Row selection",
            padding=(8, 4),
            bootstyle="secondary",
        )
        self.selection_group.pack(side=RIGHT)
        self.select_visible_button = ttk.Button(
            self.selection_group,
            text="Select visible",
            command=self.select_all_rows,
            bootstyle="secondary-outline",
        )
        self.select_visible_button.pack()

        self.tree = ttk.Treeview(table_frame, columns=DISPLAY_COLUMNS, show="headings",
                                 selectmode="extended", bootstyle="primary")
        self.tree.grid(row=1, column=0, sticky="nsew")
        self.tree.bind("<<TreeviewSelect>>", lambda _event: self.update_selected_count())
        self.tree.bind("<ButtonPress-1>", self._begin_drag_select, add="+")
        self.tree.bind("<B1-Motion>", self._drag_select_rows)
        self.tree.bind("<ButtonRelease-1>", self._end_drag_select, add="+")
        self.tree.bind("<Double-1>", self.open_selected_row_editor)
        self.tree.bind("<Return>", self.open_selected_row_editor)
        self.tree.bind("<Delete>", lambda _event: self.delete_selected())
        self.tree.bind("<Control-a>", lambda _event: (self.select_all_rows(), "break")[-1])
        self.tree.bind("<Escape>", lambda _event: self.clear_selection())
        self.tree.tag_configure("even", background="#f1f5f9")
        self.tree.tag_configure("review", foreground="#854500")
        yscroll = ttk.Scrollbar(table_frame, orient="vertical", command=self.tree.yview)
        yscroll.grid(row=1, column=1, sticky="ns")
        xscroll = ttk.Scrollbar(table_frame, orient="horizontal", command=self.tree.xview)
        xscroll.grid(row=2, column=0, sticky="ew")
        self.tree.configure(yscrollcommand=yscroll.set, xscrollcommand=xscroll.set)
        self._configure_columns()

        self.empty_state = ttk.Frame(table_frame, padding=24)
        self.empty_title = ttk.Label(self.empty_state, text="Build tasks from your project",
                                     font=("Segoe UI", 16, "bold"))
        self.empty_title.pack(pady=(0, 8))
        self.empty_help = ttk.Label(self.empty_state, justify="center", wraplength=390,
                                    bootstyle="secondary")
        self.empty_help.pack()
        self.empty_button = ttk.Button(self.empty_state, text="Open project…", command=self.load_project_file)
        self.empty_button.pack(pady=(16, 0))
        self.empty_state.place(in_=self.tree, relx=.5, rely=.5, anchor="center")

        detail = ttk.Frame(table_frame, padding=(8, 10))
        detail.grid(row=3, column=0, columnspan=2, sticky="ew")
        detail.columnconfigure(0, weight=1)
        self.detail_label = ttk.Label(detail, textvariable=self.detail_text, wraplength=740,
                                      justify="left", bootstyle="secondary")
        self.detail_label.grid(row=0, column=0, sticky="ew")
        detail.bind("<Configure>", lambda event: self.detail_label.configure(wraplength=max(240, event.width - 20)))

        sidebar = ttk.Frame(main, padding=(16, 0, 0, 0), width=290)
        main.add(sidebar, weight=1)
        self._build_sidebar(sidebar)
        main.bind("<Configure>", self._layout_panes)
        main.bind("<ButtonRelease-1>", self._remember_pane_width)

        footer = ttk.Frame(self, padding=(20, 10, 20, 14))
        footer.grid(row=4, column=0, sticky="ew")
        footer.columnconfigure(0, weight=1)
        self.progress = ttk.Progressbar(footer, mode="indeterminate", bootstyle="primary")
        self.progress.grid(row=0, column=0, columnspan=5, sticky="ew", pady=(0, 6))
        self.progress.grid_remove()
        self.status_label = ttk.Label(footer, textvariable=self.status_text, wraplength=540)
        self.status_label.grid(row=1, column=0, sticky="w", padx=(0, 12))
        ttk.Label(footer, text="Export").grid(row=1, column=1, padx=(0, 8))
        self.scope_combo = ttk.Combobox(footer, textvariable=self.export_scope,
                                        values=["All tasks", "Selected tasks"], state="readonly", width=16)
        self.scope_combo.grid(row=1, column=2, padx=(0, 8))
        self.scope_combo.bind("<<ComboboxSelected>>", lambda _event: self.update_selected_count())
        self.export_button = ttk.Button(footer, text="Export CSV…", command=self.export_selected_csv,
                                        bootstyle="success")
        self.export_button.grid(row=1, column=3)
        self.asana_upload_button = ttk.Button(
            footer,
            text="Upload to Asana…",
            command=self.upload_to_asana,
            bootstyle="info",
        )
        self.asana_upload_button.grid(row=1, column=4, padx=(8, 0))

    def _configure_columns(self) -> None:
        widths = {"Name": 300, "Assignee": 230, "Description": 320, "Estimated Time": 115}
        for column in DISPLAY_COLUMNS:
            self.tree.heading(column, text=column, command=lambda c=column: self.sort_by(c))
            self.tree.column(column, width=widths.get(column, 120), minwidth=80, stretch=False,
                             anchor="e" if column == "Estimated Time" else "w")
        self._set_column_view()

    def _layout_panes(self, event) -> None:
        # Treeview's large requested width must not squeeze the batch editor.
        self.main_panes.sashpos(0, max(360, event.width - self._sidebar_width))

    def _remember_pane_width(self, _event) -> None:
        width = self.main_panes.winfo_width()
        self._sidebar_width = min(440, max(280, width - self.main_panes.sashpos(0)))
        self.main_panes.sashpos(0, max(360, width - self._sidebar_width))

    def _set_column_view(self) -> None:
        self.tree.configure(displaycolumns=self.OVERVIEW_COLUMNS if self.column_view.get() == "Overview" else DISPLAY_COLUMNS)

    def _plain_left_drag(self, event) -> bool:
        # Tk state masks: Shift=0x0001, Control=0x0004. Leave those to Treeview.
        return not (event.state & 0x0005)

    def _begin_drag_select(self, event) -> None:
        if self._busy or not self._plain_left_drag(event):
            self._drag_anchor_iid = ""
            return
        if self.tree.identify_region(event.x, event.y) not in {"cell", "tree"}:
            self._drag_anchor_iid = ""
            return
        self._drag_anchor_iid = self.tree.identify_row(event.y)
        self._drag_selecting = False

    def _drag_select_rows(self, event):
        if not self._drag_anchor_iid or self._busy:
            return None
        target_iid = self._drag_target_iid(event)
        if not target_iid:
            return "break"
        self._drag_selecting = True
        self._select_visible_range(self._drag_anchor_iid, target_iid)
        return "break"

    def _drag_target_iid(self, event) -> str:
        if event.y < 0:
            self.tree.yview_scroll(-1, "units")
            return self.tree.identify_row(0)
        height = self.tree.winfo_height()
        if event.y >= height:
            self.tree.yview_scroll(1, "units")
            return self.tree.identify_row(height - 1)
        return self.tree.identify_row(event.y)

    def _select_visible_range(self, start_iid: str, end_iid: str) -> None:
        children = list(self.tree.get_children())
        if start_iid not in children or end_iid not in children:
            return
        start_index = children.index(start_iid)
        end_index = children.index(end_iid)
        if start_index > end_index:
            start_index, end_index = end_index, start_index
        self.tree.selection_set(children[start_index:end_index + 1])
        self.tree.focus(end_iid)
        self.update_selected_count()

    def _end_drag_select(self, _event) -> None:
        if self._drag_selecting:
            self.status_text.set(f"Selected {len(self.tree.selection())} visible task(s).")
        self._drag_anchor_iid = ""
        self._drag_selecting = False

    def _build_sidebar(self, parent) -> None:
        parent.columnconfigure(0, weight=1)
        parent.rowconfigure(2, weight=1)
        ttk.Label(parent, text="Batch edit", font=("Segoe UI", 14, "bold")).grid(row=0, column=0, sticky="w")
        ttk.Label(parent, textvariable=self.selected_count_text, bootstyle="secondary").grid(
            row=1, column=0, sticky="w", pady=(3, 12))
        scroll_area = ttk.Frame(parent)
        scroll_area.grid(row=2, column=0, sticky="nsew")
        scroll_area.rowconfigure(0, weight=1)
        scroll_area.columnconfigure(0, weight=1)
        canvas = tk.Canvas(scroll_area, highlightthickness=0, background=self.style.colors.bg,
                           width=260, height=150)
        canvas.grid(row=0, column=0, sticky="nsew")
        scrollbar = ttk.Scrollbar(scroll_area, command=canvas.yview)
        scrollbar.grid(row=0, column=1, sticky="ns")
        canvas.configure(yscrollcommand=scrollbar.set)
        form = ttk.Frame(canvas, padding=(0, 0, 8, 0))
        form.columnconfigure(0, weight=1)
        window_id = canvas.create_window(0, 0, window=form, anchor="nw")
        form.bind("<Configure>", lambda _event: canvas.configure(scrollregion=canvas.bbox("all")))
        canvas.bind("<Configure>", lambda event: canvas.itemconfigure(window_id, width=event.width))
        canvas.bind("<MouseWheel>", lambda event: canvas.yview_scroll(-int(event.delta / 120), "units"))
        ttk.Label(form, text="Apply to").grid(row=0, column=0, sticky="w")
        self.bulk_scope_combo = ttk.Combobox(
            form,
            textvariable=self.bulk_scope,
            values=BULK_SCOPES,
            state="readonly",
        )
        self.bulk_scope_combo.grid(row=1, column=0, sticky="ew", pady=(4, 10))
        self.bulk_scope_combo.bind("<<ComboboxSelected>>", lambda _event: self.update_selected_count())
        ttk.Label(form, text="Field").grid(row=2, column=0, sticky="w")
        combo = ttk.Combobox(form, textvariable=self.bulk_field, values=EDITABLE_FIELDS, state="readonly")
        combo.grid(row=3, column=0, sticky="ew", pady=(4, 10))
        combo.bind("<<ComboboxSelected>>", lambda _event: self.refresh_bulk_value_widget())
        self.mode_combo = ttk.Combobox(form, textvariable=self.bulk_mode,
                                        values=["Replace value", "Add values", "Remove values"],
                                        state="readonly")
        self.mode_combo.grid(row=4, column=0, sticky="ew", pady=(0, 8))
        self.bulk_value_container = ttk.Frame(form)
        self.bulk_value_container.grid(row=5, column=0, sticky="ew")
        self.bulk_value_container.columnconfigure(0, weight=1)
        self.refresh_bulk_value_widget()
        help_label = ttk.Label(form, textvariable=self.bulk_help_text, wraplength=240, bootstyle="secondary")
        help_label.grid(row=6, column=0, sticky="w", pady=(8, 12))
        form.bind("<Configure>", lambda event: help_label.configure(wraplength=max(140, event.width - 12)), add="+")
        actions = ttk.Frame(parent, padding=(0, 10, 0, 0))
        actions.grid(row=3, column=0, sticky="ew")
        actions.columnconfigure(0, weight=1)
        self.apply_button = ttk.Button(actions, text="Apply batch edit", command=self.apply_bulk_edit)
        self.apply_button.grid(row=0, column=0, sticky="ew")
        self.clear_field_button = ttk.Button(actions, text="Clear field", command=self.clear_bulk_field,
                                             bootstyle="secondary-link")
        self.clear_field_button.grid(row=1, column=0, sticky="ew", pady=(4, 0))
        ttk.Button(actions, text="Clear selection", command=self.clear_selection,
                   bootstyle="secondary-outline").grid(row=2, column=0, sticky="ew", pady=(6, 0))

    def refresh_bulk_value_widget(self) -> None:
        for child in self.bulk_value_container.winfo_children():
            child.destroy()
        field_name = self.bulk_field.get()
        self.bulk_value_widget = TaskField(
            self.bulk_value_container,
            field_name,
            self.options,
            "",
            compact=True,
            multi_value_fields=MULTI_VALUE_FIELDS,
        )
        self.bulk_value_widget.grid(row=0, column=0, sticky="ew")
        self.bulk_help_text.set(FIELD_HELP.get(field_name, ""))
        self.bulk_mode.set("Replace value")
        if field_name in MULTI_VALUE_FIELDS:
            self.mode_combo.grid()
        else:
            self.mode_combo.grid_remove()

    def get_bulk_value(self) -> str:
        return self.bulk_value_widget.get()

    def _schedule_search(self, *_args) -> None:
        if self._search_after is not None:
            self.after_cancel(self._search_after)
        self._search_after = self.after(180, self._run_search)

    def _run_search(self) -> None:
        self._search_after = None
        self.refresh_table()

    def clear_filters(self) -> None:
        self.search_text.set("")
        self.review_only.set(False)
        self.refresh_table()

    def sort_by(self, column: str) -> None:
        self._sort_reverse = not self._sort_reverse if self._sort_column == column else False
        self._sort_column = column
        self.refresh_table()

    def refresh_table(self) -> None:
        selected_ids = set(self.tree.selection())
        focused_id = self.tree.focus()
        scroll_y = self.tree.yview()[0]
        self._issues = {row.row_id: review_notes(row.values, self.options) for row in self.model.rows}
        query = self.search_text.get().strip().casefold()
        rows = [row for row in self.model.rows
                if (not query or any(query in row.get(column).casefold() for column in DISPLAY_COLUMNS))
                and (not self.review_only.get() or self._issues[row.row_id])]
        if self._sort_column:
            rows.sort(key=lambda row: table_sort_key(self._sort_column, row.get(self._sort_column)),
                      reverse=self._sort_reverse)
        existing = self.tree.get_children()
        if existing:
            self.tree.delete(*existing)
        for index, row in enumerate(rows):
            tags = (["even"] if index % 2 == 0 else []) + (["review"] if self._issues[row.row_id] else [])
            self.tree.insert("", END, iid=str(row.row_id), values=[row.get(column) for column in DISPLAY_COLUMNS],
                             tags=tags)
        remaining = [str(row.row_id) for row in rows if str(row.row_id) in selected_ids]
        self.tree.selection_set(remaining)
        if focused_id in self.tree.get_children():
            self.tree.focus(focused_id)
        self.tree.yview_moveto(scroll_y)
        for column in DISPLAY_COLUMNS:
            suffix = (" ▼" if self._sort_reverse else " ▲") if column == self._sort_column else ""
            self.tree.heading(column, text=column + suffix)
        count = len(self.model.rows)
        total = sum(finite_number(row.get("Estimated Time")) or 0 for row in self.model.rows)
        review_count = sum(bool(notes) for notes in self._issues.values())
        self.summary_text.set(f"{count} tasks  ·  {total:g} estimated hours  ·  {len(rows)} visible  ·  {review_count} need review")
        if self.current_draft_path:
            project = f"Draft: {self.current_draft_path.name}"
        else:
            project = self.current_project_path.name if self.current_project_path else "Manual task list" if count else "No project loaded"
        self.source_text.set(project + ("  •  Not fully exported" if self.dirty else ""))
        if rows:
            self.empty_state.place_forget()
        else:
            self.empty_title.configure(text="No matching tasks" if count else "Build tasks from your project")
            self.empty_help.configure(text="Try another search or reset your filters." if count else
                                      "Choose one project file to find its related qBOMs and generate tasks. You can also add tasks manually.")
            self.empty_button.configure(text="Reset filters" if count else "Open project…",
                                         command=self.clear_filters if count else self.load_project_file)
            self.empty_state.place(in_=self.tree, relx=.5, rely=.5, anchor="center")
        self.update_selected_count()

    def update_selected_count(self) -> None:
        selected = self.selected_rows()
        count = len(selected)
        hours = sum(finite_number(row.get("Estimated Time")) or 0 for row in selected)
        batch_rows = self.rows_for_bulk_edit()
        self.selected_count_text.set(
            f"{count} selected  ·  {hours:g} hours  ·  {len(batch_rows)} in batch scope"
        )
        if count == 1:
            row = selected[0]
            notes = self._issues.get(row.row_id, [])
            self.detail_text.set(f"{row.get('Name') or 'Unnamed task'}\n" + (
                "Review: " + "  •  ".join(notes) if notes else
                f"Labels: {row.get('Labels') or '—'}  ·  Estimate: {row.get('Estimated Time') or '—'} hours"))
        elif count > 1:
            self.detail_text.set(f"{count} tasks selected. Batch edits apply to this selection; Undo restores the previous values.")
        else:
            self.detail_text.set("Select a task to see its full name and review notes. Amber text marks tasks that need review.")
        batch_count = len(batch_rows)
        scope_text = {
            "Selected rows": "selected",
            "Visible rows": "visible",
            "All tasks": "all",
        }.get(self.bulk_scope.get(), "selected")
        self.apply_button.configure(text=f"Apply to {batch_count} {scope_text}")
        self.clear_field_button.configure(text=f"Clear field for {batch_count} {scope_text}")
        for button, enabled in [
            (self.edit_button, count == 1), (self.delete_button, count > 0),
            (self.apply_button, batch_count > 0), (self.clear_field_button, batch_count > 0),
            (self.undo_button, bool(self.history)), (self.add_button, True),
            (self.load_button, True), (self.open_draft_button, True),
            (self.save_draft_button, bool(self.model.rows)),
            (self.options_button, True), (self.empty_button, True),
            (self.schedule_button, bool(self.model.rows)),
        ]:
            button.configure(state=NORMAL if enabled and not self._busy else DISABLED)
        export_count = count if self.export_scope.get() == "Selected tasks" else len(self.model.rows)
        self.export_button.configure(text=f"Export CSV ({export_count})…",
                                     state=NORMAL if export_count and not self._busy else DISABLED)
        self.asana_upload_button.configure(
            text=f"Upload to Asana ({export_count})…",
            state=NORMAL if export_count and not self._busy else DISABLED,
        )

    def selected_rows(self) -> list[TaskRow]:
        return self.model.selected_rows(self.tree.selection())

    def visible_rows(self) -> list[TaskRow]:
        return self.model.selected_rows(tuple(self.tree.get_children()))

    def rows_for_bulk_edit(self) -> list[TaskRow]:
        scope = self.bulk_scope.get()
        if scope == "All tasks":
            return list(self.model.rows)
        if scope == "Visible rows":
            return self.visible_rows()
        return self.selected_rows()

    def _schedule_from_ui_event(self, _event=None) -> None:
        if not self._scheduling and not self._busy:
            self.recalculate_schedule(show_error=False)

    def _set_start_date(self, value: object) -> bool:
        parsed = parse_schedule_date(value)
        if parsed is None:
            return False
        effective_start = roll_forward_to_workday(parsed)
        formatted = effective_start.strftime("%m/%d/%Y")
        self.start_date_text.set(formatted)
        self.start_date_entry.entry.delete(0, "end")
        self.start_date_entry.entry.insert(0, formatted)
        return True

    def current_schedule_state(self) -> dict[str, object]:
        start_date = parse_schedule_date(self.start_date_entry.entry.get())
        if start_date is not None:
            start_date = roll_forward_to_workday(start_date)
        target_date = self.target_date_text.get().strip()
        return {
            "start_date": start_date.strftime("%m/%d/%Y") if start_date else "",
            "target_date": "" if target_date == "—" else target_date,
            "hours_per_workday": WORKDAY_CAPACITY_HOURS,
            "working_days": ["Monday", "Tuesday", "Wednesday", "Thursday", "Friday"],
            "grouping": "qBOM",
            "zero_hour_fallback": "pre-rounding decimal hours converted to ceiling integer minutes",
        }

    def recalculate_schedule(self, show_error: bool = True, refresh: bool = True) -> bool:
        if self._scheduling:
            return False
        requested_start = parse_schedule_date(self.start_date_entry.entry.get())
        if requested_start is None:
            if show_error:
                messagebox.showerror(
                    "Check Start Date",
                    "Enter a valid Start Date, such as 09/28/2026.",
                    parent=self,
                )
            self.status_text.set("Start Date is invalid; the existing schedule was not changed.")
            return False

        self._scheduling = True
        try:
            effective_start = roll_forward_to_workday(requested_start)
            self._set_start_date(effective_start)
            due_dates, target_date, lane_totals = calculate_qbom_schedule(
                self.model.rows,
                effective_start,
            )
            for row_id, due_date in due_dates.items():
                row = self.model.by_id(row_id)
                if row is not None:
                    row.set("Due Date", due_date)
            self.target_date_text.set(
                target_date.strftime("%m/%d/%Y") if target_date is not None else "—"
            )
            if refresh:
                self.refresh_table()
            if lane_totals:
                self.status_text.set(
                    f"Scheduled {len(lane_totals)} qBOM lane(s) from "
                    f"{effective_start.strftime('%m/%d/%Y')} using 6-hour Monday–Friday workdays."
                )
            else:
                self.status_text.set("No generated qBOM rows are available to schedule.")
            return True
        finally:
            self._scheduling = False

    def checkpoint(self, label: str) -> None:
        self.history.append((
            label,
            copy.deepcopy(self.model),
            copy.deepcopy(self.options),
            self.current_project_path,
            self.current_draft_path,
            copy.deepcopy(self.source_trace),
            self.start_date_entry.entry.get(),
            self.target_date_text.get(),
        ))
        self.history = self.history[-30:]

    def undo(self) -> None:
        if not self.history or self._busy:
            return
        (
            label,
            self.model,
            self.options,
            self.current_project_path,
            self.current_draft_path,
            self.source_trace,
            start_date,
            target_date,
        ) = self.history.pop()
        self._set_start_date(start_date)
        self.target_date_text.set(target_date)
        self.refresh_bulk_value_widget()
        self.refresh_table()
        if "option" in label:
            self._save_options_to_disk(show_error=False)
        self.status_text.set(f"Undid {label}.")

    def add_row(self) -> None:
        if self._busy:
            return
        def save(values):
            self.checkpoint("add task")
            row = self.model.add(values)
            self.clear_filters()
            self.tree.selection_set(str(row.row_id))
            self.tree.see(str(row.row_id))
            self.status_text.set("Task added. Ctrl+Z to undo.")
        RowEditorDialog(
            self,
            DEFAULT_ROW_VALUES.copy(),
            self.options,
            save,
            lambda values: field_errors(values, self.options),
            FIELD_HELP,
            title="Add task",
            multi_value_fields=MULTI_VALUE_FIELDS,
        )

    def delete_selected(self) -> None:
        selected = self.selected_rows()
        if not selected or self._busy:
            return
        if not messagebox.askyesno("Delete selected tasks",
                                   f"Delete {len(selected)} selected task(s)? You can Undo this change.",
                                   parent=self):
            return
        self.checkpoint("delete tasks")
        self.model.remove({row.row_id for row in selected})
        self.recalculate_schedule(show_error=False)
        self.status_text.set(f"Deleted {len(selected)} task(s). Ctrl+Z to undo.")

    def select_all_rows(self) -> None:
        self.tree.selection_set(self.tree.get_children())
        self.update_selected_count()

    def clear_selection(self) -> None:
        self.tree.selection_remove(self.tree.selection())
        self.update_selected_count()

    def apply_bulk_edit(self) -> None:
        rows = self.rows_for_bulk_edit()
        if not rows or self._busy:
            return
        name = self.bulk_field.get()
        value = self.get_bulk_value()
        if not value:
            self.status_text.set("Enter a value to apply, or use Clear this field.")
            self.bulk_value_widget.focus_input()
            return
        errors = field_errors({name: value}, self.options)
        if errors:
            messagebox.showerror("Check batch value", "\n".join(errors), parent=self)
            return
        self.checkpoint(f"batch edit {name}")
        for row in rows:
            row.set(name, merge_values(row.get(name), value, self.bulk_mode.get())
                    if name in MULTI_VALUE_FIELDS else value)
        if name == "Estimated Time":
            self.recalculate_schedule(show_error=False)
        else:
            self.refresh_table()
        self.status_text.set(f"Updated {name} for {len(rows)} task(s). Ctrl+Z to undo.")

    def clear_bulk_field(self) -> None:
        rows = self.rows_for_bulk_edit()
        name = self.bulk_field.get()
        if not rows or self._busy:
            return
        if name == "Name":
            self.status_text.set("Name is required. Enter a replacement name instead.")
            return
        if self.bulk_scope.get() == "All tasks" and not messagebox.askyesno(
            "Clear field for all tasks",
            f"Clear {name} for all {len(rows)} tasks? You can Undo this change.",
            parent=self,
        ):
            return
        self.checkpoint(f"clear {name}")
        for row in rows:
            row.set(name, "")
        if name == "Estimated Time":
            self.recalculate_schedule(show_error=False)
        else:
            self.refresh_table()
        self.status_text.set(f"Cleared {name} for {len(rows)} task(s). Ctrl+Z to undo.")

    def open_selected_row_editor(self, event=None) -> None:
        if self._busy:
            return
        if event is not None and getattr(event, "num", None) == 1:
            if self.tree.identify_region(event.x, event.y) not in {"cell", "tree"}:
                return
            item = self.tree.identify_row(event.y)
            if item:
                self.tree.selection_set(item)
        selected = self.selected_rows()
        if len(selected) != 1:
            return
        row = selected[0]
        def save(values):
            original_values = {name: row.get(name) for name in EDITABLE_FIELDS}
            if values != original_values:
                self.checkpoint("edit task")
                estimate_changed = values.get("Estimated Time", "") != row.get("Estimated Time")
                for name, value in values.items():
                    row.set(name, value)
                if estimate_changed:
                    self.recalculate_schedule(show_error=False)
                else:
                    self.refresh_table()
                self.status_text.set("Task saved. Ctrl+Z to undo.")
        RowEditorDialog(
            self,
            row.values.copy(),
            self.options,
            save,
            lambda values: field_errors(values, self.options),
            FIELD_HELP,
            multi_value_fields=MULTI_VALUE_FIELDS,
        )

    def open_option_manager(self) -> None:
        if not self._busy:
            OptionManagerDialog(
                self,
                self.options,
                self.on_options_changed,
                assignee_lookup=self._lookup_assignee_option,
            )

    def _lookup_assignee_option(self, email: str):
        settings = load_upload_settings(APP_DIR)
        user = lookup_workspace_user_by_email(email, env_path=APP_DIR / ".env")
        # A targeted email check only needs the token and workspace in .env.
        # Discovery metadata is required for task upload, but it must not block
        # adding a verified Assignee option in a freshly packaged installation.
        if settings.discovery_path.is_file():
            discovery = load_discovery(settings.discovery_path)
            workspace = discovery.get("workspace")
            discovered_workspace = (
                str(workspace.get("gid", "")) if isinstance(workspace, dict) else ""
            )
            if settings.workspace_gid and discovered_workspace != settings.workspace_gid:
                raise UploadPreviewError(
                    "The cached discovery workspace does not match ASANA_WORKSPACE_GID."
                )
            cache_workspace_user(settings.discovery_path, user)
        return user

    def on_options_changed(self) -> None:
        self.refresh_bulk_value_widget()
        self.refresh_table()
        if self._save_options_to_disk():
            self.status_text.set(f"Options saved to {OPTIONS_PATH}. Ctrl+Z to undo.")
        else:
            self.status_text.set("Options updated for this session, but could not be saved.")

    def _save_options_to_disk(self, show_error: bool = True) -> bool:
        try:
            save_options(self.options)
        except OSError as error:
            if show_error:
                messagebox.showerror(
                    "Could not save options",
                    f"{error}\n\nCheck write access to {OPTIONS_PATH.parent}.",
                    parent=self,
                )
            return False
        return True

    def save_draft_file(self) -> None:
        if self._busy or not self.model.rows:
            return
        initial_stem = safe_filename_stem(
            self.current_project_path.stem if self.current_project_path else "asana_tasks"
        )
        initial_dir = (
            self.current_draft_path.parent
            if self.current_draft_path
            else self.current_project_path.parent
            if self.current_project_path
            else APP_DIR
        )
        filename = filedialog.asksaveasfilename(
            parent=self,
            title="Save task draft",
            initialdir=str(initial_dir),
            initialfile=f"{initial_stem}.asana-draft.json",
            defaultextension=".asana-draft.json",
            filetypes=[("Asana task drafts", "*.asana-draft.json"), ("JSON files", "*.json")],
        )
        if not filename:
            return
        path = Path(filename)
        document = build_draft_document(
            self.model.to_draft_records(),
            self.options,
            self.source_trace,
            schedule=self.current_schedule_state(),
            history_actions=[entry[0] for entry in self.history],
        )
        try:
            write_json_document(path, document)
        except OSError as error:
            messagebox.showerror(
                "Could not save draft",
                f"{error}\n\nCheck write access to {path.parent}.",
                parent=self,
            )
            return
        self.current_draft_path = path
        self.refresh_table()
        self.status_text.set(f"Saved {len(self.model.rows)} tasks to draft {path}.")

    def open_draft_file(self) -> None:
        if self._busy:
            return
        filename = filedialog.askopenfilename(
            parent=self,
            title="Open task draft",
            filetypes=[("Asana task drafts", "*.asana-draft.json"), ("JSON files", "*.json")],
        )
        if not filename:
            return
        if self.dirty and not messagebox.askyesno(
            "Replace current tasks?",
            "Replace the current task list with this saved draft? You can Undo the change.",
            parent=self,
        ):
            return
        path = Path(filename)
        try:
            tasks, options, source_trace, schedule = load_draft_document(path)
        except (OSError, DraftFormatError) as error:
            messagebox.showerror("Could not open draft", str(error), parent=self)
            return
        self.checkpoint("open draft")
        self.model.clear()
        for values in tasks:
            self.model.add(values)
        self.options = options
        self.source_trace = source_trace
        source_path = str(source_trace.get("path", "")).strip()
        self.current_project_path = Path(source_path) if source_path else None
        self.current_draft_path = path
        self._exported_records = []
        saved_start = schedule.get("start_date", "")
        if saved_start:
            self._set_start_date(saved_start)
        has_schedule_groups = any(row.get(SCHEDULE_GROUP_COLUMN).strip() for row in self.model.rows)
        if has_schedule_groups:
            self.recalculate_schedule(show_error=False, refresh=False)
        else:
            saved_target = str(schedule.get("target_date", "") or "").strip()
            self.target_date_text.set(saved_target or "—")
        self.tree.selection_remove(self.tree.selection())
        self.refresh_bulk_value_widget()
        self.clear_filters()
        self.status_text.set(f"Opened draft {path.name} with {len(tasks)} tasks.")

    def load_project_file(self) -> None:
        if self._busy:
            return
        filename = filedialog.askopenfilename(
            parent=self, title="Open a saved project",
            filetypes=[("Project files", "*.csv *.xlsx *.xlsm"), ("CSV files", "*.csv"),
                       ("Excel files", "*.xlsx *.xlsm"), ("All files", "*.*")])
        if not filename:
            return
        if self.dirty and not messagebox.askyesno(
                "Replace current tasks?",
                "Some tasks have not been exported. Replace the current list with this project? "
                "You can Undo a successful load to recover this list.", parent=self):
            return
        self._start_project_load(Path(filename))

    def _start_project_load(self, path: Path) -> None:
        if self._busy:
            return
        self._busy = True
        self.status_text.set(f"Reading {path.name} and related qBOMs…")
        self.progress.grid()
        self.progress.start(12)
        self.update_selected_count()

        def worker():
            # No Tk calls in the worker; results are committed on the UI thread.
            try:
                result = generate_rows_from_project(path)
                self._load_queue.put((path, result, None))
            except Exception as error:
                self._load_queue.put((path, None, error))

        threading.Thread(target=worker, daemon=True, name="project-loader").start()
        self.after(80, self._poll_project_load)

    def _poll_project_load(self) -> None:
        try:
            path, rows, error = self._load_queue.get_nowait()
        except queue.Empty:
            self.after(80, self._poll_project_load)
            return
        self._busy = False
        self.progress.stop()
        self.progress.grid_remove()
        if error is not None:
            self.status_text.set("Project could not be loaded. Your current tasks are still available.")
            self.update_selected_count()
            messagebox.showerror("Could not load project",
                                 f"{path.name}\n\n{error}\n\nCheck the project format and related qBOM paths.",
                                 parent=self)
            return
        self.checkpoint("load project")
        self.model.clear()
        for values in rows:
            self.model.add(values)
        self.current_project_path = path
        self.current_draft_path = None
        self.source_trace = source_trace_for_project(path)
        self.recalculate_schedule(show_error=False, refresh=False)
        self.tree.selection_remove(self.tree.selection())
        self.clear_filters()
        target = self.target_date_text.get()
        target_note = f" Project target: {target}." if target != "—" else ""
        self.status_text.set(
            f"Generated {len(rows)} tasks and scheduled each qBOM independently.{target_note} "
            "Review, assign, then export or upload."
        )

    def rows_for_export(self) -> list[TaskRow]:
        return self.selected_rows() if self.export_scope.get() == "Selected tasks" else self.model.rows

    def show_help(self) -> None:
        messagebox.showinfo(
            "Task builder help",
            "Open a saved project to generate tasks from its related qBOMs.\n\n"
            "Search covers every field. Choose All fields to show every CSV column. "
            "Click column headings to sort the view.\n\n"
            "Set Start Date in Project schedule. Each qBOM starts on that date and runs as an independent lane. "
            "Tasks within a qBOM are sequential and share six working hours per Monday–Friday day. "
            "Due Date is each task's calculated completion date; Target Date is the latest qBOM completion date "
            "and is shown in the app only. A weekend Start Date moves forward to Monday.\n\n"
            "Drag through rows, or use Ctrl / Shift + click, to select multiple tasks. Select visible selects only the filtered list. "
            "Double-click or Enter edits one task. Batch scope can target selected rows, visible rows, or all tasks. "
            "Clearing a field from all tasks asks for confirmation. Batch edits can be undone (last 30 actions).\n\n"
            "Export All tasks includes tasks hidden by filters. Selected tasks exports only the selection. "
            "Sorting changes the view, not the generator's full-export order. CSV files are saved automatically "
            "in the ASANA-UPLOADS folder with a JSON traceability manifest.\n\n"
            "Upload to Asana runs a local preflight, then asks for confirmation before creating anything. "
            "Uploads run sequentially in the background. Created task GIDs are journaled locally to prevent "
            "duplicate retries, and a JSON result report is saved in ASANA-UPLOADS.\n\n"
            "Save draft stores the full task list, qBOM schedule, options, source trace and recent action names in a shareable JSON file. "
            "Open draft restores that work. Product stays visible as generated reference data, but is "
            "not exported or uploaded because it must be set manually in Asana.\n\n"
            "Needs review identifies missing or invalid fields and estimates to verify. Zero-hour and "
            "manually adjusted estimates are highlighted but never recalculated by the editor.\n\n"
            "Shortcuts: Ctrl+O Generate • Ctrl+Shift+S Save draft • Ctrl+N Add • Ctrl+F Search • Ctrl+S Export\n"
            "In the table: Ctrl+A Select visible • Ctrl+Z Undo • Delete • Esc Clear selection\n"
            "In the task editor: Ctrl+Enter Save • Esc Cancel\n\n"
            "Dropdown options are saved next to the app. New or renamed Assignee emails are checked individually "
            "in the configured Asana workspace and are added only when Asana returns a matching user. "
            "Save a draft when you want to continue or share the task list later.",
            parent=self)

    def upload_to_asana(self) -> None:
        """Preflight, confirm, then create the selected task scope in Asana."""
        if self._busy:
            return
        if any(row.get(SCHEDULE_GROUP_COLUMN).strip() for row in self.model.rows):
            if not self.recalculate_schedule(show_error=True):
                return
        rows = self.rows_for_export()
        if not rows:
            self.status_text.set("Select tasks, or change the export scope to All tasks.")
            return
        selected_only = self.export_scope.get() == "Selected tasks"
        preflight_path = automatic_upload_preview_path(
            self.current_project_path,
            selected_only=selected_only,
        )
        try:
            settings = load_upload_settings(APP_DIR)
            discovery = load_discovery(settings.discovery_path)
            preview = build_upload_preview(
                rows,
                discovery,
                settings,
                source=self.source_trace,
            )
        except (OSError, UploadPreviewError, TypeError, ValueError) as error:
            messagebox.showerror(
                "Asana upload preflight failed",
                f"{error}\n\nNothing was created in Asana.",
                parent=self,
            )
            self.status_text.set("Upload preflight failed. Nothing was created in Asana.")
            return

        summary = preview["summary"]
        if not preview["ready_for_upload"]:
            try:
                write_upload_preview(preflight_path, preview)
            except OSError:
                pass
            details: list[str] = []
            details.extend(str(error) for error in preview["configuration_errors"][:4])
            for row_error in preview["row_errors"][:4]:
                details.append(
                    f"Row {row_error['row']} ({row_error['name'] or 'Unnamed'}): "
                    + "; ".join(row_error["errors"])
                )
            messagebox.showwarning(
                "Fix upload preflight",
                f"{summary['invalid_rows']} invalid row(s); "
                f"{summary['configuration_errors']} configuration error(s).\n\n"
                + "\n".join(details)
                + f"\n\nDetails: {preflight_path}\n\nNothing was created in Asana.",
                parent=self,
            )
            self.status_text.set("Upload preflight found issues. Nothing was created in Asana.")
            return

        destination = preview["destination"]
        project_name = destination.get("project_name") or destination.get("project_gid")
        section_note = (
            f"\nSection: {destination.get('section_name') or destination['section_gid']}"
            if destination.get("section_gid") else "\nSection: project default"
        )
        if not messagebox.askyesno(
            "Create tasks in Asana?",
            f"Create {summary['valid_requests']} task(s) in:\n{project_name}{section_note}\n\n"
            "This will modify Asana. A local journal prevents confirmed tasks from being created twice.",
            parent=self,
        ):
            self.status_text.set("Asana upload canceled. Nothing was created.")
            return

        report_path = automatic_upload_report_path(self.current_project_path, selected_only)
        self._busy = True
        self._uploading_all_rows = {row.row_id for row in rows} == {
            row.row_id for row in self.model.rows
        }
        self.progress.grid()
        self.progress.start(12)
        self.status_text.set(f"Uploading {len(rows)} task(s) to Asana…")
        self.update_selected_count()

        def progress(current: int, total: int, name: str) -> None:
            self._upload_queue.put(("progress", current, total, name))

        def worker() -> None:
            try:
                client = AsanaApiClient.from_env(APP_DIR / ".env")
                report = upload_preview(
                    preview,
                    client,
                    journal_path=UPLOAD_JOURNAL_PATH,
                    progress=progress,
                )
                write_upload_report(report_path, report)
                self._upload_queue.put(("done", report, report_path))
            except Exception as error:
                self._upload_queue.put(("error", error))

        threading.Thread(target=worker, daemon=True, name="asana-task-upload").start()
        self.after(80, self._poll_asana_upload)

    def _poll_asana_upload(self) -> None:
        try:
            event = self._upload_queue.get_nowait()
        except queue.Empty:
            self.after(80, self._poll_asana_upload)
            return
        if event[0] == "progress":
            _, current, total, name = event
            self.status_text.set(f"Uploading {current}/{total}: {name}")
            self.after(40, self._poll_asana_upload)
            return

        self._busy = False
        self.progress.stop()
        self.progress.grid_remove()
        if event[0] == "error":
            error = event[1]
            messagebox.showerror(
                "Asana upload stopped",
                f"{error}\n\nReview Asana and the local journal before retrying.",
                parent=self,
            )
            self.status_text.set("Asana upload stopped. Review the journal before retrying.")
            self.update_selected_count()
            return

        _, report, report_path = event
        counts = report.get("counts", {})
        created = counts.get("created", 0)
        repaired = counts.get("section_repaired", 0)
        skipped = counts.get("skipped_existing", 0)
        failed = counts.get("failed", 0)
        partial = counts.get("partial", 0)
        ambiguous = counts.get("ambiguous", 0)
        if not failed and not partial and not ambiguous and self._uploading_all_rows:
            self._exported_records = copy.deepcopy(self.model.to_export_records())
        self.refresh_table()
        message = (
            f"Created: {created}\nAlready journaled: {skipped}\n"
            f"Section repairs: {repaired}\nFailed: {failed}\nPartial: {partial}\n"
            f"Uncertain creation: {ambiguous}\n\n"
            f"Report: {report_path}"
        )
        if failed or partial or ambiguous:
            messagebox.showwarning("Asana upload completed with issues", message, parent=self)
        else:
            messagebox.showinfo("Asana upload complete", message, parent=self)
        self.status_text.set(
            f"Asana upload finished: {created} created, {skipped} already journaled, "
            f"{failed + partial + ambiguous} need attention."
        )

    def export_selected_csv(self) -> None:
        if self._busy:
            return
        if any(row.get(SCHEDULE_GROUP_COLUMN).strip() for row in self.model.rows):
            if not self.recalculate_schedule(show_error=True):
                return
        rows = self.rows_for_export()
        if not rows:
            self.status_text.set("Select tasks to export, or change the export scope to All tasks.")
            return
        errors = [(row, field_errors(row.values, self.options)) for row in rows]
        errors = [(row, notes) for row, notes in errors if notes]
        if errors:
            preview = "\n".join(f"{row.get('Name') or 'Unnamed task'}: {'; '.join(notes)}" for row, notes in errors[:5])
            messagebox.showerror("Fix fields before export",
                                 f"{len(errors)} task(s) contain missing names or invalid field values.\n\n{preview}"
                                 "\n\nUse Needs review to find these tasks.", parent=self)
            return
        output_path = automatic_export_path(
            self.current_project_path,
            selected_only=self.export_scope.get() == "Selected tasks",
        )
        records = self.model.to_export_records(rows)
        manifest_path = output_path.with_suffix(".manifest.json")
        try:
            output_path.parent.mkdir(parents=True, exist_ok=True)
            export_csv(output_path, records)
        except OSError as error:
            messagebox.showerror("Export failed",
                                 f"{error}\n\nClose the CSV if it is open or check access to {output_path.parent}.",
                                  parent=self)
            return
        manifest_written = False
        if output_path.is_file():
            try:
                write_json_document(
                    manifest_path,
                    build_export_manifest(
                        output_path,
                        records,
                        self.export_scope.get(),
                        self.source_trace,
                        self.current_draft_path,
                        self.current_schedule_state(),
                    ),
                )
                manifest_written = True
            except OSError as error:
                messagebox.showwarning(
                    "CSV exported without manifest",
                    f"The CSV was created, but its traceability manifest could not be written.\n\n{error}",
                    parent=self,
                )
        if {row.row_id for row in rows} == {row.row_id for row in self.model.rows}:
            self._exported_records = copy.deepcopy(self.model.to_export_records())
        self.refresh_table()
        manifest_note = f" and {manifest_path.name}" if manifest_written else ""
        self.status_text.set(f"Exported {len(rows)} tasks to {output_path}{manifest_note}")

    def request_close(self) -> None:
        if self._busy:
            messagebox.showwarning(
                "Operation in progress",
                "Wait for the current project load or Asana upload to finish before closing.",
                parent=self,
            )
            return
        if self.dirty:
            if self.current_draft_path:
                detail = (
                    f"Some tasks have not been exported. The last saved draft remains at:\n"
                    f"{self.current_draft_path}\n\nChanges made after the last draft save may be lost. Close anyway?"
                )
            else:
                detail = "Some tasks have not been exported or saved as a draft. Close and discard this session?"
            if not messagebox.askyesno("Close without exporting?", detail, parent=self):
                return
        if self._search_after is not None:
            self.after_cancel(self._search_after)
        self.destroy()


def main() -> None:
    app = AsanaTaskApp()
    app.mainloop()


if __name__ == "__main__":
    main()
