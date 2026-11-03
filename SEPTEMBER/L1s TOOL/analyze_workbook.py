import json
import re
import sys
import zipfile
from collections import Counter, defaultdict
from pathlib import Path

from lxml import etree
from openpyxl import load_workbook
from openpyxl.utils import get_column_letter


SOURCE = Path(sys.argv[1]).resolve()
OUT = Path(sys.argv[2]).resolve()
OUT.mkdir(parents=True, exist_ok=True)


def serial(value):
    if value is None or isinstance(value, (str, int, float, bool)):
        return value
    return str(value)


def formula_category(formula):
    if not isinstance(formula, str) or not formula.startswith("="):
        return None
    found = re.findall(r"\b([A-Z][A-Z0-9_.]*)\s*\(", formula.upper())
    return found


wb = load_workbook(SOURCE, read_only=False, data_only=False, keep_vba=True, keep_links=True)
wb_values = load_workbook(SOURCE, read_only=False, data_only=True, keep_vba=True, keep_links=True)

result = {
    "source": str(SOURCE),
    "workbook": {
        "sheet_order": wb.sheetnames,
        "calculation": {
            "mode": getattr(wb.calculation, "calcMode", None),
            "fullCalcOnLoad": getattr(wb.calculation, "fullCalcOnLoad", None),
            "forceFullCalc": getattr(wb.calculation, "forceFullCalc", None),
        },
        "security": {
            "lockStructure": wb.security.lockStructure if wb.security else None,
            "lockWindows": wb.security.lockWindows if wb.security else None,
        },
        "defined_names": [],
    },
    "sheets": [],
}

for name, item in wb.defined_names.items():
    result["workbook"]["defined_names"].append({
        "name": name,
        "attr_text": item.attr_text,
        "hidden": item.hidden,
        "localSheetId": item.localSheetId,
        "comment": item.comment,
    })

for ws in wb.worksheets:
    wsv = wb_values[ws.title]
    nonempty = []
    formulas = []
    errors = []
    formula_functions = Counter()
    formula_shapes = Counter()
    first_row, last_row, first_col, last_col = None, 0, None, 0
    for row in ws.iter_rows():
        for c in row:
            if c.value is None:
                continue
            nonempty.append({
                "cell": c.coordinate,
                "value": serial(c.value),
                "cached_value": serial(wsv[c.coordinate].value),
                "number_format": c.number_format,
                "style_id": c.style_id,
                "data_type": c.data_type,
                "locked": c.protection.locked,
                "hidden_formula": c.protection.hidden,
                "comment": c.comment.text if c.comment else None,
                "hyperlink": c.hyperlink.target if c.hyperlink else None,
            })
            first_row = c.row if first_row is None else min(first_row, c.row)
            last_row = max(last_row, c.row)
            first_col = c.column if first_col is None else min(first_col, c.column)
            last_col = max(last_col, c.column)
            if c.data_type == "f" or (isinstance(c.value, str) and c.value.startswith("=")):
                formula_text = c.value if isinstance(c.value, str) else getattr(c.value, "text", str(c.value))
                formulas.append({"cell": c.coordinate, "formula": formula_text, "cached_value": serial(wsv[c.coordinate].value)})
                for fn in formula_category(formula_text) or []:
                    formula_functions[fn] += 1
                shape = re.sub(r"\$?[A-Z]{1,3}\$?\d+", "<CELL>", formula_text.upper())
                formula_shapes[shape] += 1
            if c.data_type == "e" or (isinstance(c.value, str) and c.value.startswith("#")):
                errors.append({"cell": c.coordinate, "value": serial(c.value)})

    dvs = []
    if ws.data_validations:
        for dv in ws.data_validations.dataValidation:
            dvs.append({
                "ranges": str(dv.sqref), "type": dv.type, "operator": dv.operator,
                "formula1": dv.formula1, "formula2": dv.formula2,
                "allow_blank": dv.allow_blank, "showErrorMessage": dv.showErrorMessage,
                "errorTitle": dv.errorTitle, "error": dv.error,
                "promptTitle": dv.promptTitle, "prompt": dv.prompt,
            })

    cfs = []
    try:
        for cf_obj, rules in ws.conditional_formatting._cf_rules.items():
            cfs.append({"ranges": str(cf_obj.sqref), "rules": [
                {"type": r.type, "operator": getattr(r, "operator", None),
                 "formula": getattr(r, "formula", None), "priority": getattr(r, "priority", None)} for r in rules
            ]})
    except Exception as exc:
        cfs.append({"parse_error": str(exc)})

    tables = []
    for table in ws.tables.values():
        tables.append({"name": table.name, "displayName": table.displayName, "ref": table.ref,
                       "columns": [col.name for col in table.tableColumns]})

    sheet = {
        "title": ws.title,
        "state": ws.sheet_state,
        "dimensions": ws.calculate_dimension(),
        "used_bounds": None if first_row is None else f"{get_column_letter(first_col)}{first_row}:{get_column_letter(last_col)}{last_row}",
        "nonempty_count": len(nonempty),
        "formula_count": len(formulas),
        "formula_functions": formula_functions.most_common(),
        "common_formula_shapes": formula_shapes.most_common(30),
        "errors": errors,
        "merged_ranges": [str(x) for x in ws.merged_cells.ranges],
        "freeze_panes": str(ws.freeze_panes) if ws.freeze_panes else None,
        "auto_filter": str(ws.auto_filter.ref) if ws.auto_filter.ref else None,
        "print_area": str(ws.print_area) if ws.print_area else None,
        "print_titles": str(ws.print_titles) if ws.print_titles else None,
        "sheet_protection": {
            "enabled": bool(ws.protection.sheet), "password_hash": ws.protection.password,
            "selectLockedCells": ws.protection.selectLockedCells,
            "selectUnlockedCells": ws.protection.selectUnlockedCells,
            "formatCells": ws.protection.formatCells,
            "insertRows": ws.protection.insertRows,
            "deleteRows": ws.protection.deleteRows,
        },
        "views": [{"showGridLines": v.showGridLines, "zoomScale": v.zoomScale,
                   "topLeftCell": v.topLeftCell, "rightToLeft": v.rightToLeft} for v in ws.views.sheetView],
        "hidden_rows": [i for i, d in ws.row_dimensions.items() if d.hidden],
        "hidden_columns": [k for k, d in ws.column_dimensions.items() if d.hidden],
        "data_validations": dvs,
        "conditional_formatting": cfs,
        "tables": tables,
        "images": len(ws._images),
        "charts": len(ws._charts),
        "nonempty": nonempty,
        "formulas": formulas,
    }
    result["sheets"].append(sheet)


with zipfile.ZipFile(SOURCE) as zf:
    names = zf.namelist()
    result["package"] = {
        "parts": names,
        "has_vba": "xl/vbaProject.bin" in names,
        "external_links": [n for n in names if n.startswith("xl/externalLinks/") and n.endswith(".xml")],
        "connections": [n for n in names if n == "xl/connections.xml"],
        "queries": [n for n in names if "quer" in n.lower()],
        "tables": [n for n in names if n.startswith("xl/tables/") and n.endswith(".xml")],
        "pivot_tables": [n for n in names if n.startswith("xl/pivotTables/") and n.endswith(".xml")],
        "pivot_cache": [n for n in names if n.startswith("xl/pivotCache/")],
        "comments": [n for n in names if "comments" in n.lower()],
        "ctrl_props": [n for n in names if n.startswith("xl/ctrlProps/")],
        "active_x": [n for n in names if n.startswith("xl/activeX/")],
        "custom_xml": [n for n in names if n.startswith("customXml/")],
        "printer_settings": [n for n in names if n.startswith("xl/printerSettings/")],
    }
    for part in ["xl/workbook.xml", "xl/_rels/workbook.xml.rels", "docProps/core.xml", "docProps/app.xml"]:
        if part in names:
            result["package"][part] = zf.read(part).decode("utf-8", errors="replace")
    vba_path = OUT / "vbaProject.bin"
    if "xl/vbaProject.bin" in names:
        vba_path.write_bytes(zf.read("xl/vbaProject.bin"))

(OUT / "workbook_analysis.json").write_text(json.dumps(result, indent=2, ensure_ascii=False), encoding="utf-8")

summary = {
    "source": result["source"],
    "workbook": result["workbook"],
    "package": {k: v for k, v in result["package"].items() if not k.endswith(".xml")},
    "sheets": [{k: v for k, v in s.items() if k not in {"nonempty", "formulas", "conditional_formatting", "common_formula_shapes"}} for s in result["sheets"]],
}
(OUT / "workbook_summary.json").write_text(json.dumps(summary, indent=2, ensure_ascii=False), encoding="utf-8")
print(json.dumps({"analysis": str(OUT / 'workbook_analysis.json'), "sheets": [
    {"title": s["title"], "state": s["state"], "used": s["used_bounds"], "cells": s["nonempty_count"],
     "formulas": s["formula_count"], "validations": len(s["data_validations"]), "protected": s["sheet_protection"]["enabled"]}
    for s in result["sheets"]
]}, indent=2))
