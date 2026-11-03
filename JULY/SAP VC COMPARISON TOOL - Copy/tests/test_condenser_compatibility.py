from __future__ import annotations

import pytest

from services.condenser_compatibility import (
    MPA,
    MPQ,
    MPW,
    is_condenser_compatible,
    normalize_condenser_family,
    parse_document_condenser_compatibility,
)


@pytest.mark.parametrize(
    "text",
    [
        "MPW/Q",
        "MPW / Q",
        "MPW/ Q",
        "MPW /Q",
        "MPW,Q",
        "MPW, Q",
        "MPW & MPQ",
        "MPW AND MPQ",
        "MPW OR MPQ",
    ],
)
def test_parse_mpw_q_variants(text: str) -> None:
    assert parse_document_condenser_compatibility(text) == {MPW, MPQ}


def test_parse_mpa() -> None:
    assert parse_document_condenser_compatibility("MPA") == {MPA}


def test_parse_combined_mpw_q_or_mpa() -> None:
    assert parse_document_condenser_compatibility("MPW/Q OR MPA") == {MPW, MPQ, MPA}


@pytest.mark.parametrize(
    ("value", "expected"),
    [
        ("MPW", MPW),
        ("MPQ", MPQ),
        ("MPA", MPA),
        ("30MPW", MPW),
        ("30MPQ", MPQ),
        ("30MPA", MPA),
        ("XMPWZ", None),
    ],
)
def test_normalize_product_family(value: str, expected: str | None) -> None:
    assert normalize_condenser_family(value) == expected


@pytest.mark.parametrize(
    ("product", "document", "expected"),
    [
        ("MPW", "MPW/Q", True),
        ("MPQ", "MPW/Q", True),
        ("MPA", "MPW/Q", False),
        ("MPW", "MPA", False),
        ("MPQ", "MPA", False),
        ("MPA", "MPA", True),
        ("MPW", "MPW", True),
        ("MPQ", "MPQ", True),
        ("MPW", "MPQ", False),
        ("MPQ", "MPW", False),
        ("MPW", "MPW/Q OR MPA", True),
        ("MPQ", "MPW/Q OR MPA", True),
        ("MPA", "MPW/Q OR MPA", True),
    ],
)
def test_compatibility_matrix(product: str, document: str, expected: bool) -> None:
    assert is_condenser_compatible(product, document) is expected
