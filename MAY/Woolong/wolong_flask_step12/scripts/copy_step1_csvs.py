"""Copy the core Step 1 exported sheet CSVs into the Flask app data folder.

Usage from project root:
    python scripts/copy_step1_csvs.py /path/to/wolong_step1_data_extract/sheets_csv
"""
from pathlib import Path
import shutil
import sys

CORE_SHEETS = {
    "05_Data_Common.csv": "Data_Common.csv",
    "06_Data_Misc.csv": "Data_Misc.csv",
    "07_Data_FE.csv": "Data_FE.csv",
    "08_Data_FE_Copeland.csv": "Data_FE_Copeland.csv",
    "09_Data_FE_LG.csv": "Data_FE_LG.csv",
    "10_Data_ERV.csv": "Data_ERV.csv",
    "11_Data_GE.csv": "Data_GE.csv",
    "12_Data_JE.csv": "Data_JE.csv",
    "13_Data_38AX.csv": "Data_38AX.csv",
    "19_Data_GasFE.csv": "Data_GasFE.csv",
    "20_Data_GasGE.csv": "Data_GasGE.csv",
    "21_Data_GasJE.csv": "Data_GasJE.csv",
    "22_FIOPList_FEStd.csv": "FIOPList_FEStd.csv",
}


def main() -> int:
    if len(sys.argv) != 2:
        print("Usage: python scripts/copy_step1_csvs.py /path/to/sheets_csv")
        return 2

    source_dir = Path(sys.argv[1]).expanduser().resolve()
    target_dir = Path(__file__).resolve().parents[1] / "data"
    target_dir.mkdir(exist_ok=True)

    copied = 0
    for source_name, target_name in CORE_SHEETS.items():
        source = source_dir / source_name
        target = target_dir / target_name
        if source.exists():
            shutil.copy2(source, target)
            print(f"copied {source.name} -> data/{target.name}")
            copied += 1
        else:
            print(f"missing {source.name}")

    print(f"Done. Copied {copied}/{len(CORE_SHEETS)} files.")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
