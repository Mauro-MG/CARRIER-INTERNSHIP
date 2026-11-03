from __future__ import annotations

from typing import Dict, Optional, Any

import pandas as pd

from models.model_number import ModelNumber
from models.electrical import ElectricalResult, CompressorLoad, MotorLoad
from models.errors import ErrorResult
from .model_parser import get_voltage_text
from .workbook_ranges import (
    excel_lookup,
    fmt_float,
    get_range_df,
    load_defined_ranges,
    to_float,
)


VOLTAGE_INFO = {
    "1": {"voltage": "575", "phase": "3", "hz": "60", "max": "633", "min": "518"},
    "3": {"voltage": "208/230", "phase": "1", "hz": "60", "max": "253", "min": "197"},
    "5": {"voltage": "208/230", "phase": "3", "hz": "60", "max": "253", "min": "187"},
    "6": {"voltage": "460", "phase": "3", "hz": "60", "max": "506", "min": "414"},
    "7": {"voltage": "460", "phase": "1", "hz": "60", "max": "506", "min": "414"},
    "9": {"voltage": "400", "phase": "3", "hz": "50", "max": "440", "min": "360"},
}


def _model_scope(model: ModelNumber) -> str:
    if model.cdu or model.model_string == "38AX":
        return "Data_38AX"
    if model.tier == "GE" or model.model_string.endswith("GE"):
        return "Data_GE"
    if model.tier == "JE" or model.model_string.endswith("JE"):
        return "Data_JE"
    # QE currently shares FE-style parsing, but no Data_QE sheet exists in the
    # workbook extraction. Until the QE-specific route is proven, use Data_FE.
    return "Data_FE"


def _voltage_final(model: ModelNumber) -> tuple[int, bool]:
    if model.voltage_index == 9:
        return 6, True
    return model.voltage_index, False


def _bool_digit(flag: bool) -> str:
    return "1" if flag else "0"


def _lookup_defined(tables, ranges, scope: str, name: str, key, col: int, default: str = "n/a") -> str:
    try:
        rng = get_range_df(tables, ranges, scope, name)
    except Exception:
        return default
    return excel_lookup(key, rng, col, default=default)


def _choose_comp_range_name(model: ModelNumber) -> str:
    voltage_final, _ = _voltage_final(model)
    # Mirrors VBA WriteCompressors: CompPartNum + Digital + HP + DC + TS + Vx
    digital = "Digital" if getattr(model, "digital", False) else ""
    hp = "HP" if model.heat_pump else ""
    dc = "DC" if model.dual_circ else ""
    ts = "TS" if model.two_stage or model.three_stage else ""
    return f"CompPartNum{digital}{hp}{dc}{ts}V{voltage_final}"


def _add_compressors(result: ElectricalResult, errors: ErrorResult, model: ModelNumber, tables, ranges, scope: str) -> None:
    range_name = _choose_comp_range_name(model)
    comp_data = None
    part_range = None
    try:
        part_range = get_range_df(tables, ranges, scope, range_name)
        comp_data = get_range_df(tables, ranges, "Data_Common", "CompData")
    except Exception as exc:
        errors.add("COMP_LOOKUP_RANGE_MISSING", f"Compressor lookup range missing: {scope}.{range_name} ({exc})", severity="warning")
        result.notes.append(f"Compressor lookup skipped; missing range {scope}.{range_name}.")
        return

    _, is_voltage_9 = _voltage_final(model)
    for i in range(1, 4):
        part_number = excel_lookup(model.size, part_range, i + 1)
        if not part_number or part_number.lower() == "n/a":
            continue
        lookup_part = f"{part_number}-50" if is_voltage_9 else part_number
        rla_raw = excel_lookup(lookup_part, comp_data, 5, default="")
        lra_raw = excel_lookup(lookup_part, comp_data, 6, default="")
        rla = to_float(rla_raw)
        lra = to_float(lra_raw)
        result.compressors.append(
            CompressorLoad(
                name=lookup_part,
                rla=rla,
                lra=lra,
                quantity=1,
                source_range=f"{scope}.{range_name}:Comp{i}",
            )
        )
        if rla == 0 or lra == 0:
            errors.add("COMP_DATA_INCOMPLETE", f"Compressor data is not completely specified for {lookup_part}.", severity="warning")

    if not result.compressors:
        result.notes.append(f"No compressor part numbers found for size {model.size} in {scope}.{range_name}.")


def _add_chassis(result: ElectricalResult, errors: ErrorResult, model: ModelNumber, tables, ranges, scope: str) -> None:
    if model.cdu:
        result.chassis = "CDU"
        return
    suffix = "HP" if model.heat_pump else "DC" if model.dual_circ else ""
    range_name = "Chassis" + suffix
    chassis = _lookup_defined(tables, ranges, scope, range_name, model.size, 2, default="")
    if chassis:
        result.chassis = chassis
        model.chassis = chassis
    else:
        errors.add("CHASSIS_LOOKUP_MISSING", f"Chassis not found for size {model.size} in {scope}.{range_name}.", severity="warning")


def _add_charge(result: ElectricalResult, errors: ErrorResult, model: ModelNumber, tables, ranges, scope: str) -> None:
    # VBA WriteCharge key:
    # normal: size + dualcirc + rtpf + reheat + b50 + heatpump + twostage
    # GE additionally appends three_stage.
    _, b50 = _voltage_final(model)
    key = (
        f"{model.size}"
        f"{_bool_digit(model.dual_circ)}"
        f"{_bool_digit(model.rtpf)}"
        f"{_bool_digit(model.reheat)}"
        f"{_bool_digit(b50)}"
        f"{_bool_digit(model.heat_pump)}"
        f"{_bool_digit(model.two_stage)}"
    )
    if scope == "Data_GE":
        key += _bool_digit(model.three_stage)
    try:
        charge_range = get_range_df(tables, ranges, scope, "Charge")
    except Exception as exc:
        errors.add("CHARGE_RANGE_MISSING", f"Charge lookup range missing for {scope}: {exc}", severity="warning")
        return

    pairs = []
    for i in range(1, 4):
        lbm_raw = excel_lookup(key, charge_range, i + 1, default="n/a")
        if not lbm_raw or lbm_raw.lower() == "n/a":
            continue
        kg = to_float(lbm_raw) / 2.204622622 if to_float(lbm_raw) else 0
        pairs.append(f"Circuit {i}: {lbm_raw} lbm / {kg:.2f} kg")
    if pairs:
        result.charge = "; ".join(pairs)
    else:
        errors.add("CHARGE_NOT_FOUND", f"Please enter charge data for this unit - lookup key {key} in {scope}.Charge.", severity="warning")


def _add_indoor_fan(result: ElectricalResult, errors: ErrorResult, model: ModelNumber, tables, ranges, scope: str) -> None:
    if model.cdu:
        return
    key = f"{model.series}{model.voltage_index}{model.size}{model.motor_drive}"
    try:
        part_range = get_range_df(tables, ranges, scope, "IndoorPartNum")
        fla_range = get_range_df(tables, ranges, scope, "IndoorDataNoHACR")
        lra_range = get_range_df(tables, ranges, scope, "IndoorLRAData")
        phase_range = get_range_df(tables, ranges, scope, "IndoorPhaseData")
        voltage_range = get_range_df(tables, ranges, scope, "IndoorVoltageData")
        bhp_range = get_range_df(tables, ranges, scope, "IndoorMotorBHP")
    except Exception as exc:
        errors.add("INDOOR_RANGE_MISSING", f"Indoor fan lookup range missing for {scope}: {exc}", severity="warning")
        return

    return_col = 4 if model.heat_pump else 3 if model.dual_circ else 2
    part_number = excel_lookup(key, part_range, return_col, default="n/a")
    if not part_number or part_number.lower() == "n/a":
        errors.add("INDOOR_PART_NOT_FOUND", f"Invalid indoor fan motor option. Lookup key {key} in {scope}.IndoorPartNum.", severity="warning")
        return

    voltage_idx = excel_lookup(part_number, voltage_range, model.voltage_index + 2, default=str(model.voltage_index))
    voltage = VOLTAGE_INFO.get(str(voltage_idx), VOLTAGE_INFO.get(str(model.voltage_index), {}))
    fla_raw = excel_lookup(part_number, fla_range, model.voltage_index + 2, default="")
    lra_raw = excel_lookup(part_number, lra_range, model.voltage_index + 2, default="")
    phase = excel_lookup(part_number, phase_range, model.voltage_index + 2, default=voltage.get("phase", ""))
    bhp_raw = excel_lookup(part_number, bhp_range, 2, default="")

    result.motors.append(
        MotorLoad(
            name=f"Indoor Fan - {part_number} ({voltage.get('voltage','')}V/{phase}ph/{voltage.get('hz','')}Hz)",
            fla=to_float(fla_raw),
            lra=to_float(lra_raw),
            hp=to_float(bhp_raw) if bhp_raw else None,
            quantity=1,
            source_range=f"{scope}.IndoorPartNum/Motor1",
            duty="both",
        )
    )


def _outdoor_suffix(model: ModelNumber) -> str:
    if model.heat_pump:
        return "HP"
    if model.mm or model.reheat:
        return "Reheat"
    return "NoReheat"


def _add_outdoor_fan(result: ElectricalResult, errors: ErrorResult, model: ModelNumber, tables, ranges, scope: str) -> None:
    suffix = _outdoor_suffix(model)
    if model.three_stage and scope == "Data_GE":
        suffix = "3Stg" if not model.heat_pump else "HP3Stg"
    try:
        fla_range = get_range_df(tables, ranges, scope, f"OutdoorFLAData{suffix}")
        lra_range = get_range_df(tables, ranges, scope, f"OutdoorLRAData{suffix}")
        phase_range = get_range_df(tables, ranges, scope, f"OutdoorPhaseData{suffix}")
        bhp_range_name = "OutdoorMotorBHP3Stg" if model.three_stage and scope == "Data_GE" else "OutdoorMotorBHP"
        bhp_range = get_range_df(tables, ranges, scope, bhp_range_name)
    except Exception as exc:
        errors.add("OUTDOOR_RANGE_MISSING", f"Outdoor fan lookup range missing for {scope} suffix {suffix}: {exc}", severity="warning")
        return

    qty_raw = excel_lookup(model.size, fla_range, 2, default="")
    fla_raw = excel_lookup(model.size, fla_range, model.voltage_index + 2, default="")
    lra_raw = excel_lookup(model.size, lra_range, model.voltage_index + 2, default="")
    phase = excel_lookup(model.size, phase_range, 2, default="")
    bhp_col = 4 if model.heat_pump else 3 if model.reheat or model.mm else 2
    bhp_raw = excel_lookup(model.size, bhp_range, bhp_col, default="")
    voltage = VOLTAGE_INFO.get(str(model.voltage_index), {})
    qty = int(to_float(qty_raw, 1) or 1)

    result.motors.append(
        MotorLoad(
            name=f"Outdoor Fan ({voltage.get('voltage','')}V/{phase}ph/{voltage.get('hz','')}Hz)",
            fla=to_float(fla_raw),
            lra=to_float(lra_raw),
            hp=to_float(bhp_raw) if bhp_raw else None,
            quantity=qty,
            source_range=f"{scope}.Outdoor*{suffix}/Motor2",
            duty="cool",
        )
    )


def _choose_electric_heat_data_range(model: ModelNumber) -> str:
    """Mirror WriteCombustionFan electric-heat data table selection."""
    if model.voltage_index == 3:
        return "ElecHeatDataSinglePhase"
    if model.voltage_index == 9:
        return "ElecHeatData50"
    return "ElecHeatDataThreePhase"


def _electric_heat_part_range_names(model: ModelNumber) -> list[str]:
    """Candidate range names used by VBA WriteCombustionFan.

    For the main nameplate, nHeatLevel is the selected level. Some sheets use
    Fiop ranges; older/default flows use L ranges. We try the exact likely names
    in the same order a migration/debugger would inspect them.
    """
    if model.heat_level <= 0:
        return []
    direct = "DD" if model.direct_drive else ""
    chassis_suffix = "5" if str(model.chassis) == "5" else ""
    level = model.heat_level
    return [
        f"ElecHeatPartNumFiop{level}{direct}{chassis_suffix}",
        f"ElecHeatPartNumL{level}{direct}{chassis_suffix}",
        f"ElecHeatPartNumFiop{level}",
        f"ElecHeatPartNumL{level}",
    ]


def _add_electric_heat(result: ElectricalResult, errors: ErrorResult, model: ModelNumber, tables, ranges, scope: str) -> None:
    """Port the useful electric-heat slice of VBA WriteCombustionFan.

    VBA writes electric heat into Motor3 with:
      Motor(4)=Qty, Motor(5)=FLA, Motor(6)=LRA, Motor(7)=kW,
      plus NumofWires/ActNumofWires from ElecHeatData*.
    """
    if model.gas or not (model.series == 50 or model.is_50) or model.heat_level <= 0:
        return

    part_number = "n/a"
    used_range = ""
    for range_name in _electric_heat_part_range_names(model):
        try:
            part_range = get_range_df(tables, ranges, scope, range_name)
        except Exception:
            continue
        candidate = excel_lookup(model.size, part_range, model.voltage_index + 1, default="n/a")
        if candidate and candidate.lower() != "n/a":
            part_number = candidate
            used_range = f"{scope}.{range_name}"
            break

    if not part_number or part_number.lower() == "n/a":
        errors.add(
            "ELEC_HEAT_PART_NOT_FOUND",
            f"Electric heat part number not found for size {model.size}, voltage index {model.voltage_index}, heat level {model.heat_level}.",
            severity="warning",
        )
        return

    data_range_name = _choose_electric_heat_data_range(model)
    try:
        heat_data = get_range_df(tables, ranges, "Data_Common", data_range_name)
    except Exception as exc:
        errors.add("ELEC_HEAT_DATA_RANGE_MISSING", f"Missing Data_Common.{data_range_name}: {exc}", severity="warning")
        return

    qty_raw = excel_lookup(part_number, heat_data, 9, default="")
    if str(qty_raw).strip().startswith("=") or not str(qty_raw).strip():
        # The extracted CSV contains unevaluated formulas such as "=" in some
        # quantity cells. The VBA sees the cached Excel value; for Motor3 heat
        # this is effectively one heater package.
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

    if not qty_raw or not fla_raw or not kw_raw:
        errors.add("ELEC_HEAT_DATA_INCOMPLETE", f"Electric heat is not fully specified for {part_number}.", severity="warning")

    duty = "both" if model.heat_pump else "heat"
    result.motors.append(
        MotorLoad(
            name=f"Electric Heat - {part_number}",
            fla=fla_raw,
            lra=lra_raw,
            hp=None,
            quantity=qty_raw or 1,
            source_range=f"{used_range}/{data_range_name}/Motor3",
            duty=duty,
            kw=kw_raw,
            part_number=part_number,
            num_wires=num_wires,
            actual_num_wires=actual_wires,
        )
    )
    result.notes.append(
        f"Electric heat: part {part_number}, kW {kw_raw}, FLA {fla_raw}, wires {num_wires}/{actual_wires}."
    )


def _clean_motor_value(value: Any, *, decimals: int | None = None) -> Any:
    """Normalize workbook lookup values while preserving slash strings when needed."""
    text = str(value or "").strip()
    if not text or text.lower() in {"n/a", "nan"}:
        return ""
    if text.startswith("=1000/"):
        try:
            denominator = float(text.split("/", 1)[1])
            value = 1000.0 / denominator if denominator else 0.0
            return f"{value:.{decimals or 1}f}" if decimals is not None else str(value)
        except Exception:
            return ""
    if text.startswith("="):
        return ""
    if decimals is None or "/" in text:
        return text
    try:
        return f"{float(text):.{decimals}f}"
    except Exception:
        return text


def _make_motor_from_data_range(
    *,
    name: str,
    source_range: str,
    voltage_index: int,
    data_range: pd.DataFrame,
    duty: str = "both",
    starred_fla: bool = False,
) -> MotorLoad | None:
    """Build Motor4/Motor6/Motor7 style loads from a VBA DataRange.

    The VBA layout is consistent for OutletData and ERV* ranges:
    lookup key = voltage index, columns 2-5 = voltage/phase/hz/qty,
    column 6 = FLA, column 7 = LRA.
    """
    voltage = excel_lookup(voltage_index, data_range, 2, default="")
    phase = excel_lookup(voltage_index, data_range, 3, default="")
    hertz = excel_lookup(voltage_index, data_range, 4, default="")
    qty_raw = excel_lookup(voltage_index, data_range, 5, default="")
    fla_raw = excel_lookup(voltage_index, data_range, 6, default="")
    lra_raw = excel_lookup(voltage_index, data_range, 7, default="")
    qty = to_float(qty_raw, 0)
    fla = _clean_motor_value(fla_raw, decimals=1)
    lra = _clean_motor_value(lra_raw, decimals=0)
    if not lra and str(lra_raw or "").strip().upper().startswith("=AI"):
        # Extracted CSV stores the cached LRA as an Excel reference; use FLA as
        # a conservative fallback until formula-cache extraction is added.
        lra = _clean_motor_value(fla_raw, decimals=0)
    if not voltage or not phase or not hertz or not qty or not fla or not lra:
        return None
    hp = None
    try:
        hp = float(str(lra).replace("*", "")) * 0.746
    except Exception:
        hp = None
    fla_value: Any = f"*{fla}*" if starred_fla else fla
    return MotorLoad(
        name=f"{name} ({voltage}V/{phase}ph/{hertz}Hz)",
        fla=fla_value,
        lra=lra,
        hp=hp,
        quantity=int(qty),
        source_range=source_range,
        duty=duty,
    )


def _add_power_exhaust_or_erv_exhaust(result: ElectricalResult, errors: ErrorResult, model: ModelNumber, tables, ranges, scope: str) -> None:
    """Port WritePowerExhaustFan for active PE/ERV exhaust load (Motor4)."""
    if model.pe:
        suffix = "7_11" if model.seven_eleven else ""
        try:
            voltage_range = get_range_df(tables, ranges, scope, f"PwrExhVoltageData{suffix}")
            fla_range = get_range_df(tables, ranges, scope, f"PwrExhFLAData{suffix}")
            lra_range = get_range_df(tables, ranges, scope, f"PwrExhLRAData{suffix}")
        except Exception as exc:
            errors.add("POWER_EXHAUST_RANGE_MISSING", f"Power exhaust lookup range missing for {scope}: {exc}", severity="warning")
            return
        voltage = excel_lookup(model.voltage_index, voltage_range, 2, default="")
        phase = excel_lookup(model.voltage_index, voltage_range, 3, default="")
        hz = excel_lookup(model.voltage_index, voltage_range, 4, default="")
        qty_raw = excel_lookup(result.chassis or model.chassis, fla_range, 2, default="")
        fla_raw = excel_lookup(result.chassis or model.chassis, fla_range, model.voltage_index + 2, default="")
        lra_raw = excel_lookup(result.chassis or model.chassis, lra_range, model.voltage_index + 2, default="")
        if not voltage or not phase or not hz or not qty_raw or not fla_raw or not lra_raw:
            errors.add("POWER_EXHAUST_INCOMPLETE", "Power exhaust is not fully specified.", severity="warning")
            return
        result.motors.append(MotorLoad(
            name=f"Power Exhaust ({voltage}V/{phase}ph/{hz}Hz)",
            fla=f"*{_clean_motor_value(fla_raw, decimals=1)}*",
            lra=_clean_motor_value(lra_raw, decimals=0),
            hp=None,
            quantity=int(to_float(qty_raw, 1) or 1),
            source_range=f"{scope}.PwrExhFLAData/Motor4",
            duty="both",
        ))
        result.notes.append("Power exhaust accessory load added from Motor4 logic.")
        return

    if int(model.erv or 0) != 0:
        try:
            data_range = get_range_df(tables, ranges, "Data_ERV", f"ERVExhDataCH{result.chassis or model.chassis}")
        except Exception as exc:
            errors.add("ERV_EXHAUST_RANGE_MISSING", f"ERV exhaust lookup range missing for chassis {result.chassis or model.chassis}: {exc}", severity="warning")
            return
        motor = _make_motor_from_data_range(
            name="ERV Exhaust",
            source_range=f"Data_ERV.ERVExhDataCH{result.chassis or model.chassis}/Motor4",
            voltage_index=model.voltage_index,
            data_range=data_range,
            duty="both",
        )
        if motor:
            result.motors.append(motor)
            result.notes.append("ERV exhaust accessory load added from Motor4 logic.")
        else:
            errors.add("ERV_EXHAUST_INCOMPLETE", "ERV exhaust is not fully specified.", severity="warning")


def _add_convenience_outlet(result: ElectricalResult, errors: ErrorResult, model: ModelNumber, tables, ranges) -> None:
    """Port WriteConvenienceOutlet for active powered convenience outlet (Motor5)."""
    if not model.co:
        return
    try:
        data_range = get_range_df(tables, ranges, "Data_Common", "OutletData")
    except Exception as exc:
        errors.add("OUTLET_RANGE_MISSING", f"Convenience outlet lookup range missing: {exc}", severity="warning")
        return
    motor = _make_motor_from_data_range(
        name="Outlet",
        source_range="Data_Common.OutletData/Motor5",
        voltage_index=model.voltage_index,
        data_range=data_range,
        duty="both",
    )
    if motor:
        motor.hp = None
        result.motors.append(motor)
        result.notes.append("Convenience outlet accessory load added from Motor5 logic.")
    else:
        errors.add("OUTLET_INCOMPLETE", "Convenience outlet is not fully specified.", severity="warning")


def _add_erv_wheel_and_supply(result: ElectricalResult, errors: ErrorResult, model: ModelNumber, tables, ranges) -> None:
    """Port WriteERVWheel and WriteERVSupply for active ERV loads (Motor6/Motor7)."""
    if int(model.erv or 0) == 0:
        return
    chassis = result.chassis or model.chassis
    for range_prefix, label, motor_no, starred in [
        ("ERVWheelDataCH", "ERV Wheel", "Motor6", False),
        ("ERVSupplyDataCH", "ERV Supply", "Motor7", True),
    ]:
        range_name = f"{range_prefix}{chassis}"
        try:
            data_range = get_range_df(tables, ranges, "Data_ERV", range_name)
        except Exception as exc:
            errors.add(f"{label.upper().replace(' ', '_')}_RANGE_MISSING", f"{label} lookup range missing for {range_name}: {exc}", severity="warning")
            continue
        motor = _make_motor_from_data_range(
            name=label,
            source_range=f"Data_ERV.{range_name}/{motor_no}",
            voltage_index=model.voltage_index,
            data_range=data_range,
            duty="both",
            starred_fla=starred,
        )
        if motor:
            result.motors.append(motor)
            result.notes.append(f"{label} accessory load added from {motor_no} logic.")
        else:
            errors.add(f"{label.upper().replace(' ', '_')}_INCOMPLETE", f"{label} is not fully specified.", severity="warning")


def build_electrical_result(model: ModelNumber, lookup_tables: Dict[str, pd.DataFrame]) -> tuple[ElectricalResult, ErrorResult]:
    """Port the first useful slice of mWrite_Values into Python.

    Implemented in Step 5:
    - GetVoltage
    - GetChassis
    - WriteCharge
    - WriteCompressors
    - WriteIndoorFan
    - WriteOutdoorFan
    """
    errors = ErrorResult()
    ranges = load_defined_ranges()
    scope = _model_scope(model)
    result = ElectricalResult(voltage=get_voltage_text(model), voltage_index=model.voltage_index, chassis=model.chassis)
    result.notes.append(f"Data sheet route: {scope}")

    if not lookup_tables:
        errors.add("LOOKUPS_NOT_LOADED", "No lookup CSVs are loaded.", severity="warning")
        return result, errors

    if scope not in lookup_tables:
        errors.add("DATA_SHEET_NOT_LOADED", f"Lookup CSV not loaded for selected sheet: {scope}.", severity="warning")
        return result, errors

    _add_chassis(result, errors, model, lookup_tables, ranges, scope)
    _add_charge(result, errors, model, lookup_tables, ranges, scope)
    _add_compressors(result, errors, model, lookup_tables, ranges, scope)
    _add_indoor_fan(result, errors, model, lookup_tables, ranges, scope)
    _add_outdoor_fan(result, errors, model, lookup_tables, ranges, scope)
    _add_electric_heat(result, errors, model, lookup_tables, ranges, scope)
    _add_power_exhaust_or_erv_exhaust(result, errors, model, lookup_tables, ranges, scope)
    _add_convenience_outlet(result, errors, model, lookup_tables, ranges)
    _add_erv_wheel_and_supply(result, errors, model, lookup_tables, ranges)

    if not result.compressors:
        result.notes.append("No compressors were generated yet; validate model route/flags against Excel output.")
    if not result.motors:
        result.notes.append("No fan motors were generated yet; validate model route/flags against Excel output.")

    return result, errors
