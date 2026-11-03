import re
from decimal import Decimal, InvalidOperation


def clean_cell(value: str | None) -> str:
    return (value or "").strip()


def normalize_part_number(value: str | None) -> str:
    """Make matching case-insensitive and ignore pasted whitespace only."""
    return re.sub(r"\s+", "", clean_cell(value)).upper()


def normalize_header(value: str | None) -> str:
    return re.sub(r"[^a-z0-9]", "", clean_cell(value).lower())


def parse_quantity(value: str | None) -> Decimal | None:
    cleaned = clean_cell(value).replace(",", "")
    if not cleaned:
        return None
    try:
        return Decimal(cleaned)
    except InvalidOperation:
        return None


def normalize_source_code(value: str | None) -> str:
    cleaned = clean_cell(value)
    if not cleaned:
        return ""
    try:
        number = Decimal(cleaned)
        if number == number.to_integral_value():
            return str(int(number))
    except InvalidOperation:
        pass
    return cleaned.upper()


def derive_source(source_code_1: str, source_code_2: str) -> str | None:
    pair = (normalize_source_code(source_code_1), normalize_source_code(source_code_2))
    return {("", ""): "R", ("50", "50"): "M", ("0", "0"): "B"}.get(pair)
