from dataclasses import dataclass, field, asdict
from typing import Dict, Any, List


@dataclass
class AppMessage:
    code: str
    message: str
    severity: str = "error"  # error, warning, info
    source: str = "python"


@dataclass
class ErrorResult:
    """Python equivalent of VBA Error_Type, but easier to serialize."""
    clear: bool = True
    end: bool = False
    messages: List[AppMessage] = field(default_factory=list)

    def add(self, code: str, message: str, severity: str = "error", source: str = "python") -> None:
        self.clear = False if severity == "error" else self.clear
        self.messages.append(AppMessage(code=code, message=message, severity=severity, source=source))
        if severity == "error":
            self.end = True

    def to_dict(self) -> Dict[str, Any]:
        return asdict(self)
