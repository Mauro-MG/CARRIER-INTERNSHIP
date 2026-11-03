"""Generate a Tasks file with estimated design hours for one project.

The project file must contain a ``QBomSaved`` column plus Primary, Secondary,
and Tertiary L1 quantities. Referenced qBOM files are located automatically in
the project's sibling ``Qboms`` folder or can be supplied with ``--qbom-dir``.
Excel project workbooks may also contain the qBOMs as embedded worksheets.
"""

from __future__ import annotations

import argparse
import math
import re
import sys
from dataclasses import dataclass
from decimal import Decimal, ROUND_FLOOR, ROUND_HALF_UP
from pathlib import Path
from typing import Iterable

import pandas as pd
from openpyxl.styles import Alignment, Font, PatternFill

from estimation_rules import (
    SECONDARY_L1_WEIGHT,
    TERTIARY_L1_WEIGHT,
    weighted_hour_components,
    weighted_quantity_multiplier,
)


PROJECT_COLUMNS = {
    "qbomsaved": "QBomSaved",
    "primaryl1sqty": "Primary L1s Qty",
    "secondaryl1sqty": "Secondary L1s Qty",
    "tertiaryl1sqty": "Tertiary L1s Qty",
    "summaryid": "SummaryID",
    "productfamily": "Product Family",
}

QBOM_COLUMNS = {
    "uniqueid": "UniqueID",
    "qbom": "qBOM",
    "productfamily": "Product Family",
    "set": "SET",
    "label": "Label",
    "modelinghrs": "Modeling Hrs",
    "modellinghrs": "Modeling Hrs",
    "detailinghrs": "Detailing Hrs",
    "detaillinghrs": "Detailing Hrs",
    "bomhrs": "BOM Hrs",
}

TASK_COLUMNS = [
    "Name",
    "Assignee",
    "Product",
    "Priority",
    "Due date",
    "Project",
    "Status",
    "Labels",
    "Estimated time",
    "ECN",
    "Task Type",
    "Description",
]
SCHEDULE_GROUP_COLUMN = "_QBom Group"
RAW_ESTIMATED_TIME_COLUMN = "_Raw Estimated Hours"
INTERNAL_TASK_COLUMNS = TASK_COLUMNS + [SCHEDULE_GROUP_COLUMN, RAW_ESTIMATED_TIME_COLUMN]

COMPONENT_COLUMNS = [
    "SummaryID",
    "QBomSaved",
    "Source",
    "Task",
    "Hour type",
    "PRT base hours",
    "ASSY base hours",
    "L1 base hours",
    "Combined base hours",
    "Primary L1s Qty",
    "Primary hours",
    "Secondary L1s Qty",
    "Secondary weight",
    "Secondary hours",
    "Tertiary L1s Qty",
    "Tertiary weight",
    "Tertiary hours",
    "Estimated time",
]

TASK_DEFINITIONS = [
    ("PRT", "PRT", "Modeling Hrs", "PRT"),
    ("ASSY", "ASSY", "Modeling Hrs", "ASSY"),
    ("L1 Modeling", "L1", "Modeling Hrs", "ASSY"),
    ("DRW PRT", "PRT", "Detailing Hrs", "DRW-S"),
    ("DRW ASSY", "ASSY", "Detailing Hrs", "ASSY-DRW"),
    ("L1 DRW", "L1", "Detailing Hrs", "L1-DRW"),
    ("L1 BOM", "L1", "BOM Hrs", "BOM"),
]

MAX_TASK_ESTIMATED_TIME = 40


class GenerationError(RuntimeError):
    """Raised when required project or qBOM data is missing or invalid."""


@dataclass(frozen=True)
class QbomSource:
    display_name: str
    data: pd.DataFrame


def normalized_header(value: object) -> str:
    return re.sub(r"[^a-z0-9]", "", str(value).strip().casefold())


def rename_known_columns(df: pd.DataFrame, aliases: dict[str, str]) -> pd.DataFrame:
    rename = {
        column: aliases[normalized_header(column)]
        for column in df.columns
        if normalized_header(column) in aliases
    }
    return df.rename(columns=rename)


def clean_text(value: object) -> str:
    if value is None or (isinstance(value, float) and math.isnan(value)):
        return ""
    return str(value).strip()


def round_estimated_time(value: float) -> int:
    return int(Decimal(str(value)).quantize(Decimal("1"), rounding=ROUND_HALF_UP))


def split_task_row(row: dict[str, object]) -> list[dict[str, object]]:
    estimated_time = round_estimated_time(float(row["Estimated time"]))
    row = dict(row)
    row["Estimated time"] = estimated_time

    if estimated_time <= MAX_TASK_ESTIMATED_TIME:
        return [row]

    split_rows = []
    remaining_time = estimated_time
    split_number = 1
    while remaining_time > 0:
        split_row = dict(row)
        split_row["Name"] = f"{row['Name']}_{split_number}"
        split_row["Estimated time"] = min(MAX_TASK_ESTIMATED_TIME, remaining_time)
        split_rows.append(split_row)
        remaining_time -= MAX_TASK_ESTIMATED_TIME
        split_number += 1
    return split_rows


def reconcile_and_split_task_rows(rows: list[dict[str, object]]) -> list[dict[str, object]]:
    """Allocate whole hours without changing the rounded total, then apply the 40-hour cap."""
    if not rows:
        return []
    raw_values = [Decimal(str(row["Estimated time"])) for row in rows]
    target_total = int(sum(raw_values, Decimal("0")).quantize(Decimal("1"), rounding=ROUND_HALF_UP))
    allocated = [int(value.to_integral_value(rounding=ROUND_FLOOR)) for value in raw_values]
    remaining = target_total - sum(allocated)
    order = sorted(
        range(len(rows)),
        key=lambda index: (raw_values[index] - Decimal(allocated[index]), -index),
        reverse=True,
    )
    for index in order[:remaining]:
        allocated[index] += 1

    result = []
    for row, raw_value, estimated_time in zip(rows, raw_values, allocated):
        reconciled = dict(row)
        reconciled.setdefault(RAW_ESTIMATED_TIME_COLUMN, float(raw_value))
        reconciled["Estimated time"] = estimated_time
        result.extend(split_task_row(reconciled))
    return result


def nonnegative_number(value: object, field_name: str, row_number: int) -> float:
    number = pd.to_numeric(pd.Series([value]), errors="coerce").iloc[0]
    if pd.isna(number):
        number = 0
    number = float(number)
    if number < 0:
        raise GenerationError(f"{field_name} cannot be negative (project row {row_number}).")
    return number


def l1_quantity_multiplier(primary: object, secondary: object, tertiary: object, row_number: int = 0) -> float:
    """Return Primary + 0.25*Secondary + 0.10*Tertiary."""
    p = nonnegative_number(primary, "Primary L1s Qty", row_number)
    s = nonnegative_number(secondary, "Secondary L1s Qty", row_number)
    t = nonnegative_number(tertiary, "Tertiary L1s Qty", row_number)
    return weighted_quantity_multiplier(p, s, t)


def choose_project_sheet(excel: pd.ExcelFile, project_path: Path, requested_sheet: str | None) -> str:
    if requested_sheet:
        if requested_sheet not in excel.sheet_names:
            raise GenerationError(
                f"Project sheet '{requested_sheet}' was not found. Available sheets: {', '.join(excel.sheet_names)}"
            )
        return requested_sheet

    if project_path.stem in excel.sheet_names:
        return project_path.stem

    for sheet_name in excel.sheet_names:
        headers = pd.read_excel(excel, sheet_name=sheet_name, nrows=0)
        normalized = {normalized_header(column) for column in headers.columns}
        if "qbomsaved" in normalized:
            return sheet_name

    raise GenerationError("No worksheet containing a QBomSaved column was found in the project workbook.")


def load_project(project_path: Path, project_sheet: str | None = None) -> tuple[pd.DataFrame, pd.ExcelFile | None]:
    suffix = project_path.suffix.casefold()
    if suffix == ".csv":
        project = pd.read_csv(project_path)
        excel = None
    elif suffix in {".xlsx", ".xlsm"}:
        excel = pd.ExcelFile(project_path, engine="openpyxl")
        sheet_name = choose_project_sheet(excel, project_path, project_sheet)
        project = pd.read_excel(excel, sheet_name=sheet_name)
    else:
        raise GenerationError("Project file must be .csv, .xlsx, or .xlsm.")

    project = rename_known_columns(project, PROJECT_COLUMNS)
    required = ["QBomSaved", "Primary L1s Qty", "Secondary L1s Qty", "Tertiary L1s Qty"]
    missing = [column for column in required if column not in project.columns]
    if missing:
        raise GenerationError(f"Project file is missing required columns: {', '.join(missing)}")

    if "SummaryID" in project.columns:
        project = project[
            project["SummaryID"].fillna("").astype(str).str.strip().str.casefold() != "totals"
        ].copy()

    project["QBomSaved"] = project["QBomSaved"].apply(clean_text)
    project = project[project["QBomSaved"] != ""].copy()
    if project.empty:
        raise GenerationError("The project does not reference any qBOM files.")

    return project.reset_index(drop=True), excel


def candidate_qbom_roots(project_path: Path, explicit_dir: Path | None) -> list[Path]:
    candidates = []
    if explicit_dir:
        candidates.append(explicit_dir)
    candidates.extend(
        [
            project_path.parent,
            project_path.parent / "Qboms",
            project_path.parent.parent / "Qboms",
            project_path.parent / "Project Files" / "Qboms",
        ]
    )

    unique = []
    seen = set()
    for candidate in candidates:
        resolved = candidate.resolve()
        key = str(resolved).casefold()
        if key not in seen and resolved.is_dir():
            seen.add(key)
            unique.append(resolved)
    return unique


def find_qbom_file(reference: str, roots: Iterable[Path], project_path: Path) -> Path | None:
    reference_path = Path(reference)
    direct_candidates = []
    if reference_path.is_absolute():
        direct_candidates.append(reference_path)
    else:
        direct_candidates.append(project_path.parent / reference_path)
        direct_candidates.extend(root / reference_path.name for root in roots)

    for candidate in direct_candidates:
        if candidate.is_file():
            return candidate.resolve()

    wanted_names = {reference_path.name.casefold()}
    if not reference_path.suffix:
        wanted_names.update(f"{reference_path.name}{ext}".casefold() for ext in (".csv", ".xlsx", ".xlsm"))

    for root in roots:
        for candidate in root.rglob("*"):
            if candidate.is_file() and candidate.name.casefold() in wanted_names:
                return candidate.resolve()
    return None


def load_qbom_file(path: Path) -> pd.DataFrame:
    if path.suffix.casefold() == ".csv":
        return pd.read_csv(path)
    if path.suffix.casefold() in {".xlsx", ".xlsm"}:
        return pd.read_excel(path, engine="openpyxl")
    raise GenerationError(f"Unsupported qBOM file type: {path}")


def load_qbom_source(
    reference: str,
    project_path: Path,
    project_excel: pd.ExcelFile | None,
    roots: list[Path],
) -> QbomSource:
    sheet_candidate = Path(reference).stem
    if project_excel is not None:
        matching_sheet = next(
            (name for name in project_excel.sheet_names if name.casefold() == sheet_candidate.casefold()),
            None,
        )
        if matching_sheet:
            return QbomSource(
                display_name=f"{project_path.name}:{matching_sheet}",
                data=pd.read_excel(project_excel, sheet_name=matching_sheet),
            )

    qbom_path = find_qbom_file(reference, roots, project_path)
    if qbom_path is None:
        searched = ", ".join(str(root) for root in roots) or str(project_path.parent)
        raise GenerationError(f"qBOM '{reference}' was not found. Searched: {searched}")
    return QbomSource(display_name=qbom_path.name, data=load_qbom_file(qbom_path))


def label_from_set(set_value: object) -> str:
    match = re.search(r"(\d+)", clean_text(set_value))
    if not match:
        raise GenerationError(f"Cannot classify qBOM row because SET value '{clean_text(set_value)}' has no number.")
    set_number = int(match.group(1))
    if set_number <= 3:
        return "PRT"
    if set_number <= 6:
        return "ASSY"
    return "L1"


def normalize_label(value: object) -> str:
    label = clean_text(value).upper().replace("-", " ").replace("_", " ")
    if label in {"PRT", "PART", "PARTS"}:
        return "PRT"
    if label in {"ASSY", "ASSEMBLY", "ASSEMBLIES"}:
        return "ASSY"
    if label in {"L1", "L 1"}:
        return "L1"
    return ""


def summarize_qbom(source: QbomSource) -> tuple[pd.DataFrame, str, str, str]:
    qbom = rename_known_columns(source.data.copy(), QBOM_COLUMNS)
    required_hours = ["Modeling Hrs", "Detailing Hrs", "BOM Hrs"]
    missing_hours = [column for column in required_hours if column not in qbom.columns]
    if missing_hours:
        raise GenerationError(f"{source.display_name} is missing columns: {', '.join(missing_hours)}")

    if "UniqueID" in qbom.columns:
        unique_ids = qbom["UniqueID"].fillna("").astype(str).str.strip()
        qbom = qbom[(unique_ids != "") & (unique_ids.str.casefold() != "totals")].copy()
    else:
        qbom = qbom.dropna(subset=required_hours, how="all").copy()

    if qbom.empty:
        raise GenerationError(f"{source.display_name} does not contain any qBOM detail rows.")

    if "Label" in qbom.columns:
        qbom["_Task group"] = qbom["Label"].apply(normalize_label)
    else:
        qbom["_Task group"] = ""

    unresolved = qbom["_Task group"] == ""
    if unresolved.any():
        if "SET" not in qbom.columns:
            raise GenerationError(f"{source.display_name} needs either a Label or SET column for task grouping.")
        qbom.loc[unresolved, "_Task group"] = qbom.loc[unresolved, "SET"].apply(label_from_set)

    for column in required_hours:
        qbom[column] = pd.to_numeric(qbom[column], errors="coerce").fillna(0.0)

    totals = qbom.groupby("_Task group", as_index=True)[required_hours].sum()
    totals = totals.reindex(["PRT", "ASSY", "L1"], fill_value=0.0)

    unique_id = clean_text(qbom.iloc[0].get("UniqueID", "")) if not qbom.empty else ""
    qbom_name = clean_text(qbom.iloc[0].get("qBOM", "")) if not qbom.empty else ""
    product_family = clean_text(qbom.iloc[0].get("Product Family", "")) if not qbom.empty else ""
    return totals, unique_id, qbom_name, product_family


def build_tasks(
    project: pd.DataFrame,
    project_path: Path,
    project_excel: pd.ExcelFile | None,
    qbom_dir: Path | None = None,
    product: str = "ART",
    project_name: str = "DOAS",
    priority: str = "Normal",
    status: str = "Pending",
    task_type: str = "SW",
    description: str | None = None,
) -> tuple[pd.DataFrame, list[dict[str, object]], pd.DataFrame]:
    roots = candidate_qbom_roots(project_path, qbom_dir)
    task_rows = []
    audit_rows = []
    component_rows = []

    for index, project_row in project.iterrows():
        row_number = index + 2
        reference = clean_text(project_row["QBomSaved"])
        multiplier = l1_quantity_multiplier(
            project_row["Primary L1s Qty"],
            project_row["Secondary L1s Qty"],
            project_row["Tertiary L1s Qty"],
            row_number,
        )
        primary_qty = nonnegative_number(project_row["Primary L1s Qty"], "Primary L1s Qty", row_number)
        secondary_qty = nonnegative_number(project_row["Secondary L1s Qty"], "Secondary L1s Qty", row_number)
        tertiary_qty = nonnegative_number(project_row["Tertiary L1s Qty"], "Tertiary L1s Qty", row_number)
        source = load_qbom_source(reference, project_path, project_excel, roots)
        totals, qbom_id, qbom_name, qbom_product_family = summarize_qbom(source)

        summary_id = clean_text(project_row.get("SummaryID", "")) or project_path.stem
        qbom_id = qbom_id or Path(reference).stem
        qbom_name = qbom_name or Path(reference).stem
        product_family = (
            clean_text(project_row.get("Product Family", ""))
            or qbom_product_family
        )
        task_description = description if description is not None else product_family
        schedule_group = f"{row_number}:{reference}"

        def add_task(
            suffix: str,
            label: str,
            hour_type: str,
            prt_base: float = 0.0,
            assy_base: float = 0.0,
            l1_base: float = 0.0,
        ) -> None:
            base_hours = float(prt_base) + float(assy_base) + float(l1_base)
            primary_hours, secondary_hours, tertiary_hours = weighted_hour_components(
                base_hours,
                primary_qty,
                secondary_qty,
                tertiary_qty,
            )
            estimated_time = round(primary_hours + secondary_hours + tertiary_hours, 2)
            task_row = {
                "Name": f"{summary_id}_{qbom_id}_{qbom_name}_{suffix}",
                "Assignee": "",
                "Product": product,
                "Priority": priority,
                "Due date": "",
                "Project": project_name,
                "Status": status,
                "Labels": label,
                "Estimated time": estimated_time,
                "ECN": "",
                "Task Type": task_type,
                "Description": task_description,
                SCHEDULE_GROUP_COLUMN: schedule_group,
                RAW_ESTIMATED_TIME_COLUMN: estimated_time,
            }
            task_rows.append(task_row)
            component_rows.append(
                {
                    "SummaryID": summary_id,
                    "QBomSaved": reference,
                    "Source": source.display_name,
                    "Task": suffix,
                    "Hour type": hour_type,
                    "PRT base hours": float(prt_base),
                    "ASSY base hours": float(assy_base),
                    "L1 base hours": float(l1_base),
                    "Combined base hours": base_hours,
                    "Primary L1s Qty": primary_qty,
                    "Primary hours": primary_hours,
                    "Secondary L1s Qty": secondary_qty,
                    "Secondary weight": SECONDARY_L1_WEIGHT,
                    "Secondary hours": secondary_hours,
                    "Tertiary L1s Qty": tertiary_qty,
                    "Tertiary weight": TERTIARY_L1_WEIGHT,
                    "Tertiary hours": tertiary_hours,
                    "Estimated time": estimated_time,
                }
            )

        for suffix, group, hour_column, label in TASK_DEFINITIONS:
            group_bases = {"PRT": 0.0, "ASSY": 0.0, "L1": 0.0}
            group_bases[group] = float(totals.loc[group, hour_column])
            add_task(
                suffix,
                label,
                hour_column,
                prt_base=group_bases["PRT"],
                assy_base=group_bases["ASSY"],
                l1_base=group_bases["L1"],
            )

        add_task(
            "BOM/WT",
            "WTPART",
            "BOM Hrs",
            prt_base=float(totals.loc["PRT", "BOM Hrs"]),
            assy_base=float(totals.loc["ASSY", "BOM Hrs"]),
        )

        base_design_hours = float(
            totals[["Modeling Hrs", "Detailing Hrs", "BOM Hrs"]].to_numpy().sum()
        )
        primary_design_hours, secondary_design_hours, tertiary_design_hours = weighted_hour_components(
            base_design_hours,
            primary_qty,
            secondary_qty,
            tertiary_qty,
        )

        audit_rows.append(
            {
                "QBomSaved": reference,
                "Source": source.display_name,
                "Primary L1s Qty": primary_qty,
                "Secondary L1s Qty": secondary_qty,
                "Tertiary L1s Qty": tertiary_qty,
                "Multiplier": multiplier,
                "Base design hours": base_design_hours,
                "Primary design hours": primary_design_hours,
                "Secondary design hours": secondary_design_hours,
                "Tertiary design hours": tertiary_design_hours,
                "Estimated design hours": round(
                    primary_design_hours + secondary_design_hours + tertiary_design_hours, 2
                ),
            }
        )

    return (
        pd.DataFrame(reconcile_and_split_task_rows(task_rows), columns=INTERNAL_TASK_COLUMNS),
        audit_rows,
        pd.DataFrame(component_rows, columns=COMPONENT_COLUMNS),
    )


def write_output(
    tasks: pd.DataFrame,
    audit_rows: list[dict[str, object]],
    components: pd.DataFrame,
    output_path: Path,
) -> None:
    output_path.parent.mkdir(parents=True, exist_ok=True)
    export_tasks = tasks[TASK_COLUMNS]
    if output_path.suffix.casefold() == ".csv":
        export_tasks.to_csv(output_path, index=False)
        components.to_csv(output_path.with_name(f"{output_path.stem}_components.csv"), index=False)
        pd.DataFrame(audit_rows).to_csv(output_path.with_name(f"{output_path.stem}_audit.csv"), index=False)
        return
    if output_path.suffix.casefold() != ".xlsx":
        raise GenerationError("Output file must end in .xlsx or .csv.")

    with pd.ExcelWriter(output_path, engine="openpyxl") as writer:
        export_tasks.to_excel(writer, sheet_name="Tasks", index=False)
        components.to_excel(writer, sheet_name="Components", index=False)
        pd.DataFrame(audit_rows).to_excel(writer, sheet_name="Audit", index=False)

        tasks_sheet = writer.book["Tasks"]
        tasks_sheet.freeze_panes = "A2"
        tasks_sheet.auto_filter.ref = tasks_sheet.dimensions
        task_widths = {
            "A": 62,
            "B": 16,
            "C": 12,
            "D": 12,
            "E": 14,
            "F": 14,
            "G": 14,
            "H": 14,
            "I": 16,
            "J": 18,
            "K": 14,
            "L": 14,
            "M": 24,
        }
        for column, width in task_widths.items():
            tasks_sheet.column_dimensions[column].width = width
        for cell in tasks_sheet["J"][1:]:
            cell.number_format = "0"

        components_sheet = writer.book["Components"]
        components_sheet.freeze_panes = "D2"
        components_sheet.auto_filter.ref = components_sheet.dimensions
        component_widths = {
            "A": 20, "B": 24, "C": 30, "D": 18, "E": 18,
            "F": 18, "G": 18, "H": 18, "I": 20, "J": 18,
            "K": 18, "L": 20, "M": 18, "N": 20, "O": 18,
            "P": 18, "Q": 18, "R": 18,
        }
        for column, width in component_widths.items():
            components_sheet.column_dimensions[column].width = width
        for column in ("F", "G", "H", "I", "K", "N", "Q", "R"):
            for cell in components_sheet[column][1:]:
                cell.number_format = "0.00"
        for column in ("M", "P"):
            for cell in components_sheet[column][1:]:
                cell.number_format = "0.00"

        audit_sheet = writer.book["Audit"]
        audit_sheet.freeze_panes = "A2"
        audit_sheet.auto_filter.ref = audit_sheet.dimensions
        audit_sheet.column_dimensions["A"].width = 24
        audit_sheet.column_dimensions["B"].width = 60
        for column in ("C", "D", "E", "F", "G", "H", "I", "J", "K"):
            audit_sheet.column_dimensions[column].width = 20

        header_fill = PatternFill("solid", fgColor="1F4E78")
        header_font = Font(color="FFFFFF", bold=True)
        for sheet in (tasks_sheet, components_sheet, audit_sheet):
            for cell in sheet[1]:
                cell.fill = header_fill
                cell.font = header_font
                cell.alignment = Alignment(horizontal="center", vertical="center")


def parse_args(argv: list[str] | None = None) -> argparse.Namespace:
    parser = argparse.ArgumentParser(
        description="Generate task estimated times from one project file and its related qBOM files."
    )
    parser.add_argument("project_file", type=Path, help="Project summary .csv/.xlsx/.xlsm file")
    parser.add_argument("--qbom-dir", type=Path, help="Folder containing referenced qBOM files")
    parser.add_argument("--project-sheet", help="Project worksheet name for Excel input")
    parser.add_argument("--output", type=Path, help="Output .xlsx or .csv path")
    parser.add_argument("--product", default="ART")
    parser.add_argument("--project", dest="task_project", default="DOAS")
    parser.add_argument("--priority", default="Normal")
    parser.add_argument("--status", default="Pending")
    parser.add_argument("--task-type", default="SW")
    parser.add_argument("--description", help="Override Description for every generated task")
    return parser.parse_args(argv)


def main(argv: list[str] | None = None) -> int:
    args = parse_args(argv)
    project_path = args.project_file.resolve()
    if not project_path.is_file():
        print(f"Error: project file not found: {project_path}", file=sys.stderr)
        return 2

    output_path = (args.output or project_path.with_name(f"{project_path.stem}_tasks.xlsx")).resolve()

    try:
        project, project_excel = load_project(project_path, args.project_sheet)
        tasks, audit_rows, components = build_tasks(
            project,
            project_path,
            project_excel,
            qbom_dir=args.qbom_dir.resolve() if args.qbom_dir else None,
            product=args.product,
            project_name=args.task_project,
            priority=args.priority,
            status=args.status,
            task_type=args.task_type,
            description=args.description,
        )
        write_output(tasks, audit_rows, components, output_path)
    except (GenerationError, OSError, ValueError, pd.errors.ParserError) as error:
        print(f"Error: {error}", file=sys.stderr)
        return 1

    print(f"Created {output_path}")
    print(f"Generated {len(tasks)} tasks from {len(audit_rows)} qBOM reference(s).")
    print(f"Total estimated design hours: {tasks['Estimated time'].sum():.0f}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
