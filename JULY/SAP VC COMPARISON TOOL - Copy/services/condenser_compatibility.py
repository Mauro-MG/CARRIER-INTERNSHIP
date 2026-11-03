from __future__ import annotations

import re


MPW = "MPW"
MPQ = "MPQ"
MPA = "MPA"
ALL_CONDENSERS = "ALL"
VALID_CONDENSER_FAMILIES = {MPW, MPQ, MPA}

_DIRECT_FAMILY_RE = re.compile(r"(?<![A-Z0-9])(?:30)?(MP[WAQ])(?![A-Z0-9])")
_MPW_Q_GROUP_RE = re.compile(r"(?<![A-Z0-9])MPW\s*(?:/|,)\s*Q(?![A-Z0-9])")
_ALL_RE = re.compile(r"(?<![A-Z0-9])ALL(?:\s+(?:MODELS?|CONDENSERS?|PRODUCTS?|UNITS?))?(?![A-Z0-9])")


def normalize_condenser_family(value: str) -> str | None:
    """Normalize explicit product-family values to MPW, MPQ, or MPA."""
    normalized = _normalize_text(value)
    if not normalized:
        return None
    match = _DIRECT_FAMILY_RE.search(normalized)
    if not match:
        return None
    family = match.group(1)
    return family if family in VALID_CONDENSER_FAMILIES else None


def parse_document_condenser_compatibility(value: str) -> set[str]:
    """Parse Carrier row compatibility text into canonical product families.

    Empty text returns an empty set. The DOCX extractor treats that as no explicit
    restriction in contexts where blank compatibility means universal applicability.
    """
    normalized = _normalize_text(value)
    if not normalized:
        return set()

    families: set[str] = set()
    if _ALL_RE.search(normalized):
        families.add(ALL_CONDENSERS)

    if _MPW_Q_GROUP_RE.search(normalized):
        families.update({MPW, MPQ})

    for match in _DIRECT_FAMILY_RE.finditer(normalized):
        family = match.group(1)
        if family in VALID_CONDENSER_FAMILIES:
            families.add(family)

    return families


def is_condenser_compatible(product_family: str | None, document_value: str) -> bool:
    """Return whether a product family is compatible with a DOCX row label."""
    family = normalize_condenser_family(product_family or "")
    if family is None:
        return True
    document_families = parse_document_condenser_compatibility(document_value)
    if not document_families or ALL_CONDENSERS in document_families:
        return True
    return family in document_families


def format_condenser_families(families: set[str]) -> str:
    if not families:
        return "ALL"
    if ALL_CONDENSERS in families:
        return "ALL"
    return ", ".join(family for family in (MPW, MPQ, MPA) if family in families)


def _normalize_text(value: str) -> str:
    text = str(value or "").upper()
    text = text.replace("\u2013", "-").replace("\u2014", "-")
    text = re.sub(r"\s+", " ", text)
    return text.strip()
