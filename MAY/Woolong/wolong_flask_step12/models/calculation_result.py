from dataclasses import dataclass, field, asdict
from typing import Dict, Any, List, Optional, Union
from .model_number import ModelNumber
from .electrical import ElectricalResult
from .errors import ErrorResult


McaValue = Optional[Union[float, int, str]]


@dataclass
class AccessoryMcaRow:
    name: str = ""
    mca: McaValue = None
    mocp: McaValue = None
    disconnect: McaValue = None
    lra: McaValue = None
    single_point_box: str = ""
    single_point_box_hsccr: str = ""
    source: str = ""


@dataclass
class McaMocpResult:
    mca: McaValue = None
    mocp: McaValue = None
    mca_2: McaValue = None
    mocp_2: McaValue = None
    feeder: str = ""
    disconnect: McaValue = None
    disconnect_2: McaValue = None
    disconnect_lra: str = ""
    fuse: McaValue = None
    single_point_box: str = ""
    single_point_box_hsccr: str = ""
    num_wires: str = ""
    actual_num_wires: str = ""
    lra: McaValue = None
    calculation_notes: List[str] = field(default_factory=list)
    accessory_rows: List[AccessoryMcaRow] = field(default_factory=list)


@dataclass
class CalculationResult:
    model: ModelNumber = field(default_factory=ModelNumber)
    electrical: ElectricalResult = field(default_factory=ElectricalResult)
    mca_mocp: McaMocpResult = field(default_factory=McaMocpResult)
    errors: ErrorResult = field(default_factory=ErrorResult)
    debug: Dict[str, Any] = field(default_factory=dict)

    def to_dict(self) -> Dict[str, Any]:
        return asdict(self)
