import pytest

from services.catalog_normalizer import normalize_catalog_number


@pytest.mark.parametrize(("source", "expected"), [
    ("30RC-2522S-1-----", "30RC-2522S-1-----"),
    (" 30rc_lg_condfan_001 ", "30RC_LG_CONDFAN_001"),
    ("30RC_LG_COND\nFAN_001", "30RC_LG_CONDFAN_001"),
    ("AB–12—CD", "AB-12-CD"),
    ("A B\tC\r\nD", "ABCD"),
])
def test_normalization(source: str, expected: str) -> None:
    assert normalize_catalog_number(source) == expected


def test_rejects_non_text() -> None:
    with pytest.raises(TypeError):
        normalize_catalog_number(123)  # type: ignore[arg-type]
