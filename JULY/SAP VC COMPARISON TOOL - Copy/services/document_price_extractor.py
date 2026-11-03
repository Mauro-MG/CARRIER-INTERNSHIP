from __future__ import annotations

import math
import re
from dataclasses import dataclass, field
from decimal import Decimal

from .pdf_extractor import CatalogOccurrence, ExtractedPage, PDFWord
from .price_parser import INVALID, NUMERIC_PRICE, ParsedDocumentValue, parse_document_value

SCORE_WEIGHTS = {
    "same_row": 42.0,
    "right_of_catalog": 18.0,
    "same_block": 13.0,
    "below_overlap": 38.0,
    "nearby": 9.0,
    "close": 12.0,
    "currency": 9.0,
    "thousands_separator": 6.0,
    "master_price_column": 30.0,
    "multiline_below": 12.0,
    "plain_text_fallback": 18.0,
    "small_quantity": -28.0,
    "label_penalty": -32.0,
    "header_footer": -55.0,
    "closer_catalog": -48.0,
    "far": -18.0,
}

MASTER_PRICE_COLUMN_TOLERANCE = 48.0

HIGH_THRESHOLD = 70.0
MEDIUM_THRESHOLD = 48.0
LOW_THRESHOLD = 25.0
AMBIGUITY_MARGIN = 6.0

_VOLTAGE = re.compile(r"^(?:\d{3}(?:/\d{3})?-\d-\d{2})$")
_DATE = re.compile(r"^(?:\d{1,2}[/.-]){2}\d{2,4}$")
_CONTEXT_LABELS = {"PAGE", "POSITION", "POS", "QTY", "QUANTITY", "VOLTAGE", "SIZE"}
_FALLBACK_TOKEN = re.compile(
    r"\(\s*\$?\s*\d[\d,]*(?:\.\d+)?\s*\)|\$?\d[\d,]*(?:\.\d+)?|"
    r"No\s+Charge|Standard|Std\.?|Included|N/A|N/C|NC|NA|None|[—-]",
    re.IGNORECASE,
)


@dataclass
class PriceCandidate:
    raw_text: str
    parsed_value: Decimal | None
    value_type: str
    page_number: int
    bounding_box: tuple[float, float, float, float]
    strategy: str
    distance: float
    score: float
    reasons: list[str] = field(default_factory=list)
    surrounding_text: str = ""


@dataclass
class DocumentPriceResult:
    catalog_number: str
    found: bool
    document_value_type: str | None
    document_price: Decimal | None
    document_raw_value: str | None
    page_number: int | None
    confidence: str
    score: float | None
    candidate_count: int
    alternative_candidates: list[PriceCandidate]
    evidence_text: str
    selected_candidate: PriceCandidate | None = None
    selected_occurrence: CatalogOccurrence | None = None


def looks_like_voltage(text: str) -> bool:
    return bool(_VOLTAGE.fullmatch(text.strip()))


def _bbox(words: list[PDFWord]) -> tuple[float, float, float, float]:
    return (
        min(word.x0 for word in words), min(word.y0 for word in words),
        max(word.x1 for word in words), max(word.y1 for word in words),
    )


def _center(box: tuple[float, float, float, float]) -> tuple[float, float]:
    return ((box[0] + box[2]) / 2, (box[1] + box[3]) / 2)


def _overlap_x(a: tuple[float, float, float, float], b: tuple[float, float, float, float]) -> float:
    overlap = max(0.0, min(a[2], b[2]) - max(a[0], b[0]))
    return overlap / max(1.0, min(a[2] - a[0], b[2] - b[0]))


def _candidate_word_groups(page: ExtractedPage) -> list[tuple[list[PDFWord], ParsedDocumentValue]]:
    groups: list[tuple[list[PDFWord], ParsedDocumentValue]] = []
    for index, word in enumerate(page.words):
        parsed = parse_document_value(word.text)
        if parsed.value_type != INVALID:
            groups.append(([word], parsed))
        if index + 1 < len(page.words):
            following = page.words[index + 1]
            if following.block_number == word.block_number and abs(following.y0 - word.y0) < 4:
                combined = f"{word.text} {following.text}"
                parsed_pair = parse_document_value(combined)
                if parsed_pair.value_type != INVALID:
                    groups.append(([word, following], parsed_pair))
    return groups


def _surrounding_text(page: ExtractedPage, box: tuple[float, float, float, float]) -> str:
    nearby = [
        word.text for word in page.words
        if word.x1 >= box[0] - 90 and word.x0 <= box[2] + 120
        and word.y1 >= box[1] - 24 and word.y0 <= box[3] + 24
    ]
    return " ".join(nearby[:30])


def _master_price_column_distance(page: ExtractedPage, box: tuple[float, float, float, float]) -> float | None:
    """Return horizontal distance to the nearest valid MASTER PRICE column header."""
    candidate_center = _center(box)[0]
    distances: list[float] = []
    for price_word in page.words:
        if price_word.text.strip() not in {"PRICE", "PRICES"} or price_word.y1 > box[1]:
            continue
        if any(
            word.text.strip() == "MASTER"
            and (
                (
                    abs(_center(word.bbox)[1] - _center(price_word.bbox)[1]) <= 4
                    and 0 <= price_word.x0 - word.x1 <= 90
                )
                or (
                    0 <= price_word.y0 - word.y1 <= 32
                    and abs(_center(word.bbox)[0] - _center(price_word.bbox)[0]) <= 45
                )
            )
            for word in page.words
        ):
            distances.append(abs(_center(price_word.bbox)[0] - candidate_center))
    return min(distances) if distances else None


def _closer_to_other_catalog(
    box: tuple[float, float, float, float], occurrence: CatalogOccurrence,
    all_occurrences: list[CatalogOccurrence],
) -> bool:
    candidate_center = _center(box)
    current = math.dist(candidate_center, _center(occurrence.bounding_box))
    for other in all_occurrences:
        if other is occurrence or other.page_number != occurrence.page_number:
            continue
        if math.dist(candidate_center, _center(other.bounding_box)) + 8 < current:
            return True
    return False


def _same_cell_below(
    box: tuple[float, float, float, float], occurrence: CatalogOccurrence,
    all_occurrences: list[CatalogOccurrence], page: ExtractedPage,
) -> bool:
    catalog_box = occurrence.bounding_box
    vertical_gap = box[1] - catalog_box[3]
    average_word_height = sum(word.y1 - word.y0 for word in occurrence.matched_words) / max(
        1, len(occurrence.matched_words)
    )
    center_distance = abs(_center(box)[0] - _center(catalog_box)[0])
    horizontally_aligned = _overlap_x(box, catalog_box) >= 0.25 or center_distance <= 48
    if vertical_gap < -2 or vertical_gap > max(28.0, average_word_height * 2.5) or not horizontally_aligned:
        return False
    known_catalog_boundary = any(
        other is not occurrence
        and other.page_number == occurrence.page_number
        and other.bounding_box[1] > catalog_box[3]
        and other.bounding_box[1] < box[1]
        and (_overlap_x(other.bounding_box, catalog_box) >= 0.2 or abs(_center(other.bounding_box)[0] - _center(catalog_box)[0]) <= 48)
        for other in all_occurrences
    )
    if known_catalog_boundary:
        return False
    for word in page.words:
        if word in occurrence.matched_words or word.y0 <= catalog_box[3] or word.y0 >= box[1]:
            continue
        normalized = word.text.strip().upper()
        looks_catalog_like = (
            len(normalized) >= 6
            and any(character.isalpha() for character in normalized)
            and any(character.isdigit() for character in normalized)
            and ("_" in normalized or "-" in normalized)
        )
        aligned = _overlap_x(word.bbox, catalog_box) >= 0.2 or abs(
            _center(word.bbox)[0] - _center(catalog_box)[0]
        ) <= 48
        if looks_catalog_like and aligned:
            return False
    return True


def score_candidate(
    parsed: ParsedDocumentValue,
    words: list[PDFWord],
    occurrence: CatalogOccurrence,
    page: ExtractedPage,
    all_occurrences: list[CatalogOccurrence],
) -> PriceCandidate | None:
    if any(word in occurrence.matched_words for word in words):
        return None
    raw_text = parsed.raw_text.strip()
    if looks_like_voltage(raw_text) or _DATE.fullmatch(raw_text):
        return None

    box = _bbox(words)
    catalog_box = occurrence.bounding_box
    same_cell_below = _same_cell_below(box, occurrence, all_occurrences, page)
    master_price_column_distance = _master_price_column_distance(page, box)
    if master_price_column_distance is None:
        return None
    if master_price_column_distance > MASTER_PRICE_COLUMN_TOLERANCE and not same_cell_below:
        return None
    cx, cy = _center(box)
    catalog_cx, catalog_cy = _center(catalog_box)
    distance = math.dist((cx, cy), (catalog_cx, catalog_cy))
    average_catalog_word_height = sum(word.y1 - word.y0 for word in occurrence.matched_words) / max(
        1, len(occurrence.matched_words)
    )
    vertical_tolerance = max(4.0, average_catalog_word_height * 0.75)
    same_row = abs(cy - catalog_cy) <= vertical_tolerance
    right = box[0] >= catalog_box[2] - 2
    below = box[1] >= catalog_box[3] - 2 and box[1] - catalog_box[3] <= 100
    overlap = _overlap_x(box, catalog_box)
    same_row = same_row and (right or overlap >= 0.25)
    same_block = occurrence.block_number is not None and all(
        word.block_number == occurrence.block_number for word in words
    )
    nearby = box[0] <= catalog_box[2] + 250 and box[2] >= catalog_box[0] - 35 \
        and box[1] <= catalog_box[3] + 100 and box[3] >= catalog_box[1] - 30
    if not (same_row or (below and overlap >= 0.25) or same_block or nearby):
        return None

    score = 0.0
    reasons: list[str] = []
    strategy = "NEARBY_WORDS"
    if same_row:
        score += SCORE_WEIGHTS["same_row"]
        reasons.append("same visual row")
        strategy = "SAME_ROW"
    if right and same_row:
        score += SCORE_WEIGHTS["right_of_catalog"]
        reasons.append("positioned to the right")
    if below and overlap >= 0.25:
        score += SCORE_WEIGHTS["below_overlap"]
        reasons.append("directly below with horizontal overlap")
        strategy = "SAME_COLUMN_BELOW"
        if same_cell_below:
            reasons.append("inside the catalog's apparent table cell")
            strategy = "SAME_CELL_BELOW"
        matched_line_positions = {round(_center(word.bbox)[1], 1) for word in occurrence.matched_words}
        if len(matched_line_positions) > 1:
            score += SCORE_WEIGHTS["multiline_below"]
            reasons.append("below a wrapped catalog code")
            if same_cell_below:
                strategy = "MULTILINE_CELL"
    if same_block:
        score += SCORE_WEIGHTS["same_block"]
        reasons.append("same text block")
    if nearby:
        score += SCORE_WEIGHTS["nearby"]
        reasons.append("inside local search rectangle")
    if distance <= 90:
        score += SCORE_WEIGHTS["close"]
        reasons.append("short geometric distance")
    elif distance > 220:
        score += SCORE_WEIGHTS["far"]
        reasons.append("far from catalog")
    if "$" in raw_text:
        score += SCORE_WEIGHTS["currency"]
        reasons.append("currency formatted")
    if "," in raw_text:
        score += SCORE_WEIGHTS["thousands_separator"]
        reasons.append("thousands separator")

    context = _surrounding_text(page, box)
    context_upper = context.upper()
    score += SCORE_WEIGHTS["master_price_column"]
    if master_price_column_distance <= MASTER_PRICE_COLUMN_TOLERANCE:
        reasons.append(f"aligned under MASTER PRICE column ({master_price_column_distance:.1f} pt)")
    else:
        reasons.append("same-cell ownership within a merged MASTER PRICE header")
    neighboring_tokens = set(re.findall(r"[A-Z]+", context_upper))
    if neighboring_tokens & _CONTEXT_LABELS:
        score += SCORE_WEIGHTS["label_penalty"]
        reasons.append("near quantity/position/voltage label")
    if page.height and (box[1] < page.height * 0.055 or box[3] > page.height * 0.94):
        score += SCORE_WEIGHTS["header_footer"]
        reasons.append("header or footer region")
    if parsed.value_type == NUMERIC_PRICE and parsed.decimal_value in {Decimal("0"), Decimal("1"), Decimal("2"), Decimal("3")}:
        score += SCORE_WEIGHTS["small_quantity"]
        reasons.append("small integer resembles quantity")
    if _closer_to_other_catalog(box, occurrence, all_occurrences):
        score += SCORE_WEIGHTS["closer_catalog"]
        reasons.append("closer to another catalog occurrence")

    return PriceCandidate(
        raw_text=raw_text,
        parsed_value=parsed.decimal_value,
        value_type=parsed.value_type,
        page_number=page.page_number,
        bounding_box=box,
        strategy=strategy,
        distance=round(distance, 2),
        score=round(score, 2),
        reasons=reasons,
        surrounding_text=context,
    )


def generate_price_candidates(
    occurrence: CatalogOccurrence,
    page: ExtractedPage,
    all_occurrences: list[CatalogOccurrence],
) -> list[PriceCandidate]:
    deduplicated: dict[tuple[str, tuple[float, float, float, float]], PriceCandidate] = {}
    for words, parsed in _candidate_word_groups(page):
        candidate = score_candidate(parsed, words, occurrence, page, all_occurrences)
        if candidate is None:
            continue
        key = (candidate.raw_text.upper(), candidate.bounding_box)
        previous = deduplicated.get(key)
        if previous is None or candidate.score > previous.score:
            deduplicated[key] = candidate
    return sorted(deduplicated.values(), key=lambda item: item.score, reverse=True)


def _plain_text_fallback(occurrence: CatalogOccurrence, page: ExtractedPage) -> list[PriceCandidate]:
    lines = [line.strip() for line in page.text.splitlines() if line.strip()]
    target = occurrence.normalized_catalog_number
    candidates: list[PriceCandidate] = []
    for index in range(len(lines)):
        window = " ".join(lines[index:index + 3])
        compact_window = re.sub(r"\s+", "", window).upper()
        if target not in compact_window:
            continue
        nearby_lines = lines[index:min(len(lines), index + 5)]
        evidence = " ".join(nearby_lines)
        for line in nearby_lines[1:]:
            for match in _FALLBACK_TOKEN.finditer(line):
                parsed = parse_document_value(match.group(0))
                if parsed.value_type == INVALID or looks_like_voltage(match.group(0)):
                    continue
                candidates.append(PriceCandidate(
                    raw_text=parsed.raw_text.strip(), parsed_value=parsed.decimal_value,
                    value_type=parsed.value_type, page_number=page.page_number,
                    bounding_box=occurrence.bounding_box, strategy="PLAIN_TEXT_FALLBACK",
                    distance=0.0, score=LOW_THRESHOLD,
                    reasons=["plain-text fallback only"], surrounding_text=evidence,
                ))
        break
    return candidates


def extract_document_price(
    catalog_number: str,
    occurrences: list[CatalogOccurrence],
    pages: list[ExtractedPage],
    all_occurrences: list[CatalogOccurrence],
) -> DocumentPriceResult:
    page_by_number = {page.page_number: page for page in pages}
    candidates_with_occurrence: list[tuple[PriceCandidate, CatalogOccurrence]] = []
    for occurrence in occurrences:
        page = page_by_number.get(occurrence.page_number)
        if page:
            coordinate_candidates = generate_price_candidates(occurrence, page, all_occurrences)
            candidates_with_occurrence.extend((candidate, occurrence) for candidate in coordinate_candidates)
    candidates_with_occurrence.sort(key=lambda item: item[0].score, reverse=True)
    credible = [item for item in candidates_with_occurrence if item[0].score >= LOW_THRESHOLD]
    if not credible:
        return DocumentPriceResult(catalog_number, False, None, None, None, None, "NOT_FOUND", None, len(candidates_with_occurrence), [item[0] for item in candidates_with_occurrence[:5]], "No credible local document value candidate was found.")

    same_cell = [item for item in credible if item[0].strategy in {"SAME_CELL_BELOW", "MULTILINE_CELL"}]
    same_row = [item for item in credible if item[0].strategy == "SAME_ROW"]
    selection_pool = same_cell or same_row or credible
    selection_stage = "same cell" if same_cell else "same visual row" if same_row else "local geometry"
    best, selected_occurrence = selection_pool[0]
    best.reasons.append(f"selected during {selection_stage} search stage")
    alternative_candidates = [
        item[0] for item in candidates_with_occurrence
        if item[0] is not best
    ][:5]
    confidence = "LOW"
    if len(selection_pool) > 1 and abs(best.score - selection_pool[1][0].score) <= AMBIGUITY_MARGIN \
            and (best.raw_text != selection_pool[1][0].raw_text or best.page_number != selection_pool[1][0].page_number):
        confidence = "AMBIGUOUS"
    elif best.score >= HIGH_THRESHOLD:
        confidence = "HIGH"
    elif best.score >= MEDIUM_THRESHOLD:
        confidence = "MEDIUM"
    evidence = f"Page {best.page_number}: {best.surrounding_text}"
    return DocumentPriceResult(
        catalog_number=catalog_number,
        found=True,
        document_value_type=best.value_type,
        document_price=best.parsed_value,
        document_raw_value=best.raw_text,
        page_number=best.page_number,
        confidence=confidence,
        score=best.score,
        candidate_count=len(candidates_with_occurrence),
        alternative_candidates=alternative_candidates,
        evidence_text=evidence,
        selected_candidate=best,
        selected_occurrence=selected_occurrence,
    )
