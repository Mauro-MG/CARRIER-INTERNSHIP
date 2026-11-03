from dataclasses import dataclass, field, asdict
from typing import Dict, Any, List, Optional


@dataclass
class CompressorLoad:
    name: str = ""
    rla: float = 0.0
    lra: float = 0.0
    quantity: int = 1
    source_range: str = ""  # VBA equivalent: Comp1, Comp2, Comp3


@dataclass
class MotorLoad:
    name: str = ""
    # Values may be numeric or slash strings such as "41.8/48.3" for 208/230V
    # because the VBA keeps left/right voltage values in the same cell.
    fla: Any = 0.0
    lra: Any = 0.0
    hp: Optional[float] = None
    quantity: Any = 1
    source_range: str = ""  # VBA equivalent: Motor1..Motor7
    duty: str = "cool"  # VBA CHB_M equivalent: cool, heat, or both
    kw: Any = 0.0      # Used for electric heat logic / Motor(3,kW_M)
    part_number: str = ""
    num_wires: Any = ""
    actual_num_wires: Any = ""


@dataclass
class AccessoryLoad:
    name: str = ""
    amps: float = 0.0
    quantity: int = 1
    source_range: str = ""
    duty: str = "cool"


@dataclass
class ElectricalResult:
    voltage: str = ""
    voltage_index: int = 0
    sccr: str = ""
    sccr_ka: str = ""
    charge: str = ""
    chassis: str = ""
    compressors: List[CompressorLoad] = field(default_factory=list)
    motors: List[MotorLoad] = field(default_factory=list)
    accessories: List[AccessoryLoad] = field(default_factory=list)
    notes: List[str] = field(default_factory=list)

    def to_dict(self) -> Dict[str, Any]:
        return asdict(self)
