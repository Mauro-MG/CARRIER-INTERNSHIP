from dataclasses import dataclass, asdict
from typing import Dict, Any


@dataclass
class ModelNumber:
    """Python equivalent of VBA ModelNumber_Type.

    This is intentionally broad so the first Python app can preserve the same
    intermediate state that the VBA macros currently store in ModelNumber_Type.
    Later steps should fill these fields from the real CheckModelNumber logic.
    """
    model_number: str = ""
    model_index: int = 0
    model_string: str = ""
    special_order_type: str = ""
    fiop_string: str = ""

    series: int = 0
    gas: bool = False
    heat_level: int = 0
    heat: str = ""
    control_type_text: str = ""
    size: int = 0
    motor_drive: str = ""
    reheat: bool = False
    voltage_index: int = 0
    design: str = ""

    conv_outlet: int = 0
    terminal_block: int = 0
    intake: int = 0
    exhaust: int = 0
    coil_guard: int = 0
    filter_type: int = 0
    poise: int = 0
    uv: int = 0

    co: bool = False
    hacr: bool = False
    pe: bool = False
    erv: int = 0
    econ_erv: bool = False
    econ: bool = False
    mocp_factor: float = 0.0
    free_bump: bool = False
    manufacturer: int = 0
    refrigerant_option: str = ""
    sensor_option: str = ""
    control_type: int = 0
    packaging: str = "0"

    co2: bool = False
    heat_pump: bool = False
    dual_comp: bool = False
    direct_drive: bool = False
    cdu: bool = False
    is_50: bool = False
    chassis: str = ""
    rtpf: bool = False
    mmcdu: bool = False
    mm: bool = False
    eto: bool = False
    two_speed_text: str = ""
    disc: bool = False
    mech_ctrl: bool = False
    target: bool = False
    single_phase: bool = False
    two_speed: bool = False
    two_stage: bool = False
    fan_coil: bool = False
    three_speed: bool = False
    efficiency: str = ""
    hsccr: bool = False
    seven_eleven: bool = False
    seer2: bool = False
    ulnx: bool = False
    doas: str = ""
    doas_unit: bool = False
    tier: str = ""
    dual_circ: bool = False
    three_stage: bool = False

    def to_dict(self) -> Dict[str, Any]:
        return asdict(self)
