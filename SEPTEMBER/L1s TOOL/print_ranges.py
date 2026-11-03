import sys
from openpyxl import load_workbook
from openpyxl.utils import range_boundaries, get_column_letter

path = sys.argv[1]
wb = load_workbook(path, data_only=False, keep_vba=True)
wbv = load_workbook(path, data_only=True, keep_vba=True)

ranges = {
    "AD1": ["A1:U16"],
    "Sheet1": ["A1:J44"],
    "REF DESIGN": ["A1:K5"],
    "RUN TEST": ["A1:K9"],
    "1. WindchillAD": ["B1:U15", "W1:AC15", "AZ1:AZ7"],
    "2. WindchillSAP": ["B1:T15", "AZ1:AZ7"],
    "3. ValidationSAP": ["B1:X44", "AZ1:BD44"],
    "WD-PART": ["A1:U12"],
    "WD-BOM": ["A1:H19"],
}

for sheet, rs in ranges.items():
    ws, wsv = wb[sheet], wbv[sheet]
    print(f"\n## {sheet}")
    for rg in rs:
        print(f"### {rg}")
        minc, minr, maxc, maxr = range_boundaries(rg)
        for r in range(minr, maxr + 1):
            vals = []
            for c in range(minc, maxc + 1):
                cell = ws.cell(r,c)
                value = cell.value
                if value is not None:
                    if not isinstance(value, (str,int,float,bool)):
                        value = getattr(value, "text", str(value))
                    vals.append(f"{get_column_letter(c)}{r}={value!r} [cached={wsv.cell(r,c).value!r}]")
            if vals:
                print(" | ".join(vals))
