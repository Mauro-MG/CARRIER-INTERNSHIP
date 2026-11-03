from __future__ import annotations

from dataclasses import dataclass, replace
from typing import List, Optional

from models.model_number import ModelNumber
from models.electrical import ElectricalResult, MotorLoad
from .data_loader import load_lookup_tables
from .workbook_ranges import excel_lookup, get_range_df, load_defined_ranges, to_float
from .electrical_data import (
    _model_scope,
    _clean_motor_value,
    _electric_heat_part_range_names,
    _choose_electric_heat_data_range,
)


@dataclass
class OptionalAccessoryScenario:
    """A workbook AccRow-style optional accessory scenario.

    The Excel macro writes optional rows into AccRow1..AccRowN, then temporarily
    swaps those loads into Motor3/Motor4 before calling GetMCAMOCP/GetMCAMOCP50.
    In Python we keep the same idea as a named scenario with one or more motors.
    """
    name: str
    motors: List[MotorLoad]
    source: str = ""


def heat_level_offset(model: ModelNumber) -> int:
    """Return the number of optional electric heat rows to generate.

    VBA normally reads Info_Plate!iHeatLevelOffset. The extracted workbook uses
    that as a UI variable; for the migration MVP, 3 is the safe default. The VBA
    has a specific GE/M06/voltage-5 override to 7, so we preserve that branch.
    """
    if model.model_string.endswith("GE") and model.size == 5 and model.voltage_index == 5:
        return 7
    return 3


def make_power_exhaust_motor(model: ModelNumber, electrical: ElectricalResult) -> Optional[MotorLoad]:
    """Create the optional Power Exhaust Motor4 row used by AccRow logic."""
    tables = load_lookup_tables()
    ranges = load_defined_ranges()
    scope = _model_scope(model)
    suffix = "7_11" if model.seven_eleven else ""
    try:
        voltage_range = get_range_df(tables, ranges, scope, f"PwrExhVoltageData{suffix}")
        fla_range = get_range_df(tables, ranges, scope, f"PwrExhFLAData{suffix}")
        lra_range = get_range_df(tables, ranges, scope, f"PwrExhLRAData{suffix}")
    except Exception:
        return None

    chassis = electrical.chassis or model.chassis
    voltage = excel_lookup(model.voltage_index, voltage_range, 2, default="")
    phase = excel_lookup(model.voltage_index, voltage_range, 3, default="")
    hz = excel_lookup(model.voltage_index, voltage_range, 4, default="")
    qty_raw = excel_lookup(chassis, fla_range, 2, default="")
    fla_raw = excel_lookup(chassis, fla_range, model.voltage_index + 2, default="")
    lra_raw = excel_lookup(chassis, lra_range, model.voltage_index + 2, default="")
    if not voltage or not phase or not hz or not qty_raw or not fla_raw or not lra_raw:
        return None

    return MotorLoad(
        name=f"Optional Power Exhaust ({voltage}V/{phase}ph/{hz}Hz)",
        fla=f"*{_clean_motor_value(fla_raw, decimals=1)}*",
        lra=_clean_motor_value(lra_raw, decimals=0),
        hp=None,
        quantity=int(to_float(qty_raw, 1) or 1),
        source_range=f"{scope}.PwrExhFLAData/OptionalAccRow/Motor4",
        duty="both",
    )


def make_optional_electric_heat_motor(model: ModelNumber, electrical: ElectricalResult, level: int) -> Optional[MotorLoad]:
    """Create an optional electric heat Motor3 row for a candidate heat level."""
    if model.gas or not (model.series == 50 or model.is_50):
        return None

    tables = load_lookup_tables()
    ranges = load_defined_ranges()
    scope = _model_scope(model)
    temp_model = replace(model, heat_level=level, chassis=electrical.chassis or model.chassis)

    part_number = "n/a"
    used_range = ""
    for range_name in _electric_heat_part_range_names(temp_model):
        try:
            part_range = get_range_df(tables, ranges, scope, range_name)
        except Exception:
            continue
        candidate = excel_lookup(model.size, part_range, model.voltage_index + 1, default="n/a")
        if candidate and str(candidate).lower() != "n/a":
            part_number = candidate
            used_range = f"{scope}.{range_name}"
            break
    if not part_number or str(part_number).lower() == "n/a":
        return None

    data_range_name = _choose_electric_heat_data_range(model)
    try:
        heat_data = get_range_df(tables, ranges, "Data_Common", data_range_name)
    except Exception:
        return None

    qty_raw = excel_lookup(part_number, heat_data, 9, default="")
    if str(qty_raw).strip().startswith("=") or not str(qty_raw).strip():
        qty_raw = "1"
    fla_raw = excel_lookup(part_number, heat_data, 6, default="")
    lra_raw = excel_lookup(part_number, heat_data, 6, default="")
    kw_raw = excel_lookup(part_number, heat_data, 5, default="")
    if model.hsccr:
        num_wires = excel_lookup(part_number, heat_data, 16, default="")
        actual_wires = excel_lookup(part_number, heat_data, 17, default="")
    else:
        num_wires = excel_lookup(part_number, heat_data, 10, default="")
        actual_wires = excel_lookup(part_number, heat_data, 11, default="")
    if not fla_raw or not kw_raw:
        return None

    return MotorLoad(
        name=f"Optional Electric Heat L{level} - {part_number}",
        fla=fla_raw,
        lra=lra_raw,
        hp=None,
        quantity=qty_raw or 1,
        source_range=f"{used_range}/{data_range_name}/OptionalAccRow/Motor3",
        duty="both" if model.heat_pump else "heat",
        kw=kw_raw,
        part_number=part_number,
        num_wires=num_wires,
        actual_num_wires=actual_wires,
    )


def build_optional_accessory_scenarios(model: ModelNumber, electrical: ElectricalResult) -> List[OptionalAccessoryScenario]:
    """Build optional AccRow scenarios that are not already active in the model.

    This ports the next useful slice of the workbook's accessory section:
    - optional power exhaust by itself when PE/ERV is not already selected;
    - optional electric heat rows when a 50-series unit has no selected heat;
    - optional PE + electric heat combinations for the no-heat/no-PE case.
    """
    scenarios: List[OptionalAccessoryScenario] = []
    has_active_pe_or_erv = bool(model.pe) or int(model.erv or 0) != 0
    has_active_heat = (model.series == 50 or model.is_50) and model.heat_level > 0

    optional_pe = None if has_active_pe_or_erv else make_power_exhaust_motor(model, electrical)
    if optional_pe is not None and not (model.series == 50 or model.is_50):
        scenarios.append(OptionalAccessoryScenario("Optional Power Exhaust", [optional_pe], optional_pe.source_range))

    if model.gas or not (model.series == 50 or model.is_50) or has_active_heat:
        return scenarios

    heat_motors: List[MotorLoad] = []
    for level in range(1, heat_level_offset(model) + 1):
        heat = make_optional_electric_heat_motor(model, electrical, level)
        if heat is None:
            continue
        heat_motors.append(heat)
        scenarios.append(OptionalAccessoryScenario(f"Optional Electric Heat L{level}", [heat], heat.source_range))

    # VBA also builds paired PE + electric heat rows when neither option is active.
    if optional_pe is not None and not has_active_pe_or_erv:
        for heat in heat_motors:
            scenarios.append(OptionalAccessoryScenario(
                f"Optional Power Exhaust + {heat.name.replace('Optional ', '')}",
                [optional_pe, heat],
                f"{optional_pe.source_range} + {heat.source_range}",
            ))

    return scenarios
