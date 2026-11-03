from dataclasses import dataclass, field
from decimal import Decimal


@dataclass(frozen=True)
class PasteRecord:
    dataset: str
    row_number: int
    values: dict[str, str]
    original_line: str
    normalized_part_number: str
    quantity: Decimal | None = None

    @property
    def part_number(self) -> str:
        return self.values.get("part_number", "")

    @property
    def display_part_number(self) -> str:
        return self.part_number or "(missing part number)"


@dataclass(frozen=True)
class ValidationMessage:
    dataset: str
    message: str
    row_number: int | None = None
    part_number: str = ""
    code: str = "validation_error"
    severity: str = "error"


@dataclass
class ParseResult:
    dataset: str
    records: list[PasteRecord] = field(default_factory=list)
    messages: list[ValidationMessage] = field(default_factory=list)
    header_detected: bool = False


@dataclass(frozen=True)
class ComparisonItem:
    status: str
    normalized_part_number: str
    part_number: str
    record: str
    dataset: str
    reason: str
    values: dict[str, str] = field(default_factory=dict)
