from __future__ import annotations

import re
from dataclasses import dataclass
from typing import Optional

from models.model_number import ModelNumber
from models.errors import ErrorResult
from .parser_rules import (
    LEGACY_FAMILY_PREFIXES,
    STANDARD_UNIT_RULES,
    VALID_38AX_BRAND_PACKAGING,
    VALID_38AX_COIL,
    VALID_38AX_CONTROLS,
    VALID_38AX_ELECTRICAL,
    VALID_38AX_REFRIGERANT,
    VALID_38AX_SENSOR,
    VALID_38AX_SERVICE,
    VALID_38AX_SPLIT_TYPE,
    VALID_38AX_VOLTAGE,
    VALID_BRAND_PACKAGING,
    VALID_COIL,
    VALID_CONTROLS,
    VALID_DESIGN,
    VALID_ELECTRICAL,
    VALID_FAN_DRIVE_OR_POISE,
    VALID_INTAKE_EXHAUST,
    VALID_REFRIGERANT_OR_SYSTEM,
    VALID_SENSOR,
    VALID_SERIES,
    VALID_SERVICE,
    VALID_VOLTAGE,
    VOLTAGE_CODE_TO_TEXT,
)


@dataclass(frozen=True)
class ParsedPosition:
    position: str
    label: str
    value: str
    field_name: Optional[str] = None


def _clean(raw_model_number: str) -> str:
    """Normalize user-entered model number like the Excel UI effectively does."""
    return re.sub(r"[\s\-_/]", "", (raw_model_number or "").strip().upper())


def _char(value: str, pos: int) -> str:
    """1-based character accessor used to mirror VBA Mid(model, pos, 1)."""
    return value[pos - 1] if 1 <= pos <= len(value) else ""


def _mid(value: str, start: int, length: int) -> str:
    """1-based substring helper used to mirror VBA Mid(model, start, length)."""
    return value[start - 1 : start - 1 + length]


def _require_in(errors: ErrorResult, value: str, allowed: set[str], code: str, message: str) -> None:
    if value not in allowed:
        errors.add(code, message)


def parse_model_number(raw_model_number: str) -> tuple[ModelNumber, ErrorResult]:
    """Python replacement for the first layer of VBA CheckModelNumber.

    This Step 4 parser now performs real positional decoding for:
    - Standard Carrier 18-character FE/GE/JE/QE style models
    - Standard 18-character 38AX split-system models

    It also detects legacy Bryant/ICP/special-order families and returns a clear
    warning instead of silently guessing their brand-specific rules.
    """
    errors = ErrorResult()
    value = _clean(raw_model_number)
    model = ModelNumber(model_number=value)

    if not value:
        errors.add("MODEL_EMPTY", "Model number is required.")
        return model, errors

    if value.startswith("38AX"):
        _parse_38ax_model(value, model, errors)
        return model, errors

    prefix4 = value[:4]
    prefix3 = value[:3]
    if prefix4 in LEGACY_FAMILY_PREFIXES or prefix3 in LEGACY_FAMILY_PREFIXES:
        _parse_legacy_family(value, model, errors)
        return model, errors

    _parse_standard_packaged_model(value, model, errors)
    return model, errors


def _parse_standard_packaged_model(value: str, model: ModelNumber, errors: ErrorResult) -> None:
    """Port of the FEStd positional parser used by FE/GE/JE/QE families.

    This corrects the Step 4 placeholder mapping to match the VBA module
    mFE_Std.bas:
      1-2 series, 3-4 tier, 5 heat, 6 refrigerant/system,
      7-8 size, 9 sensor, 10 indoor fan drive, 11 coil/RTPF,
      12 voltage, 13 design, 14 controls, 15 intake/exhaust,
      16 service/convenience outlet, 17 electrical/HACR/disconnect,
      18 packaging.
    """
    if len(value) != 18:
        errors.add("MODEL_LENGTH_INVALID", "Incorrect number of digits in unit model number - must be 18.")

    series = _mid(value, 1, 2)
    tier = _mid(value, 3, 2)
    heat = _char(value, 5)
    system = _char(value, 6)
    size_text = _mid(value, 7, 2)
    sensor = _char(value, 9)
    motor_drive_code = _char(value, 10)
    coil = _char(value, 11)
    voltage = _char(value, 12)
    design = _char(value, 13)
    controls = _char(value, 14)
    intake_exhaust = _char(value, 15)
    service = _char(value, 16)
    electrical = _char(value, 17)
    packaging = _char(value, 18)

    model.series = int(series) if series.isdigit() else 0
    model.gas = series == "48"
    model.is_50 = series == "50"
    model.model_string = _mid(value, 1, 4)
    model.chassis = model.model_string
    model.special_order_type = STANDARD_UNIT_RULES.get(tier).description if tier in STANDARD_UNIT_RULES else ""
    model.tier = tier
    model.heat = heat
    if not model.gas:
        if heat == "A":
            model.heat_level = 1
        elif heat == "B":
            model.heat_level = 2
        elif heat == "C":
            model.heat_level = 3
        elif heat in {"Q", "-"}:
            model.heat_level = 0
            if heat == "Q":
                model.heat_pump = True
        else:
            errors.add("POSITION_5_HEAT_INVALID", "Position 5: Bad Heat Type Specified for 50 Series - Must be -, Q, A, B or C.", severity="warning")
    else:
        # Gas heat levels are used by combustion-fan logic. This first pass
        # mirrors the common FEStd levels without porting every gas edge case.
        if heat in {"D", "G", "L", "S"}:
            model.heat_level = 1
        elif heat in {"E", "H", "R"}:
            model.heat_level = 2
        elif heat in {"F", "T"}:
            model.heat_level = 3
    model.refrigerant_option = system
    model.sensor_option = sensor
    model.design = design
    model.control_type_text = controls
    model.packaging = packaging or "0"
    model.intake = _option_index(intake_exhaust)
    model.exhaust = _option_index(intake_exhaust)
    model.coil_guard = _option_index(coil)
    model.rtpf = coil in VALID_COIL
    model.terminal_block = _option_index(electrical)
    model.voltage_index = _voltage_index(voltage)
    model.single_phase = voltage == "3"

    if series not in VALID_SERIES:
        errors.add("POSITION_1_2_SERIES_INVALID", "Position 1 and 2: Bad Series specified - must be 48 or 50.")

    if tier not in STANDARD_UNIT_RULES:
        errors.add("POSITION_3_4_UNIT_TYPE_INVALID", "Positions 3 and 4: Bad Unit Type specified - must be FE, GE, JE, or QE.")
    elif tier == "QE":
        model.heat_pump = True

    # Position 6 flags from VBA Position6_FEStd.
    if system in {"A"}:
        model.two_stage = False; model.reheat = False; model.mm = False
    elif system in {"B", "W"}:
        model.two_stage = False; model.reheat = True; model.mm = True
    elif system in {"F", "V"}:
        model.two_stage = False; model.reheat = False; model.mm = True
    elif system in {"M", "X"}:
        model.two_stage = True; model.reheat = False; model.mm = False
    elif system in {"N", "Y"}:
        model.two_stage = True; model.reheat = True; model.mm = True
    elif system in {"P", "Z"}:
        model.two_stage = True; model.reheat = False; model.mm = True
    elif system in {"T", "R"}:
        model.two_stage = False; model.three_stage = True; model.reheat = False; model.mm = False
    elif system in {"U", "S"}:
        model.two_stage = False; model.three_stage = True; model.reheat = True; model.mm = False
    else:
        errors.add("POSITION_6_REFRIGERANT_INVALID", "Position 6: Bad refrigerant system option specified - must be A, B, F, M, N, P, T, U, R, S, V, W.")

    if size_text.isdigit():
        model.size = int(size_text)
        if size_text in {"04", "05", "06"}:
            model.dual_comp = False
        elif size_text == "07":
            model.dual_comp = tier in {"GE", "QE"}
        elif size_text in {"08", "09", "11", "12", "14", "16"}:
            model.dual_comp = True
        else:
            errors.add("POSITION_7_8_SIZE_INVALID", "Positions 7 and 8: Bad size specified - 04, 05, 06, 07, 08, 09, 11, 12, 14 or 16.")
    else:
        errors.add("POSITION_7_8_SIZE_INVALID", "Positions 7 and 8: Bad size specified - 04, 05, 06, 07, 08, 09, 11, 12, 14 or 16.")

    # Position 10 maps many visual choices into fan drive level 1/2/3.
    if motor_drive_code in {"1", "4", "D", "G"}:
        model.motor_drive = "1"
    elif motor_drive_code in {"2", "5", "E", "H", "K"}:
        model.motor_drive = "2"
    elif motor_drive_code in {"3", "6", "F", "J", "L"}:
        model.motor_drive = "3"
    else:
        errors.add("POSITION_10_FAN_DRIVE_INVALID", "Position 10: Bad Indoor Fan Drive/Poise Specified - must be 1 - 6, or D, E, F, G, H, J.")

    if sensor not in VALID_SENSOR:
        errors.add("POSITION_9_SENSOR_INVALID", "Position 9: Bad sensor option specified - must be A, B, C, D, E, F, G, H, J, K, L, M, N, P, Q or R.")
    if coil not in VALID_COIL:
        errors.add("POSITION_11_COIL_INVALID", "Position 11: Bad Coil Type Specified - must be A, B, C, D, E, F, M, N, P, Q, R or S.")
    if voltage not in VALID_VOLTAGE:
        errors.add("POSITION_12_VOLTAGE_INVALID", "Position 12: Bad Voltage Specified - must be 1, 3, 5, 6 or 9.")
    if design not in {"A", "B"}:
        errors.add("POSITION_13_DESIGN_INVALID", "Position 13: Bad Design Variation Specified - must be A.")

    if controls in {"0", "8"}:
        model.mech_ctrl = True
    elif controls == "S":
        model.seven_eleven = True
    elif controls not in {"3", "5", "T"}:
        errors.add("POSITION_14_CONTROLS_INVALID", "Position 14: Bad base unit controls specified - must be 0 - 8, A, S or X.")

    if intake_exhaust in {"1", "2", "3", "4"}:
        model.econ_erv = intake_exhaust in {"2", "4"}
        model.econ = model.econ_erv
        model.erv = 1
    elif intake_exhaust == "A":
        model.pe = False
    elif intake_exhaust in {"B", "F", "U", "W", "L", "M"}:
        model.econ = True
    elif intake_exhaust in {"N", "P", "V", "X"}:
        model.econ = True; model.pe = True
    else:
        errors.add("POSITION_15_INTAKE_EXHAUST_INVALID", "Position 15: Bad intake/exhaust option specified - must be A, B, F, L, M, N, P, U, V, W, X, or 1-4.")

    if service in {"2", "5", "8", "B", "E", "H", "L", "P"}:
        model.conv_outlet = 1; model.co = True
    elif service in {"0", "1", "3", "4", "6", "7", "9", "A", "C", "D", "F", "G", "J", "K", "M", "N"}:
        model.conv_outlet = 0; model.co = False
    else:
        errors.add("POSITION_16_SERVICE_INVALID", "Position 16: Bad service option specified - must be 0-9 or A-P.")

    if electrical in {"A", "D", "N", "R"}:
        model.hacr = False; model.disc = False
    elif electrical in {"C", "F", "Q", "T"}:
        model.hacr = False; model.disc = True
    elif electrical in {"B", "E", "P", "S"}:
        model.hacr = tier in {"GE", "JE", "QE"}; model.disc = False
        if tier == "FE":
            errors.add("POSITION_17_ELECTRICAL_INVALID", "Position 17: Bad electrical option specified - B or E not available for FE.")
    elif electrical in {"1", "2"}:
        model.hacr = False; model.disc = False; model.hsccr = True
    else:
        errors.add("POSITION_17_ELECTRICAL_INVALID", "Position 17: Bad electrical option specified - must be A - F, or P - T., or 1-2.")

    if packaging not in VALID_BRAND_PACKAGING:
        errors.add("POSITION_18_BRAND_INVALID", "Position 18: Bad brand/packaging specified - must be 0 - 4 or Z.")

def _parse_38ax_model(value: str, model: ModelNumber, errors: ErrorResult) -> None:
    if len(value) != 18:
        errors.add(
            "MODEL_LENGTH_INVALID",
            "Incorrect number of digits in unit model number - must be 18.",
        )

    model.series = 38
    model.model_string = "38AX"
    model.chassis = "38AX"
    model.cdu = True
    model.gas = False
    model.is_50 = False
    model.special_order_type = "Standard 38AX split-system unit"

    if _mid(value, 1, 4) != "38AX":
        errors.add("POSITION_1_4_38AX_INVALID", "Position 1-4: Bad Series specified - must be 38AX.")

    split_type = _char(value, 5)
    refrigerant = _char(value, 6)
    size_text = _mid(value, 7, 2)
    sensor = _char(value, 9)
    coil = _char(value, 10)
    voltage = _char(value, 11)
    design = _char(value, 12)
    controls = _char(value, 13)
    service = _char(value, 14)
    electrical = _char(value, 15)
    brand = _char(value, 16)
    packaging = _char(value, 17)

    model.refrigerant_option = refrigerant
    model.sensor_option = sensor
    model.coil_guard = _option_index(coil)
    model.voltage_index = _voltage_index(voltage)
    model.design = design
    model.control_type_text = controls
    model.packaging = packaging or "0"
    model.single_phase = voltage == "3"

    if size_text.isdigit():
        model.size = int(size_text)
    else:
        errors.add("POSITION_7_8_SIZE_INVALID", "Bad size specified in positions 7 and 8.")

    _require_in(errors, split_type, VALID_38AX_SPLIT_TYPE, "POSITION_5_SPLIT_TYPE_INVALID", "Bad Split Type Specified must be D, Q or Z.")
    _require_in(errors, refrigerant, VALID_38AX_REFRIGERANT, "POSITION_6_REFRIGERANT_INVALID", "Bad refrigerant system option specified - must be M, N, T, U, or E.")
    _require_in(errors, sensor, VALID_38AX_SENSOR, "POSITION_9_SENSOR_INVALID", "Bad sensor option specified - must be A or E.")
    _require_in(errors, coil, VALID_38AX_COIL, "POSITION_10_COIL_INVALID", "Bad Coil Type Specified - must be A, B, C, E, G, K, M, N, P, R, T or W.")
    _require_in(errors, voltage, VALID_38AX_VOLTAGE, "POSITION_11_VOLTAGE_INVALID", "Bad Voltage Specified - must be 1, 5, 6 or 9.")
    _require_in(errors, design, VALID_DESIGN, "POSITION_12_DESIGN_INVALID", "Bad Design Variation Specified - must be A.")
    _require_in(errors, controls, VALID_38AX_CONTROLS, "POSITION_13_CONTROLS_INVALID", "Bad base unit controls specified - must be 0, 1, 2, 3 or S.")
    _require_in(errors, service, VALID_38AX_SERVICE, "POSITION_14_SERVICE_INVALID", "Bad service option specified - must be 0-2.")
    _require_in(errors, electrical, VALID_38AX_ELECTRICAL, "POSITION_15_ELECTRICAL_INVALID", "Bad electrical option specified - must be A, or C.")
    _require_in(errors, brand, VALID_38AX_BRAND_PACKAGING, "POSITION_16_BRAND_INVALID", "Bad brand/packaging specified - must be 0, 1 or 2.")


def _parse_legacy_family(value: str, model: ModelNumber, errors: ErrorResult) -> None:
    model.model_string = value[:4]
    model.chassis = value[:4]
    if value[:2].isdigit():
        model.series = int(value[:2])
        model.gas = value[:2] == "48"
        model.is_50 = value[:2] == "50"

    errors.add(
        "LEGACY_FAMILY_NOT_PORTED",
        "This model family exists in the VBA workbook, but its Bryant/ICP/special-order parser branch has not been ported yet.",
        severity="warning",
    )


def _voltage_index(code: str) -> int:
    return int(code) if str(code).isdigit() else 0


def _option_index(code: str) -> int:
    if not code:
        return 0
    if code.isdigit():
        return int(code)
    return ord(code) - ord("A") + 10


def get_voltage_text(model: ModelNumber) -> str:
    voltage_pos = 11 if model.cdu or model.model_string == "38AX" else 12
    return VOLTAGE_CODE_TO_TEXT.get(_char(model.model_number, voltage_pos), "")
