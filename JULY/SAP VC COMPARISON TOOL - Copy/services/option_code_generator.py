from __future__ import annotations

import re


OPTION_CODE_PATTERN = re.compile(r"^(?P<group>[1-9]|1[0-9]|20)(?P<letter>[A-Z])?$")
OPTION_CODE_LETTERS = tuple("ABCDEFGHIJKLMNOPQRSTUVWXYZ")


class OptionCodeError(ValueError):
    """Raised when an option-code group or range cannot be generated."""


def generate_option_code_group(group_number: int) -> list[str]:
    """Return the base option code plus A-Z suffixes for one numeric group."""
    _validate_group_number(group_number)
    base = str(group_number)
    return [base, *[f"{base}{letter}" for letter in OPTION_CODE_LETTERS]]


def generate_option_code_range(group_number: int, start_code: str, end_code: str) -> list[str]:
    """Return an inclusive natural-order range inside one numeric option-code group."""
    _validate_group_number(group_number)
    group_codes = generate_option_code_group(group_number)
    normalized_start = normalize_option_code(start_code)
    normalized_end = normalize_option_code(end_code)

    start_group = parse_option_code(normalized_start)[0]
    end_group = parse_option_code(normalized_end)[0]
    if start_group != group_number or end_group != group_number:
        raise OptionCodeError(
            f"Range {normalized_start} through {normalized_end} must stay inside group {group_number}."
        )

    start_index = group_codes.index(normalized_start)
    end_index = group_codes.index(normalized_end)
    if start_index > end_index:
        raise OptionCodeError(f"Range start {normalized_start} cannot come after end {normalized_end}.")
    return group_codes[start_index : end_index + 1]


def sort_option_codes(option_codes: list[str]) -> list[str]:
    """Sort option codes by numeric group first, then base value, then A-Z."""
    return sorted((normalize_option_code(code) for code in option_codes), key=option_code_sort_key)


def normalize_option_code(option_code: str) -> str:
    return str(option_code).strip().upper()


def parse_option_code(option_code: str) -> tuple[int, str | None]:
    normalized = normalize_option_code(option_code)
    match = OPTION_CODE_PATTERN.fullmatch(normalized)
    if not match:
        raise OptionCodeError(f"Invalid option code: {option_code}")
    return int(match.group("group")), match.group("letter")


def option_code_sort_key(option_code: str) -> tuple[int, int]:
    group, letter = parse_option_code(option_code)
    suffix_order = 0 if letter is None else OPTION_CODE_LETTERS.index(letter) + 1
    return group, suffix_order


def _validate_group_number(group_number: int) -> None:
    if group_number < 1 or group_number > 20:
        raise OptionCodeError("Option-code group must be between 1 and 20.")
