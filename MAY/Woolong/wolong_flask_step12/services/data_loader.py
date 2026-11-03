from pathlib import Path
from typing import Dict
import pandas as pd


DATA_DIR = Path(__file__).resolve().parents[1] / "data"

CORE_LOOKUP_FILES = {
    "Data_Common": "Data_Common.csv",
    "Data_Misc": "Data_Misc.csv",
    "Data_FE": "Data_FE.csv",
    "Data_FE_Copeland": "Data_FE_Copeland.csv",
    "Data_FE_LG": "Data_FE_LG.csv",
    "Data_GE": "Data_GE.csv",
    "Data_JE": "Data_JE.csv",
    "Data_38AX": "Data_38AX.csv",
    "Data_GasFE": "Data_GasFE.csv",
    "Data_GasGE": "Data_GasGE.csv",
    "Data_GasJE": "Data_GasJE.csv",
    "Data_ERV": "Data_ERV.csv",
    "FIOPList_FEStd": "FIOPList_FEStd.csv",
}


def load_lookup_tables() -> Dict[str, pd.DataFrame]:
    """Load extracted workbook lookup tables from app/data.

    The Step 3 package includes only the structural code. Copy the Step 1 CSVs
    into data/ using scripts/copy_step1_csvs.py, or place files manually.
    """
    tables: Dict[str, pd.DataFrame] = {}
    for table_name, file_name in CORE_LOOKUP_FILES.items():
        path = DATA_DIR / file_name
        if path.exists():
            tables[table_name] = pd.read_csv(path, dtype=str, header=None).fillna("")
    return tables
