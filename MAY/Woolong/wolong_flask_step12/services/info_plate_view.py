"""Build a complete Info_Plate-style view model from CalculationResult.

This module is intentionally UI-oriented. It does not calculate anything; it only
organizes the already-calculated Python replacement of the Excel/VBA Info_Plate
output into sections that can be rendered by Flask or returned as JSON.
"""
from __future__ import annotations

from typing import Any, Dict, Iterable, List


EMPTY_VALUES = {None, "", "None", "nan", "NaN"}


def _is_empty(value: Any) -> bool:
    if value in EMPTY_VALUES:
        return True
    if isinstance(value, (list, tuple, dict)) and len(value) == 0:
        return True
    return False


def _display(value: Any) -> str:
    if _is_empty(value):
        return "—"
    if isinstance(value, bool):
        return "Yes" if value else "No"
    return str(value)


def _row(label: str, value: Any, key: str = "") -> Dict[str, str]:
    return {"label": label, "value": _display(value), "key": key}


def _rows_from_dict(data: Dict[str, Any], *, include_empty: bool = False) -> List[Dict[str, str]]:
    rows: List[Dict[str, str]] = []
    for key, value in data.items():
        if isinstance(value, (dict, list, tuple)):
            continue
        if not include_empty and _is_empty(value):
            continue
        label = key.replace("_", " ").title()
        rows.append(_row(label, value, key))
    return rows


def _table_rows(items: Iterable[Dict[str, Any]], columns: List[str]) -> List[Dict[str, str]]:
    output: List[Dict[str, str]] = []
    for item in items:
        output.append({column: _display(item.get(column)) for column in columns})
    return output


def build_info_plate_view(result_dict: Dict[str, Any]) -> Dict[str, Any]:
    """Create the full visual data model for the Info Plate page."""
    model = result_dict.get("model", {}) or {}
    electrical = result_dict.get("electrical", {}) or {}
    mca = result_dict.get("mca_mocp", {}) or {}
    errors = result_dict.get("errors", {}) or {}

    header_rows = [
        _row("Model number", model.get("model_number")),
        _row("Model family", model.get("model_string")),
        _row("Series", model.get("series")),
        _row("Voltage", electrical.get("voltage")),
        _row("Chassis", model.get("chassis") or electrical.get("chassis")),
        _row("Size", model.get("size")),
        _row("Gas heat", model.get("gas")),
        _row("50-series / electric heat capable", model.get("is_50")),
        _row("Heat level", model.get("heat_level")),
        _row("Heat code", model.get("heat")),
        _row("Charge", electrical.get("charge")),
        _row("SCCR", electrical.get("sccr")),
        _row("SCCR kA", electrical.get("sccr_ka")),
    ]

    electrical_rating_rows = [
        _row("MCA", mca.get("mca")),
        _row("MOCP", mca.get("mocp")),
        _row("Fuse", mca.get("fuse")),
        _row("Disconnect", mca.get("disconnect")),
        _row("LRA", mca.get("lra")),
        _row("MCA 2", mca.get("mca_2")),
        _row("MOCP 2", mca.get("mocp_2")),
        _row("Disconnect 2", mca.get("disconnect_2")),
        _row("Feeder", mca.get("feeder")),
        _row("Disconnect LRA", mca.get("disconnect_lra")),
        _row("Single point box", mca.get("single_point_box")),
        _row("Single point box HSCCR", mca.get("single_point_box_hsccr")),
        _row("Number of wires", mca.get("num_wires")),
        _row("Actual number of wires", mca.get("actual_num_wires")),
    ]

    option_rows = [
        _row("Control type", model.get("control_type")),
        _row("Control type text", model.get("control_type_text")),
        _row("Sensor option", model.get("sensor_option")),
        _row("Motor drive", model.get("motor_drive")),
        _row("Design", model.get("design")),
        _row("Refrigerant option", model.get("refrigerant_option")),
        _row("Convenience outlet", model.get("conv_outlet")),
        _row("Terminal block", model.get("terminal_block")),
        _row("Intake", model.get("intake")),
        _row("Exhaust", model.get("exhaust")),
        _row("Power exhaust", model.get("pe")),
        _row("ERV", model.get("erv")),
        _row("Economizer", model.get("econ")),
        _row("Economizer / ERV", model.get("econ_erv")),
        _row("HACR", model.get("hacr")),
        _row("HSCCR", model.get("hsccr")),
        _row("Packaging", model.get("packaging")),
    ]

    compressor_columns = ["source_range", "name", "part_number", "quantity", "rla", "lra"]
    motor_columns = ["source_range", "name", "part_number", "quantity", "fla", "lra", "hp", "kw", "duty", "num_wires", "actual_num_wires"]
    accessory_columns = ["name", "amps", "quantity", "source_range", "duty"]
    accessory_row_columns = ["name", "mca", "mocp", "disconnect", "lra", "single_point_box", "single_point_box_hsccr", "source"]

    messages = errors.get("messages", []) or []
    notes = []
    notes.extend(electrical.get("notes", []) or [])
    notes.extend(mca.get("calculation_notes", []) or [])

    all_model_rows = _rows_from_dict(model, include_empty=True)
    all_electrical_rows = _rows_from_dict(electrical, include_empty=True)
    all_mca_rows = _rows_from_dict(mca, include_empty=True)

    return {
        "title": "Info Plate Preview",
        "model_number": model.get("model_number", ""),
        "summary_cards": [
            {"label": "Voltage", "value": _display(electrical.get("voltage"))},
            {"label": "MCA", "value": _display(mca.get("mca"))},
            {"label": "MOCP/Fuse", "value": _display(mca.get("fuse") or mca.get("mocp"))},
            {"label": "Disconnect", "value": _display(mca.get("disconnect"))},
            {"label": "LRA", "value": _display(mca.get("lra"))},
            {"label": "Chassis", "value": _display(model.get("chassis") or electrical.get("chassis"))},
        ],
        "sections": [
            {"id": "nameplate", "title": "Nameplate / unit summary", "rows": header_rows},
            {"id": "ratings", "title": "Electrical ratings", "rows": electrical_rating_rows},
            {"id": "options", "title": "Decoded model options", "rows": option_rows},
        ],
        "tables": [
            {"id": "compressors", "title": "Compressors", "columns": compressor_columns, "rows": _table_rows(electrical.get("compressors", []) or [], compressor_columns)},
            {"id": "motors", "title": "Motors / loads", "columns": motor_columns, "rows": _table_rows(electrical.get("motors", []) or [], motor_columns)},
            {"id": "accessories", "title": "Accessory loads", "columns": accessory_columns, "rows": _table_rows(electrical.get("accessories", []) or [], accessory_columns)},
            {"id": "accessory_mca", "title": "Accessory MCA/MOCP rows", "columns": accessory_row_columns, "rows": _table_rows(mca.get("accessory_rows", []) or [], accessory_row_columns)},
        ],
        "notes": notes,
        "messages": messages,
        "complete_field_sections": [
            {"title": "All model fields", "rows": all_model_rows},
            {"title": "All electrical fields", "rows": all_electrical_rows},
            {"title": "All MCA/MOCP fields", "rows": all_mca_rows},
        ],
    }
