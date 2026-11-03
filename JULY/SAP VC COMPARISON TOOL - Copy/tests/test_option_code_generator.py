from __future__ import annotations

import pytest

from services.option_code_generator import (
    OptionCodeError,
    generate_option_code_group,
    generate_option_code_range,
    sort_option_codes,
)


def test_generate_option_code_group_includes_base_then_a_through_z() -> None:
    codes = generate_option_code_group(1)

    assert codes[:4] == ["1", "1A", "1B", "1C"]
    assert codes[-1] == "1Z"
    assert len(codes) == 27


def test_generate_option_code_range_is_inclusive() -> None:
    assert generate_option_code_range(2, "2", "2F") == ["2", "2A", "2B", "2C", "2D", "2E", "2F"]
    assert generate_option_code_range(4, "4C", "4M") == [
        "4C",
        "4D",
        "4E",
        "4F",
        "4G",
        "4H",
        "4I",
        "4J",
        "4K",
        "4L",
        "4M",
    ]


def test_generate_option_code_range_rejects_reversed_range() -> None:
    with pytest.raises(OptionCodeError):
        generate_option_code_range(1, "1M", "1C")


def test_generate_option_code_range_must_stay_inside_group() -> None:
    with pytest.raises(OptionCodeError):
        generate_option_code_range(1, "1A", "2A")


def test_sort_option_codes_uses_natural_group_order() -> None:
    assert sort_option_codes(["10", "2A", "1Z", "2", "1"]) == ["1", "1Z", "2", "2A", "10"]
