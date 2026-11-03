from __future__ import annotations

import re
from dataclasses import dataclass
from pathlib import Path
from typing import Dict, Optional

import pandas as pd
from openpyxl.utils.cell import column_index_from_string

DATA_DIR = Path(__file__).resolve().parents[1] / "data"
DEFINED_NAMES_PATH = DATA_DIR / "defined_names.csv"


@dataclass(frozen=True)
class DefinedRange:
    name: str
    scope: str
    sheet: str
    start_row: int  # 1-based Excel row
    start_col: int  # 1-based Excel col
    end_row: int
    end_col: int
    refers_to: str


_RANGE_RE = re.compile(
    r"(?P<sheet>'?[^'!]+(?: [^'!]+)*'?)[!]\$(?P<c1>[A-Z]+)\$(?P<r1>\d+)(?::\$(?P<c2>[A-Z]+)\$(?P<r2>\d+))?"
)


def _clean_sheet(value: str) -> str:
    return value.strip().strip("'")


def parse_refers_to(name: str, scope: str, refers_to: str) -> Optional[DefinedRange]:
    if not isinstance(refers_to, str) or "#REF!" in refers_to or "!" not in refers_to:
        return None
    m = _RANGE_RE.search(refers_to)
    if not m:
        return None
    c1 = column_index_from_string(m.group("c1"))
    r1 = int(m.group("r1"))
    c2 = column_index_from_string(m.group("c2") or m.group("c1"))
    r2 = int(m.group("r2") or m.group("r1"))
    sheet = _clean_sheet(m.group("sheet"))
    return DefinedRange(name=name, scope=scope, sheet=sheet, start_row=r1, start_col=c1, end_row=r2, end_col=c2, refers_to=refers_to)


def load_defined_ranges() -> Dict[tuple[str, str], DefinedRange]:
    """Load workbook defined names keyed by (scope, name).

    Scope-specific names matter because the workbook reuses names such as
    Charge, Chassis, IndoorPartNum, etc. across Data_FE, Data_GE, Data_JE, etc.
    """
    ranges: Dict[tuple[str, str], DefinedRange] = {}
    if not DEFINED_NAMES_PATH.exists():
        return ranges
    df = pd.read_csv(DEFINED_NAMES_PATH, dtype=str).fillna("")
    for _, row in df.iterrows():
        parsed = parse_refers_to(row.get("name", ""), row.get("scope", ""), row.get("refers_to", ""))
        if parsed:
            ranges[(parsed.scope, parsed.name)] = parsed
    return ranges


def get_range_df(tables: Dict[str, pd.DataFrame], defined_ranges: Dict[tuple[str, str], DefinedRange], scope: str, name: str) -> pd.DataFrame:
    defined = defined_ranges.get((scope, name))
    if not defined:
        raise KeyError(f"Defined range not found: scope={scope}, name={name}")
    if defined.sheet not in tables:
        raise KeyError(f"Sheet CSV not loaded for defined range {scope}.{name}: {defined.sheet}")
    df = tables[defined.sheet]
    # Dataframes are zero-based; defined rows/cols are one-based.
    return df.iloc[defined.start_row - 1 : defined.end_row, defined.start_col - 1 : defined.end_col].copy()


def norm_key(value) -> str:
    if value is None:
        return ""
    text = str(value).strip()
    if text.endswith(".0"):
        try:
            return str(int(float(text)))
        except Exception:
            pass
    return text.upper()


def excel_lookup(lookup_value, range_df: pd.DataFrame, return_col: int, default: str = "n/a") -> str:
    """Approximate the workbook's NewLookup(value, range, return_col, False).

    It searches the first column of a defined range for an exact normalized match
    and returns the requested 1-based column from the matched row.
    """
    if range_df.empty or return_col < 1 or return_col > range_df.shape[1]:
        return default
    target = norm_key(lookup_value)
    first_col = range_df.iloc[:, 0].map(norm_key)
    matches = range_df[first_col == target]
    if matches.empty:
        return default
    value = matches.iloc[0, return_col - 1]
    if pd.isna(value):
        return ""
    return str(value).strip()


def to_float(value, default: float = 0.0) -> float:
    text = str(value).strip().replace("*", "")
    if not text or text.lower() == "n/a":
        return default
    # For MOC/MRC values like 4.1/4.8, use the first numeric component for now.
    text = text.split("/")[0]
    try:
        return float(text)
    except ValueError:
        return default


def fmt_float(value, digits: int = 1) -> str:
    try:
        return f"{float(value):.{digits}f}"
    except Exception:
        return ""
