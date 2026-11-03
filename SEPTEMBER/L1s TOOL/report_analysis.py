import json
import sys
from collections import Counter
from pathlib import Path

d = json.loads(Path(sys.argv[1]).read_text(encoding="utf-8"))
print("SHEET ORDER:", " | ".join(d["workbook"]["sheet_order"]))
print("DEFINED NAMES:")
for x in d["workbook"]["defined_names"]:
    print(" ", x)
print("PACKAGE FEATURES:")
for k, v in d["package"].items():
    if k not in {"parts", "xl/workbook.xml", "xl/_rels/workbook.xml.rels", "docProps/core.xml", "docProps/app.xml"}:
        print(" ", k, v)

for s in d["sheets"]:
    print("\n###", s["title"], "state=", s["state"], "used=", s["used_bounds"], "formulas=", s["formula_count"])
    print("protection", s["sheet_protection"], "freeze", s["freeze_panes"], "filter", s["auto_filter"], "print", s["print_area"])
    if s["data_validations"]:
        print("validations", s["data_validations"])
    if s["tables"]:
        print("tables", s["tables"])
    if s["hidden_rows"] or s["hidden_columns"]:
        print("hidden rows", s["hidden_rows"][:100], "hidden cols", s["hidden_columns"])
    if s["formula_functions"]:
        print("formula functions", s["formula_functions"])
    if s["errors"]:
        print("ERRORS", s["errors"][:50])

    cells = s["nonempty"]
    if s["title"] in {"BOM1", "WD-PART", "3. ValidationSAP"}:
        for rowno in sorted({int(''.join(filter(str.isdigit, c["cell"]))) for c in cells})[:12]:
            vals = [(c["cell"], c["value"], c["cached_value"]) for c in cells if int(''.join(filter(str.isdigit, c["cell"]))) == rowno]
            print("row", rowno, vals)
        print("last cells", [(c["cell"], c["value"]) for c in cells[-30:]])
    else:
        print("cells", [(c["cell"], c["value"], c["cached_value"]) for c in cells])
    if s["formulas"]:
        print("formula sample", s["formulas"][:100])

