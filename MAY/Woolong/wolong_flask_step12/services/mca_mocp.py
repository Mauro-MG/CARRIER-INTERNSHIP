from __future__ import annotations

import math
from dataclasses import dataclass
from typing import Iterable, Tuple

from models.model_number import ModelNumber
from models.electrical import ElectricalResult, CompressorLoad, MotorLoad
from models.calculation_result import McaMocpResult, AccessoryMcaRow
from models.errors import ErrorResult
from .data_loader import load_lookup_tables
from .workbook_ranges import load_defined_ranges, get_range_df, excel_lookup
from .optional_accessories import build_optional_accessory_scenarios


STANDARD_FUSES = [
    15, 20, 25, 30, 35, 40, 45, 50, 60, 70, 80, 90, 100, 110,
    125, 150, 175, 200, 225, 250, 300, 350, 400, 450, 500, 600,
    700, 800, 1000, 1200, 1600, 2000, 2500, 3000, 4000, 5000, 6000,
]
THRESHOLD_MOCP = [30, 60, 80, 100, 400]

COOL = "cool"
HEAT = "heat"
BOTH = "both"


@dataclass(frozen=True)
class PairValue:
    """VBA left/right pair equivalent. Left = 208 side, Right = 230 side."""
    left: float
    right: float
    slash: bool = False

    @classmethod
    def same(cls, value: float) -> "PairValue":
        return cls(float(value), float(value), False)

    def max(self) -> float:
        return max(self.left, self.right)


def _pair_from_number(value: float | int | str | None) -> PairValue:
    if value is None or value == "" or value == "-":
        return PairValue.same(0.0)
    if isinstance(value, str):
        value = value.strip().replace("*", "")
        if "/" in value:
            left, right = value.split("/", 1)
            return PairValue(float(left or 0), float(right or 0), True)
    return PairValue.same(float(value or 0))


def _fmt_pair(value: PairValue, decimals: int = 1) -> str | float | int:
    """Mimic VBA fmt(...,"1") / Format(...,"0") output for single/slash values."""
    if decimals == 1:
        left = f"{value.left:.1f}"
        right = f"{value.right:.1f}"
    else:
        left = f"{value.left:.0f}"
        right = f"{value.right:.0f}"
    if value.slash and abs(value.left - value.right) > 1e-9:
        return f"{left}/{right}"
    return float(left) if decimals == 1 else int(left)


def _roundup_pair(value: PairValue) -> str | int:
    left = math.ceil(value.left)
    right = math.ceil(value.right)
    if value.slash and left != right:
        return f"{left}/{right}"
    return left


def _standard_mocp(current: float, factor: float) -> Tuple[int, int]:
    """Port of VBA StandardMOCP(Current, Small, Large, Factor)."""
    if factor not in (1.5, 2.25):
        # The original VBA shows a MsgBox. Here we continue with the table.
        pass
    for fuse in STANDARD_FUSES:
        if current < fuse:
            large = fuse
            idx = STANDARD_FUSES.index(fuse)
            small = STANDARD_FUSES[idx - 1] if idx > 0 else fuse
            if factor == 1.5:
                small = large
            return small, large
    return STANDARD_FUSES[-1], STANDARD_FUSES[-1]


def _threshold_mocp(mocp: float) -> int:
    for threshold in THRESHOLD_MOCP:
        if threshold >= mocp:
            return threshold
    return THRESHOLD_MOCP[-1]


def _free_bump(mocp15: PairValue, mocp225: PairValue) -> PairValue:
    def get_new(m15: float, m225: float) -> float:
        threshold = _threshold_mocp(m15)
        return max(m15, m225) if threshold > m225 else threshold

    return PairValue(
        get_new(mocp15.left, mocp225.left),
        get_new(mocp15.right, mocp225.right),
        mocp15.slash or mocp225.slash,
    )


def _is_electric_heat(motor: MotorLoad) -> bool:
    text = f"{motor.name} {motor.source_range}".lower()
    return motor.kw not in (0, 0.0, "", None) or "electric heat" in text or "motor3" in text


def _cooling_loads(electrical: ElectricalResult, include_heat_motor: bool = False) -> tuple[list[CompressorLoad], list[MotorLoad]]:
    motors = []
    for m in electrical.motors:
        if _is_electric_heat(m) and not include_heat_motor:
            continue
        if m.duty in (COOL, BOTH, "1", "3", ""):
            motors.append(m)
    return electrical.compressors, motors


def _heating_motors(electrical: ElectricalResult) -> list[MotorLoad]:
    return [m for m in electrical.motors if (not _is_electric_heat(m)) and m.duty in (HEAT, BOTH, "2", "3")]


def _electric_heat_motor(electrical: ElectricalResult) -> MotorLoad | None:
    for m in electrical.motors:
        if _is_electric_heat(m):
            return m
    return None


def _max_left_right(electrical: ElectricalResult) -> PairValue:
    values = []
    for comp in electrical.compressors:
        values.append(_pair_from_number(comp.rla).max())
    for motor in _cooling_loads(electrical)[1]:
        values.append(_pair_from_number(motor.fla).max())
    max_value = max(values) if values else 0.0
    return PairValue.same(max_value)


def _total_left_right(electrical: ElectricalResult, factor: float, starting: PairValue | None = None) -> PairValue:
    total_left = starting.left if starting else 0.0
    total_right = starting.right if starting else 0.0
    slash = starting.slash if starting else False

    compressors, motors = _cooling_loads(electrical)
    for comp in compressors:
        amps = _pair_from_number(comp.rla)
        qty = comp.quantity or 0
        total_left += factor * qty * amps.left
        total_right += factor * qty * amps.right
        slash = slash or amps.slash

    for motor in motors:
        amps = _pair_from_number(motor.fla)
        qty = motor.quantity or 0
        total_left += factor * qty * amps.left
        total_right += factor * qty * amps.right
        slash = slash or amps.slash

    return PairValue(total_left, total_right, slash)


def _get_mca_mocp_base(electrical: ElectricalResult, factor: float, sum_selector: int, hacr: bool) -> PairValue:
    """Port the cooling/base-unit part of VBA GetMCAMOCPBase.

    Sum selector matches VBA:
    0 = MCA, 1 = disconnect, 2 = MOCP/fuse.
    Electric heat logic from GetMCAMOCP50Base is intentionally deferred until
    Step 7 because Step 5 does not yet extract Motor(3,kW_M)/heater circuits.
    """
    max_load = _max_left_right(electrical)

    if sum_selector == 0:  # MCA 36.14a
        start = PairValue((factor - 1) * max_load.left, (factor - 1) * max_load.right, max_load.slash)
        total = _total_left_right(electrical, 1.0, start)
        if hacr:
            highest = max(total.left, total.right)
            total = PairValue(highest, highest, total.slash)
        return total

    if sum_selector == 1:  # Disconnect 36.18; no standard rounding in VBA
        return _total_left_right(electrical, factor, PairValue.same(0.0))

    if sum_selector == 2:  # MOCP 36.15 / 36.16
        mca_start = PairValue((1.25 - 1) * max_load.left, (1.25 - 1) * max_load.right, max_load.slash)
        total_mca = _total_left_right(electrical, 1.0, mca_start)
        if hacr:
            highest = max(total_mca.left, total_mca.right)
            total_mca = PairValue(highest, highest, total_mca.slash)

        mocp_start = PairValue((factor - 1) * max_load.left, (factor - 1) * max_load.right, max_load.slash)
        raw_mocp = _total_left_right(electrical, 1.0, mocp_start)
        if hacr:
            highest = max(raw_mocp.left, raw_mocp.right)
            raw_mocp = PairValue(highest, highest, raw_mocp.slash)

        small_l, large_l = _standard_mocp(raw_mocp.left, factor)
        left = small_l
        if left < total_mca.left:  # VBA Exception 2
            _, left = _standard_mocp(total_mca.left, factor)

        small_r, large_r = _standard_mocp(raw_mocp.right, factor)
        right = small_r
        if right < total_mca.right:
            _, right = _standard_mocp(total_mca.right, factor)

        return PairValue(float(left), float(right), raw_mocp.slash or total_mca.slash)

    return PairValue.same(0.0)


def _get_mca_mocp(electrical: ElectricalResult, factor: float, sum_selector: int, hacr: bool, free_bump: bool) -> PairValue:
    """Port VBA GetMCAMOCP wrapper, including FreeBump behavior."""
    if not free_bump:
        return _get_mca_mocp_base(electrical, factor, sum_selector, hacr)

    if sum_selector == 0:
        # Rev AQ: MCA is rounded up to whole amps when bFreeBump is true.
        base = _get_mca_mocp_base(electrical, factor, sum_selector, hacr)
        return PairValue(float(math.ceil(base.left)), float(math.ceil(base.right)), base.slash)
    if sum_selector == 1:
        return _get_mca_mocp_base(electrical, factor, sum_selector, hacr)
    if sum_selector == 2:
        if factor == 2.25:
            return _get_mca_mocp_base(electrical, factor, sum_selector, hacr)
        mocp15 = _get_mca_mocp_base(electrical, factor, sum_selector, hacr)
        mocp225 = _get_mca_mocp_base(electrical, 2.25, sum_selector, hacr)
        return _free_bump(mocp15, mocp225)
    return PairValue.same(0.0)


def _calculate_lra(electrical: ElectricalResult) -> PairValue:
    """Calculate LRA using left/right pairs instead of assuming scalar floats."""
    run_l = run_r = 0.0
    delta_l = delta_r = 0.0
    slash = False
    for comp in electrical.compressors:
        rla = _pair_from_number(comp.rla)
        lra = _pair_from_number(comp.lra)
        qty = _pair_from_number(comp.quantity).left or 0
        run_l += qty * rla.left
        run_r += qty * rla.right
        delta_l = max(delta_l, lra.left - rla.left)
        delta_r = max(delta_r, lra.right - rla.right)
        slash = slash or rla.slash or lra.slash
    for motor in _cooling_loads(electrical, include_heat_motor=False)[1]:
        fla = _pair_from_number(motor.fla)
        lra = _pair_from_number(motor.lra)
        qty = _pair_from_number(motor.quantity).left or 0
        run_l += qty * fla.left
        run_r += qty * fla.right
        delta_l = max(delta_l, lra.left - fla.left)
        delta_r = max(delta_r, lra.right - fla.right)
        slash = slash or fla.slash or lra.slash
    return PairValue(max(0.0, run_l + delta_l), max(0.0, run_r + delta_r), slash)


def _max_load_for(compressors: list[CompressorLoad], motors: list[MotorLoad]) -> PairValue:
    left = right = 0.0
    slash = False
    for comp in compressors:
        amps = _pair_from_number(comp.rla)
        left = max(left, amps.left); right = max(right, amps.right); slash = slash or amps.slash
    for motor in motors:
        amps = _pair_from_number(motor.fla)
        left = max(left, amps.left); right = max(right, amps.right); slash = slash or amps.slash
    return PairValue(left, right, slash)


def _total_for(compressors: list[CompressorLoad], motors: list[MotorLoad], factor: float, start: PairValue | None = None) -> PairValue:
    left = start.left if start else 0.0
    right = start.right if start else 0.0
    slash = start.slash if start else False
    for comp in compressors:
        amps = _pair_from_number(comp.rla)
        qty = _pair_from_number(comp.quantity).left or 0
        left += factor * qty * amps.left
        right += factor * qty * amps.right
        slash = slash or amps.slash
    for motor in motors:
        amps = _pair_from_number(motor.fla)
        qty = _pair_from_number(motor.quantity).left or 0
        left += factor * qty * amps.left
        right += factor * qty * amps.right
        slash = slash or amps.slash
    return PairValue(left, right, slash)


def _total_cooling_mca_mocp_50(electrical: ElectricalResult, left_heat: float, left_heat_factor: float, right_heat: float, right_heat_factor: float, factor: float, sum_selector: int, hacr: bool) -> PairValue:
    compressors, cool_motors = _cooling_loads(electrical, include_heat_motor=False)
    max_cool = _max_load_for(compressors, cool_motors)
    slash = max_cool.slash
    if sum_selector == 0:
        start = PairValue((factor - 1) * max_cool.left + left_heat_factor * left_heat, (factor - 1) * max_cool.right + right_heat_factor * right_heat, slash)
        total = _total_for(compressors, cool_motors, 1.0, start)
    elif sum_selector == 1:
        start = PairValue(factor * left_heat, factor * right_heat, slash)
        total = _total_for(compressors, cool_motors, factor, start)
    elif sum_selector == 2:
        mca_start = PairValue((1.25 - 1) * max_cool.left + left_heat_factor * left_heat, (1.25 - 1) * max_cool.right + right_heat_factor * right_heat, slash)
        total_mca = _total_for(compressors, cool_motors, 1.0, mca_start)
        if hacr:
            hi = max(total_mca.left, total_mca.right); total_mca = PairValue(hi, hi, total_mca.slash)
        raw_start = PairValue((factor - 1) * max_cool.left + left_heat, (factor - 1) * max_cool.right + right_heat, slash)
        raw = _total_for(compressors, cool_motors, 1.0, raw_start)
        if hacr:
            hi = max(raw.left, raw.right); raw = PairValue(hi, hi, raw.slash)
        small_l, large_l = _standard_mocp(raw.left, factor)
        left = small_l
        if left < total_mca.left:
            _, left = _standard_mocp(total_mca.left, factor)
        small_r, large_r = _standard_mocp(raw.right, factor)
        right = small_r
        if right < total_mca.right:
            _, right = _standard_mocp(total_mca.right, factor)
        return PairValue(float(left), float(right), raw.slash or total_mca.slash)
    else:
        return PairValue.same(0.0)
    if hacr:
        hi = max(total.left, total.right); total = PairValue(hi, hi, total.slash)
    return total


def _heat_factor(kw: float) -> float:
    return 1.0 if kw >= 50 else 1.25


def _get_mca_mocp_50_base(electrical: ElectricalResult, factor: float, sum_selector: int, hacr: bool) -> PairValue:
    """Port of VBA GetMCAMOCP50Base for main 50-series calculations.

    This handles Motor3 electric heat as a separate heat load, then returns the
    max of cooling and heating sections exactly like the VBA branch. Accessory
    and feeder-specific literature rows remain deferred.
    """
    heat = _electric_heat_motor(electrical)
    if not heat:
        # 50 unit with no electric heater selected behaves like base cooling.
        return _get_mca_mocp_base(electrical, factor, sum_selector, hacr)

    heat_amps = _pair_from_number(heat.fla)
    heat_kw = _pair_from_number(heat.kw)
    left_heat, right_heat = heat_amps.left, heat_amps.right
    left_kw, right_kw = heat_kw.left, heat_kw.right
    left_heat_factor = _heat_factor(left_kw) if heat.duty == BOTH else 0.0
    right_heat_factor = _heat_factor(right_kw) if heat.duty == BOTH else 0.0

    total_cool = _total_cooling_mca_mocp_50(
        electrical, left_heat if heat.duty == BOTH else 0.0, left_heat_factor,
        right_heat if heat.duty == BOTH else 0.0, right_heat_factor,
        factor, sum_selector, hacr,
    )

    heat_motors = _heating_motors(electrical)
    max_heat = _max_load_for([], heat_motors)
    slash = heat_amps.slash or heat_kw.slash or max_heat.slash

    if sum_selector == 0:
        total_heat = _total_for([], heat_motors, factor, PairValue.same(0.0))
        total_heat = PairValue(
            total_heat.left + (_heat_factor(left_kw) * left_heat),
            total_heat.right + (_heat_factor(right_kw) * right_heat),
            slash or total_heat.slash,
        )
        if hacr:
            # VBA has special 208/230 balancing when crossing 50kW; max() is the
            # conservative final behavior it applies.
            hi = max(total_heat.left, total_heat.right); total_heat = PairValue(hi, hi, total_heat.slash)
    elif sum_selector == 1:
        total_heat = _total_for([], heat_motors, factor, PairValue(factor * left_heat, factor * right_heat, slash))
    elif sum_selector == 2:
        total_heat_mca = _total_for([], heat_motors, 1.25, PairValue.same(0.0))
        total_heat_mca = PairValue(
            total_heat_mca.left + (_heat_factor(left_kw) * left_heat),
            total_heat_mca.right + (_heat_factor(right_kw) * right_heat),
            slash or total_heat_mca.slash,
        )
        if hacr:
            hi = max(total_heat_mca.left, total_heat_mca.right); total_heat_mca = PairValue(hi, hi, total_heat_mca.slash)

        raw_heat = _total_for([], heat_motors, 1.0, PairValue((factor - 1) * max_heat.left + left_heat, (factor - 1) * max_heat.right + right_heat, slash))
        small_l, large_l = _standard_mocp(raw_heat.left, factor)
        heat_min_l = 1.25 * left_heat
        total_left_1 = large_l if small_l < heat_min_l else small_l
        total_left_2, _large_l = _standard_mocp(raw_heat.left, factor)
        if total_left_2 < total_heat_mca.left:
            _, total_left_2 = _standard_mocp(total_heat_mca.left, factor)
        left = max(total_left_1, total_left_2)

        small_r, large_r = _standard_mocp(raw_heat.right, factor)
        heat_min_r = 1.25 * right_heat
        total_right_1 = large_r if small_r < heat_min_r else small_r
        total_right_2, _large_r = _standard_mocp(raw_heat.right, factor)
        if total_right_2 < total_heat_mca.right:
            _, total_right_2 = _standard_mocp(total_heat_mca.right, factor)
        right = max(total_right_1, total_right_2)
        total_heat = PairValue(float(left), float(right), slash or raw_heat.slash or total_heat_mca.slash)
    else:
        total_heat = PairValue.same(0.0)

    return PairValue(max(total_heat.left, total_cool.left), max(total_heat.right, total_cool.right), total_heat.slash or total_cool.slash)


def _get_mca_mocp_50(electrical: ElectricalResult, factor: float, sum_selector: int, hacr: bool, free_bump: bool) -> PairValue:
    if not free_bump:
        return _get_mca_mocp_50_base(electrical, factor, sum_selector, hacr)
    if sum_selector == 0:
        base = _get_mca_mocp_50_base(electrical, factor, sum_selector, hacr)
        return PairValue(float(math.ceil(base.left)), float(math.ceil(base.right)), base.slash)
    if sum_selector == 1:
        return _get_mca_mocp_50_base(electrical, factor, sum_selector, hacr)
    if sum_selector == 2:
        if factor == 2.25:
            return _get_mca_mocp_50_base(electrical, factor, sum_selector, hacr)
        mocp15 = _get_mca_mocp_50_base(electrical, factor, sum_selector, hacr)
        mocp225 = _get_mca_mocp_50_base(electrical, 2.25, sum_selector, hacr)
        return _free_bump(mocp15, mocp225)
    return PairValue.same(0.0)



def _is_accessory_motor(motor: MotorLoad) -> bool:
    text = f"{motor.name} {motor.source_range}".lower()
    return any(token in text for token in [
        "motor4", "motor5", "motor6", "motor7",
        "power exhaust", "pwr exh", "outlet", "erv exhaust", "erv wheel", "erv supply",
    ])


def _electrical_without_accessories(electrical: ElectricalResult) -> ElectricalResult:
    """Remove Motor4-Motor7 accessory loads while keeping base cooling/heat loads."""
    return ElectricalResult(
        voltage=electrical.voltage,
        voltage_index=electrical.voltage_index,
        sccr=electrical.sccr,
        sccr_ka=electrical.sccr_ka,
        charge=electrical.charge,
        chassis=electrical.chassis,
        compressors=list(electrical.compressors),
        motors=[m for m in electrical.motors if not _is_accessory_motor(m)],
        accessories=list(electrical.accessories),
        notes=list(electrical.notes),
    )


def _electrical_with_one_accessory(base: ElectricalResult, accessory: MotorLoad) -> ElectricalResult:
    cloned = _electrical_without_accessories(base)
    cloned.motors.append(accessory)
    return cloned


def _electrical_with_accessory_motors(base: ElectricalResult, accessories: list[MotorLoad]) -> ElectricalResult:
    cloned = _electrical_without_accessories(base)
    cloned.motors.extend(accessories)
    return cloned


def _calculate_current_pairs(model: ModelNumber, electrical: ElectricalResult, factor: float, free_bump: bool, hacr: bool) -> tuple[PairValue, PairValue, PairValue, PairValue]:
    """Shared current calculation for base and accessory rows."""
    if model.series == 50 or model.is_50:
        mca_pair = _get_mca_mocp_50(electrical, 1.25, 0, hacr, free_bump)
        mocp_pair = _get_mca_mocp_50(electrical, factor, 2, hacr, free_bump)
        disconnect_pair = _get_mca_mocp_50(electrical, 1.15, 1, hacr, free_bump=False)
    else:
        mca_pair = _get_mca_mocp(electrical, 1.25, 0, hacr, free_bump)
        mocp_pair = _get_mca_mocp(electrical, factor, 2, hacr, free_bump)
        disconnect_pair = _get_mca_mocp(electrical, 1.15, 1, hacr, free_bump=False)
    lra_pair = _calculate_lra(electrical)
    return mca_pair, mocp_pair, disconnect_pair, lra_pair


def _calculate_accessory_rows(model: ModelNumber, electrical: ElectricalResult, factor: float, free_bump: bool, hacr: bool) -> list[AccessoryMcaRow]:
    """Best-effort port of the AccMCA/AccMCARHSCCR rows.

    The workbook creates accessory rows by adding one optional/accessory motor
    to the base electrical set, then calculating MCA, MOCP, disconnect, LRA and
    SPB for that row. This implementation creates rows for active Motor4-Motor7
    accessory loads that have been ported in Step 9.
    """
    rows: list[AccessoryMcaRow] = []
    base_electrical = _electrical_without_accessories(electrical)
    base_mocp_pair = _get_mca_mocp_50(base_electrical, factor, 2, hacr, free_bump) if (model.series == 50 or model.is_50) else _get_mca_mocp(base_electrical, factor, 2, hacr, free_bump)
    base_mocp = _fmt_pair(base_mocp_pair, decimals=0)

    def append_row(row_name: str, row_electrical: ElectricalResult, source: str) -> None:
        mca_pair, mocp_pair, disc_pair, lra_pair = _calculate_current_pairs(model, row_electrical, factor, free_bump, hacr)
        mca_value = _fmt_pair(mca_pair, decimals=0 if free_bump else 1)
        mocp_value = _fmt_pair(mocp_pair, decimals=0)
        disc_value = _fmt_pair(disc_pair, decimals=0)
        spb = _get_single_point_box(model, row_electrical, base_mocp, mocp_value, mca_value, hsccr_version=False) if (model.series == 50 or model.is_50) else "-"
        spb_hsccr = _get_single_point_box(model, row_electrical, base_mocp, mocp_value, mca_value, hsccr_version=True) if (model.series == 50 or model.is_50) else "-"
        rows.append(AccessoryMcaRow(
            name=row_name,
            mca=mca_value,
            mocp=mocp_value,
            disconnect=disc_value,
            lra=_fmt_pair(lra_pair, decimals=0),
            single_point_box=spb,
            single_point_box_hsccr=spb_hsccr,
            source=source,
        ))

    for motor in electrical.motors:
        if not _is_accessory_motor(motor):
            continue
        row_electrical = _electrical_with_one_accessory(electrical, motor)
        append_row(motor.name, row_electrical, motor.source_range)

    for scenario in build_optional_accessory_scenarios(model, electrical):
        row_electrical = _electrical_with_accessory_motors(electrical, scenario.motors)
        append_row(scenario.name, row_electrical, scenario.source)

    return rows


def _numeric_max(value) -> float:
    """Return the highest side of a normal or slash MCA/MOCP value."""
    try:
        return _pair_from_number(value).max()
    except Exception:
        try:
            text = str(value or "").replace("-", "0")
            if "/" in text:
                return max(float(x or 0) for x in text.split("/", 1))
            return float(text or 0)
        except Exception:
            return 0.0


def _excel_lookup_or_selector(tables, ranges, range_name: str, key: str, col: int = 2) -> str:
    """Lookup helper that returns the selector itself when the VBA lookup would error.

    The original GetSinglePointBox returns sSinglePointDescSelector when the
    description lookup fails. Keeping that behavior makes debugging missing
    SPB table rows much easier in Flask.
    """
    try:
        rng = get_range_df(tables, ranges, "Data_Common", range_name)
        value = excel_lookup(key, rng, col, default="")
    except Exception:
        return key
    value = str(value).strip()
    return value if value and value.lower() not in ("nan", "n/a") else key


def _single_point_desc_range(chassis: str) -> str:
    chassis = str(chassis or "").strip()
    if chassis in ("1", "2"):
        return "SPBDesc12"
    if chassis in ("3", "4"):
        return "SPBDesc34"
    if chassis == "5":
        return "SPBDesc5"
    return "SPBDesc34"


def _build_spb_selector(
    *,
    chassis: str,
    unit_mca,
    base_mocp,
    unit_mocp,
    voltage_index: int,
    num_wires,
    actual_num_wires,
    heat_pump: bool,
    disc: bool,
    hacr: bool,
    erv: int,
    acc: bool,
    hsccr: bool,
    force_hsccr_bit: bool = False,
) -> tuple[str, str, str]:
    """Port the selector-building section of VBA GetSinglePointBox.

    Returns (description_selector, spb_description, final_spb_selector).
    """
    chassis = str(chassis or "").strip()
    try:
        nw = int(float(str(num_wires or 0).split("/", 1)[0]))
    except Exception:
        nw = 0
    try:
        anw = int(float(str(actual_num_wires or 0).split("/", 1)[0]))
    except Exception:
        anw = 0

    desc_selector = "1" if _numeric_max(unit_mca) > 50 else "0"
    desc_selector += str(nw)
    desc_selector += "1" if voltage_index in (3, 5) else "0"
    desc_selector += "1" if _numeric_max(base_mocp) > 60 else "0"
    desc_selector += "1" if _numeric_max(base_mocp) > 80 else "0"
    desc_selector += "1" if _numeric_max(unit_mocp) > 60 else "0"

    erv_spb = chassis in ("4", "5") and int(erv or 0) != 0 and voltage_index == 5
    large_hacr_spb = bool(hacr) and _numeric_max(unit_mocp) > 150
    large_disc_spb = bool(disc) and _numeric_max(unit_mca) > 150
    large_hsccr_spb = bool(hsccr) and voltage_index == 5

    desc_selector += "1" if (heat_pump or erv_spb) else "0"
    desc_selector += "1" if (hsccr or force_hsccr_bit) else "0"

    lookup_key = desc_selector + str(anw) if (nw == 3 and anw == 6) else desc_selector
    tables = load_lookup_tables()
    ranges = load_defined_ranges()
    desc = _excel_lookup_or_selector(tables, ranges, _single_point_desc_range(chassis), lookup_key, 2)

    if chassis in ("1", "2"):
        suffix = "1" if ((disc or hacr) and voltage_index in (3, 5) and nw > 0) or ((disc or hacr) and nw > 0 and not acc) else "0"
        spb_selector = "12" + desc + suffix
    elif chassis in ("3", "4"):
        spb_selector = chassis + desc + "0"
    elif chassis == "5":
        suffix = "1" if ((large_hacr_spb or (large_disc_spb and not acc)) or large_hsccr_spb) else "0"
        spb_selector = "4" + desc + suffix
    else:
        spb_selector = "" + desc + "0"
    return desc_selector, desc, spb_selector


def _lookup_spb(spb_selector: str) -> str:
    tables = load_lookup_tables()
    ranges = load_defined_ranges()
    try:
        rng = get_range_df(tables, ranges, "Data_Common", "SPB")
        value = excel_lookup(spb_selector, rng, 2, default="")
    except Exception:
        return spb_selector
    value = str(value).strip()
    return value if value and value.lower() not in ("nan", "n/a") else "NA"


def _get_single_point_box(model: ModelNumber, electrical: ElectricalResult, base_mocp, unit_mocp, unit_mca, *, hsccr_version: bool = False) -> str:
    """Python equivalent of GetSinglePointBox / GetSinglePointBoxHSCCR."""
    if model.gas or model.cdu:
        return "-"
    heat = _electric_heat_motor(electrical)
    num_wires = heat.num_wires if heat else 0
    actual_num_wires = heat.actual_num_wires if heat else 0
    _desc_selector, _desc, spb_selector = _build_spb_selector(
        chassis=electrical.chassis or model.chassis,
        unit_mca=unit_mca,
        base_mocp=base_mocp,
        unit_mocp=unit_mocp,
        voltage_index=model.voltage_index,
        num_wires=num_wires,
        actual_num_wires=actual_num_wires,
        heat_pump=bool(model.heat_pump),
        disc=bool(model.disc),
        hacr=bool(model.hacr),
        erv=int(model.erv or 0),
        acc=False,
        hsccr=bool(model.hsccr),
        force_hsccr_bit=hsccr_version,
    )
    return _lookup_spb(spb_selector)


def _electrical_without_heat(electrical: ElectricalResult) -> ElectricalResult:
    """Return a shallow copy with electric heat removed, matching VBA temp Motor3 blanking."""
    return ElectricalResult(
        voltage=electrical.voltage,
        voltage_index=electrical.voltage_index,
        sccr=electrical.sccr,
        sccr_ka=electrical.sccr_ka,
        charge=electrical.charge,
        chassis=electrical.chassis,
        compressors=list(electrical.compressors),
        motors=[m for m in electrical.motors if not _is_electric_heat(m)],
        accessories=list(electrical.accessories),
        notes=list(electrical.notes),
    )


def _calculate_optional_branch_circuit(model: ModelNumber, electrical: ElectricalResult, factor: float, free_bump: bool) -> tuple[object, object, object, str]:
    """Best-effort port of the 75 kW / 208-230V branch-circuit block.

    In one extracted Main branch this code is active; in another split-MCA branch
    it is commented out. We keep it guarded by the exact original condition and
    flag the feeder as dual branch when it triggers.
    """
    if not ((model.series == 50 or model.is_50) and model.voltage_index == 5 and model.heat_level == 3 and not model.gas and model.size != 14):
        return None, None, None, ""
    # VBA temporarily disables HACR for branch circuit.
    mca2 = _get_mca_mocp_50(electrical, 1.25, 0, hacr=False, free_bump=free_bump)
    mocp2 = _get_mca_mocp_50(electrical, factor, 2, hacr=False, free_bump=free_bump)
    disc2 = _get_mca_mocp_50(electrical, 1.15, 1, hacr=False, free_bump=False)
    return _fmt_pair(mca2, decimals=0 if free_bump else 1), _fmt_pair(mocp2, decimals=0), _fmt_pair(disc2, decimals=0), "dual branch circuit condition: 75 kW 208/230V electric heat"


def calculate_mca_mocp(model: ModelNumber, electrical: ElectricalResult) -> tuple[McaMocpResult, ErrorResult]:
    """Python replacement for VBA CalculateMCA/GetMCAMOCP/GetMCAMOCP50.

    Step 6 implements the base cooling-unit formulas and FreeBump behavior.
    Electric heat, dual feeder circuits, single point box selection, ERV/accessory
    MCA rows, and the final exact LRA routine are intentionally left for the next
    migration steps.
    """
    errors = ErrorResult()
    result = McaMocpResult()

    if not electrical.compressors and not electrical.motors:
        errors.add(
            "NO_LOADS",
            "No compressor/motor loads available, so MCA/MOCP cannot be calculated.",
            severity="warning",
        )
        return result, errors

    factor = model.mocp_factor or 1.5
    free_bump = model.free_bump or model.mocp_factor == 0.0
    hacr = bool(model.hacr)

    mca_pair, mocp_pair, disconnect_pair, lra_pair = _calculate_current_pairs(model, electrical, factor, free_bump, hacr)

    result.mca = _fmt_pair(mca_pair, decimals=0 if free_bump else 1)
    result.mocp = _fmt_pair(mocp_pair, decimals=0)
    result.fuse = result.mocp
    result.disconnect = _fmt_pair(disconnect_pair, decimals=0)
    result.lra = _fmt_pair(lra_pair, decimals=0)
    result.feeder = "single circuit" if not (model.series == 50 or model.is_50) else "50-series main circuit"

    heat = _electric_heat_motor(electrical)
    if heat:
        result.num_wires = str(heat.num_wires or "")
        result.actual_num_wires = str(heat.actual_num_wires or "")

    # Step 8: base MOCP is calculated with Motor3/electric heat temporarily blanked,
    # matching the VBA block immediately before GetSinglePointBox.
    if model.series == 50 or model.is_50:
        base_electrical = _electrical_without_heat(electrical)
        base_mocp_pair = _get_mca_mocp(base_electrical, factor, 2, hacr, free_bump)
        base_mocp = _fmt_pair(base_mocp_pair, decimals=0)
        result.single_point_box = _get_single_point_box(model, electrical, base_mocp, result.fuse, result.mca, hsccr_version=False)
        result.single_point_box_hsccr = _get_single_point_box(model, electrical, base_mocp, result.fuse, result.mca, hsccr_version=True)
        result.calculation_notes.append(f"Base MOCP without electric heat for SPB selection: {base_mocp}.")
    else:
        result.single_point_box = "-"
        result.single_point_box_hsccr = "-"

    mca2, mocp2, disc2, feeder_note = _calculate_optional_branch_circuit(model, electrical, factor, free_bump)
    if feeder_note:
        result.mca_2 = mca2
        result.mocp_2 = mocp2
        result.disconnect_2 = disc2
        result.feeder = feeder_note

    result.accessory_rows = _calculate_accessory_rows(model, electrical, factor, free_bump, hacr)
    if result.accessory_rows:
        result.calculation_notes.append(f"Implemented accessory MCA rows, including Step 10 optional AccRow catalog scenarios, for {len(result.accessory_rows)} active accessory load(s).")

    result.calculation_notes.extend([
        "base-unit MCA/MOCP path remains implemented for 48-series/non-electric-heat loads.",
        "50-series electric-heat MCA/MOCP path remains implemented from GetMCAMOCP50Base.",
        "Implemented Step 8 single-point-box lookup using Data_Common.SPBDesc12/SPBDesc34/SPBDesc5 and Data_Common.SPB.",
        "Implemented guarded MCA2/MOCP2 branch-circuit path for the original 75 kW 208/230V electric-heat condition.",
        f"MOCP factor used: {factor}; FreeBump used: {free_bump}; HACR used: {hacr}.",
        "Still deferred: full optional accessory catalog rows and exact split-MCA literature formatting.",
    ])

    return result, errors
