from dataclasses import dataclass

from .comparison import compare
from .parsers import extract_tumbling_name, parse_all
from .records import ComparisonItem, ValidationMessage
from .validators import validate


@dataclass
class ProcessingResult:
    valid: bool
    errors: list[ValidationMessage]
    results: dict[str, list[ComparisonItem]] | None
    record_counts: dict[str, int]
    tumbling_name: str = ""


def process(payload: dict[str, str]) -> ProcessingResult:
    parsed = parse_all(payload)
    tumbling_name = extract_tumbling_name(payload.get("tumbling", ""), parsed["tumbling"])
    errors = validate(parsed)
    counts = {dataset: len(result.records) for dataset, result in parsed.items()}
    if errors:
        return ProcessingResult(valid=False, errors=errors, results=None, record_counts=counts, tumbling_name=tumbling_name)
    return ProcessingResult(valid=True, errors=[], results=compare(parsed), record_counts=counts, tumbling_name=tumbling_name)
