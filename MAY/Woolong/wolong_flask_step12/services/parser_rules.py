"""Model-number parsing rules for the first VBA-to-Python migration pass.

These rules are based on the VBA procedure names and validation strings exposed in
`vbaProject.bin`, especially:
- CheckModelNumber
- CheckModelNumber_FEStd / GEStd / JEStd / QEStd
- CheckModelNumber_38AXStd
- Position*_FEStd and Position*_38AXStd

The goal of Step 4 is to replace the skeleton parser with a maintainable,
position-by-position decoder.  Some legacy Bryant/ICP/special-order branches are
intentionally marked as not-yet-ported rather than guessed silently.
"""

from dataclasses import dataclass
from typing import Optional


@dataclass(frozen=True)
class StandardModelRule:
    code: str
    description: str
    data_sheet: str
    gas_sheet: Optional[str] = None


STANDARD_UNIT_RULES: dict[str, StandardModelRule] = {
    "FE": StandardModelRule("FE", "Standard FE packaged rooftop unit", "Data_FE", "Data_GasFE"),
    "GE": StandardModelRule("GE", "Standard GE packaged rooftop unit", "Data_GE", "Data_GasGE"),
    "JE": StandardModelRule("JE", "Standard JE packaged rooftop unit", "Data_JE", "Data_GasJE"),
    "QE": StandardModelRule("QE", "Standard QE/Fusion packaged rooftop unit", "Data_FE", "Data_GasFE"),
}

# Legacy families from the VBA dispatch message.  These are valid workbook
# families but their brand-specific position functions have not been ported yet.
LEGACY_FAMILY_PREFIXES = {
    "582L", "559L", "547L", "551L", "581L", "549L", "549Q",
    "RGF", "RAF", "RHF", "RGG", "RAG", "RHG", "RDG",
    "569L", "575L", "569J", "575J", "CAL", "CHL",
}

# FE/GE/JE/QE validation strings visible in the VBA project.  These are purposely
# kept permissive enough for the workbook's common 18-character Carrier-format
# models, while still catching obvious wrong input.
VALID_SERIES = {"48", "50"}
VALID_REFRIGERANT_OR_SYSTEM = set("ABFMNPTURSVW")
VALID_SENSOR = set("ABCDEFGHJKLMNPQR")
VALID_FAN_DRIVE_OR_POISE = set("123456DEFGHJ")
VALID_COIL = set("ABCDEFMNPQRS")
VALID_VOLTAGE = set("13569")
VALID_DESIGN = {"A"}
VALID_CONTROLS = set("012345678ASX")
VALID_INTAKE_EXHAUST = set("ABCDFGKLMNPQRSTUVWX123467")
VALID_SERVICE = set("0123456789ABCDEFGHIJKLMNOP")
VALID_ELECTRICAL = set("ABCDEFPQRST12")
VALID_BRAND_PACKAGING = set("01234Z")

# 38AX validation strings visible in the VBA project.
VALID_38AX_SPLIT_TYPE = set("DQZ")
VALID_38AX_REFRIGERANT = set("MNTUE")
VALID_38AX_SENSOR = set("AE")
VALID_38AX_COIL = set("ABCEGKMNPRTW")
VALID_38AX_VOLTAGE = set("1569")
VALID_38AX_CONTROLS = set("0123S")
VALID_38AX_SERVICE = set("012")
VALID_38AX_ELECTRICAL = set("AC")
VALID_38AX_BRAND_PACKAGING = set("012")

VOLTAGE_CODE_TO_TEXT = {
    "1": "575-3-60",
    "3": "208/230-1-60",
    "5": "208/230-3-60",
    "6": "460-3-60",
    "9": "380-3-60",
}

# Known 50 Hz / Bryant / ICP voltage letters from VBA messages.  Kept for routing,
# not yet mapped to full electrical calculations.
LETTER_VOLTAGE_CODE_TO_TEXT = {
    "T": "575-3-60 / legacy Bryant code",
    "J": "208/230-1-60 / legacy Bryant code",
    "P": "208/230-3-60 / legacy Bryant code",
    "E": "460-3-60 / legacy Bryant code",
    "S": "575-3-60 / ICP code",
    "K": "208/230-1-60 / ICP code",
    "H": "208/230-3-60 / ICP code",
    "L": "460-3-60 / ICP code",
    "Z": "380-3-60 / ICP code",
}
