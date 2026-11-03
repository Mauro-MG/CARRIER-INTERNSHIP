from __future__ import annotations

import csv
import io
from dataclasses import dataclass, asdict, field
from pathlib import Path
from typing import Any, Dict, Iterable, List, Optional, Sequence, Tuple

from services.calculation_service import run_calculation
from services.output_builder import build_output

DEFAULT_COMPARISON_FIELDS: Tuple[str, ...] = (
    "model.series",
    "model.model_string",
    "model.size",
    "model.voltage_index",
    "model.chassis",
    "electrical.voltage",
    "electrical.chassis",
    "electrical.charge_summary",
    "mca_mocp.mca",
    "mca_mocp.mocp",
    "mca_mocp.fuse",
    "mca_mocp.disconnect",
    "mca_mocp.lra",
    "mca_mocp.single_point_box",
    "mca_mocp.single_point_box_hsccr",
    "mca_mocp.num_wires",
    "mca_mocp.actual_num_wires",
)

CONTROL_COLUMNS = {
    "model_number",
    "case_id",
    "notes",
    "expected_error_codes",
    "expected_warning_codes",
}


@dataclass
class FieldComparison:
    field: str
    expected: str = ""
    actual: Any = None
    status: str = "not_checked"  # pass, fail, missing_expected, not_checked
    difference: str = ""


@dataclass
class ValidationCaseResult:
    case_id: str
    model_number: str
    status: str
    comparisons: List[FieldComparison] = field(default_factory=list)
    error_codes: List[str] = field(default_factory=list)
    warning_codes: List[str] = field(default_factory=list)
    messages: List[str] = field(default_factory=list)
    raw_result: Dict[str, Any] = field(default_factory=dict)

    def to_dict(self) -> Dict[str, Any]:
        return asdict(self)


@dataclass
class ValidationRunResult:
    total_cases: int = 0
    passed_cases: int = 0
    failed_cases: int = 0
    skipped_cases: int = 0
    cases: List[ValidationCaseResult] = field(default_factory=list)

    @property
    def status(self) -> str:
        if self.failed_cases:
            return "fail"
        if self.total_cases == 0:
            return "empty"
        return "pass"

    def to_dict(self) -> Dict[str, Any]:
        data = asdict(self)
        data["status"] = self.status
        return data


def _get_path(data: Dict[str, Any], dotted_path: str) -> Any:
    current: Any = data
    for part in dotted_path.split("."):
        if isinstance(current, dict):
            current = current.get(part)
        elif isinstance(current, list):
            # Supports paths such as mca_mocp.accessory_rows.0.name if needed.
            if not part.isdigit():
                return None
            idx = int(part)
            if idx >= len(current):
                return None
            current = current[idx]
        else:
            return None
    return current


def _normalize(value: Any) -> str:
    if value is None:
        return ""
    if isinstance(value, bool):
        return "TRUE" if value else "FALSE"
    return str(value).strip()


def _as_float(value: Any) -> Optional[float]:
    text = _normalize(value).replace(",", "")
    if text == "":
        return None
    try:
        return float(text)
    except ValueError:
        return None


def compare_values(expected: Any, actual: Any, tolerance: float = 0.01) -> Tuple[bool, str]:
    expected_text = _normalize(expected)
    actual_text = _normalize(actual)

    exp_num = _as_float(expected)
    act_num = _as_float(actual)
    if exp_num is not None and act_num is not None:
        diff = act_num - exp_num
        return abs(diff) <= tolerance, f"{diff:.6g}"

    return expected_text.casefold() == actual_text.casefold(), ""


def read_validation_csv(csv_text: str) -> List[Dict[str, str]]:
    stream = io.StringIO(csv_text)
    reader = csv.DictReader(stream)
    return [dict(row) for row in reader]


def _fields_to_check(row: Dict[str, str], explicit_fields: Optional[Sequence[str]] = None) -> List[str]:
    if explicit_fields:
        return list(explicit_fields)

    expected_columns = [
        col[len("expected_") :]
        for col in row.keys()
        if col.startswith("expected_") and col not in {"expected_error_codes", "expected_warning_codes"}
    ]
    if expected_columns:
        return expected_columns
    return list(DEFAULT_COMPARISON_FIELDS)


def _extract_expected(row: Dict[str, str], field_name: str) -> str:
    return _normalize(row.get(f"expected_{field_name}", row.get(field_name, "")))


def _message_codes(raw_result: Dict[str, Any], severity: str) -> List[str]:
    messages = raw_result.get("errors", {}).get("messages", []) or []
    return [m.get("code", "") for m in messages if m.get("severity") == severity]


def _check_expected_codes(expected_csv_value: str, actual_codes: List[str]) -> Tuple[bool, str]:
    expected_codes = [c.strip() for c in expected_csv_value.replace(";", "|").split("|") if c.strip()]
    if not expected_codes:
        return True, ""
    missing = [c for c in expected_codes if c not in actual_codes]
    if missing:
        return False, "Missing: " + ", ".join(missing)
    return True, ""


def validate_rows(
    rows: Iterable[Dict[str, str]],
    fields: Optional[Sequence[str]] = None,
    tolerance: float = 0.01,
) -> ValidationRunResult:
    run = ValidationRunResult()

    for idx, row in enumerate(rows, start=1):
        model_number = _normalize(row.get("model_number"))
        case_id = _normalize(row.get("case_id")) or str(idx)
        if not model_number:
            run.skipped_cases += 1
            case = ValidationCaseResult(case_id=case_id, model_number="", status="skipped")
            case.messages.append("Missing model_number; case skipped.")
            run.cases.append(case)
            continue

        calculation = run_calculation(model_number)
        raw = build_output(calculation)
        error_codes = _message_codes(raw, "error")
        warning_codes = _message_codes(raw, "warning")

        comparisons: List[FieldComparison] = []
        case_failed = False
        checked_any = False
        for field_name in _fields_to_check(row, fields):
            expected = _extract_expected(row, field_name)
            if expected == "":
                comparisons.append(FieldComparison(field=field_name, expected="", actual=_get_path(raw, field_name), status="missing_expected"))
                continue
            checked_any = True
            actual = _get_path(raw, field_name)
            ok, diff = compare_values(expected, actual, tolerance=tolerance)
            status = "pass" if ok else "fail"
            if not ok:
                case_failed = True
            comparisons.append(FieldComparison(field=field_name, expected=expected, actual=actual, status=status, difference=diff))

        expected_errors_ok, expected_errors_msg = _check_expected_codes(row.get("expected_error_codes", ""), error_codes)
        expected_warnings_ok, expected_warnings_msg = _check_expected_codes(row.get("expected_warning_codes", ""), warning_codes)
        if not expected_errors_ok or not expected_warnings_ok:
            case_failed = True

        messages = []
        if expected_errors_msg:
            messages.append("Expected errors: " + expected_errors_msg)
        if expected_warnings_msg:
            messages.append("Expected warnings: " + expected_warnings_msg)
        if not checked_any and not row.get("expected_error_codes") and not row.get("expected_warning_codes"):
            messages.append("No expected values provided; case calculated but not graded.")

        status = "fail" if case_failed else "pass"
        run.total_cases += 1
        if case_failed:
            run.failed_cases += 1
        else:
            run.passed_cases += 1

        run.cases.append(
            ValidationCaseResult(
                case_id=case_id,
                model_number=model_number,
                status=status,
                comparisons=comparisons,
                error_codes=error_codes,
                warning_codes=warning_codes,
                messages=messages,
                raw_result=raw,
            )
        )

    return run


def validate_csv_text(csv_text: str, fields: Optional[Sequence[str]] = None, tolerance: float = 0.01) -> ValidationRunResult:
    return validate_rows(read_validation_csv(csv_text), fields=fields, tolerance=tolerance)


def validate_csv_file(path: str | Path, fields: Optional[Sequence[str]] = None, tolerance: float = 0.01) -> ValidationRunResult:
    text = Path(path).read_text(encoding="utf-8-sig")
    return validate_csv_text(text, fields=fields, tolerance=tolerance)


def flatten_validation_results(run: ValidationRunResult) -> List[Dict[str, Any]]:
    rows: List[Dict[str, Any]] = []
    for case in run.cases:
        if not case.comparisons:
            rows.append(
                {
                    "case_id": case.case_id,
                    "model_number": case.model_number,
                    "case_status": case.status,
                    "field": "",
                    "expected": "",
                    "actual": "",
                    "field_status": "",
                    "difference": "",
                    "errors": "|".join(case.error_codes),
                    "warnings": "|".join(case.warning_codes),
                    "messages": "|".join(case.messages),
                }
            )
            continue
        for comp in case.comparisons:
            rows.append(
                {
                    "case_id": case.case_id,
                    "model_number": case.model_number,
                    "case_status": case.status,
                    "field": comp.field,
                    "expected": comp.expected,
                    "actual": _normalize(comp.actual),
                    "field_status": comp.status,
                    "difference": comp.difference,
                    "errors": "|".join(case.error_codes),
                    "warnings": "|".join(case.warning_codes),
                    "messages": "|".join(case.messages),
                }
            )
    return rows


def write_validation_report_csv(run: ValidationRunResult, output_path: str | Path) -> Path:
    output_path = Path(output_path)
    output_path.parent.mkdir(parents=True, exist_ok=True)
    rows = flatten_validation_results(run)
    fieldnames = [
        "case_id",
        "model_number",
        "case_status",
        "field",
        "expected",
        "actual",
        "field_status",
        "difference",
        "errors",
        "warnings",
        "messages",
    ]
    with output_path.open("w", newline="", encoding="utf-8") as f:
        writer = csv.DictWriter(f, fieldnames=fieldnames)
        writer.writeheader()
        writer.writerows(rows)
    return output_path
