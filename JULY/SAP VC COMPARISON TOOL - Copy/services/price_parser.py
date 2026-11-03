from __future__ import annotations

import re
from dataclasses import dataclass
from decimal import Decimal, InvalidOperation

NUMERIC_PRICE = "NUMERIC_PRICE"
STANDARD = "STANDARD"
NO_CHARGE = "NO_CHARGE"
INCLUDED = "INCLUDED"
NOT_AVAILABLE = "NOT_AVAILABLE"
NONE_VALUE = "NONE"
DASH = "DASH"
INVALID = "INVALID"


@dataclass(frozen=True)
class ParsedDocumentValue:
    raw_text: str
    value_type: str
    decimal_value: Decimal | None


_SPECIAL_VALUES = {
    "STD": STANDARD,
    "STD.": STANDARD,
    "STANDARD": STANDARD,
    "NC": NO_CHARGE,
    "N/C": NO_CHARGE,
    "NO CHARGE": NO_CHARGE,
    "INCLUDED": INCLUDED,
    "N/A": NOT_AVAILABLE,
    "NA": NOT_AVAILABLE,
    "NONE": NONE_VALUE,
    "-": DASH,
    "—": DASH,
    "–": DASH,
}

_NUMBER_PATTERN = re.compile(
    r"^(?P<open>\()?\s*\$?\s*(?P<number>(?:\d{1,3}(?:,\d{3})+|\d+)(?:\.\d+)?)\s*(?P<close>\))?$"
)


def parse_document_value(raw_text: str) -> ParsedDocumentValue:
    raw = raw_text
    text = raw_text.strip()
    special = _SPECIAL_VALUES.get(" ".join(text.upper().split()))
    if special:
        return ParsedDocumentValue(raw, special, None)

    match = _NUMBER_PATTERN.fullmatch(text)
    if not match or bool(match.group("open")) != bool(match.group("close")):
        return ParsedDocumentValue(raw, INVALID, None)
    try:
        value = Decimal(match.group("number").replace(",", ""))
    except InvalidOperation:
        return ParsedDocumentValue(raw, INVALID, None)
    if match.group("open"):
        value = -value
    return ParsedDocumentValue(raw, NUMERIC_PRICE, value)
