from __future__ import annotations

import re
from dataclasses import dataclass
from decimal import Decimal
from pathlib import Path
from typing import TypedDict

import fitz

from .catalog_normalizer import normalize_catalog_number
from .sap_input_parser import SAPRecord


class PDFExtractionError(RuntimeError):
    pass


@dataclass(frozen=True)
class TextBlock:
    bbox: tuple[float, float, float, float]
    text: str


@dataclass(frozen=True)
class PDFWord:
    bbox: tuple[float, float, float, float]
    text: str
    block_number: int
    line_number: int
    word_number: int
    page_number: int = 0

    @property
    def x0(self) -> float:
        return self.bbox[0]

    @property
    def y0(self) -> float:
        return self.bbox[1]

    @property
    def x1(self) -> float:
        return self.bbox[2]

    @property
    def y1(self) -> float:
        return self.bbox[3]

    @property
    def block_no(self) -> int:
        return self.block_number

    @property
    def line_no(self) -> int:
        return self.line_number

    @property
    def word_no(self) -> int:
        return self.word_number


@dataclass(frozen=True)
class CatalogOccurrence:
    normalized_catalog_number: str
    original_catalog_number: str
    page_number: int
    bounding_box: tuple[float, float, float, float]
    matched_words: list[PDFWord]
    block_number: int | None
    surrounding_words: list[PDFWord]


@dataclass(frozen=True)
class ExtractedPage:
    page_number: int
    text: str
    blocks: list[TextBlock]
    words: list[PDFWord]
    width: float = 0.0
    height: float = 0.0


class CatalogMatch(TypedDict):
    catalog_number: str
    sap_price: Decimal
    found: bool
    pages_found: list[int]
    occurrence_count: int
    contexts: list[str]
    occurrences: list[CatalogOccurrence]


def extract_pdf(pdf_path: str | Path | bytes, start_page: int = 1) -> list[ExtractedPage]:
    if start_page < 1:
        raise PDFExtractionError("Start Page must be 1 or greater.")
    try:
        document = fitz.open(stream=pdf_path, filetype="pdf") if isinstance(pdf_path, bytes) else fitz.open(str(pdf_path))
    except Exception as exc:
        raise PDFExtractionError("The uploaded file is not a readable PDF.") from exc

    try:
        if document.page_count == 0:
            raise PDFExtractionError("The uploaded PDF has no pages.")
        if start_page > document.page_count:
            raise PDFExtractionError(f"Start Page {start_page} exceeds the PDF's {document.page_count} pages.")
        pages: list[ExtractedPage] = []
        for index in range(start_page - 1, document.page_count):
            page = document.load_page(index)
            blocks = [
                TextBlock((float(b[0]), float(b[1]), float(b[2]), float(b[3])), str(b[4]))
                for b in page.get_text("blocks", sort=True)
                if str(b[4]).strip()
            ]
            words = [
                PDFWord(
                    (float(w[0]), float(w[1]), float(w[2]), float(w[3])),
                    str(w[4]), int(w[5]), int(w[6]), int(w[7]), index + 1,
                )
                for w in page.get_text("words", sort=True)
            ]
            pages.append(ExtractedPage(
                index + 1, page.get_text("text", sort=True), blocks, words,
                float(page.rect.width), float(page.rect.height),
            ))
        return pages
    except PDFExtractionError:
        raise
    except Exception as exc:
        raise PDFExtractionError("PDF text extraction failed.") from exc
    finally:
        document.close()


def _compact_with_map(text: str) -> tuple[str, list[int]]:
    compact: list[str] = []
    positions: list[int] = []
    for index, char in enumerate(text):
        normalized = normalize_catalog_number(char)
        if normalized:
            compact.append(normalized)
            positions.extend([index] * len(normalized))
    return "".join(compact), positions


def _context(text: str, positions: list[int], start: int, length: int, radius: int = 65) -> str:
    source_start = positions[start]
    source_end = positions[min(start + length - 1, len(positions) - 1)] + 1
    snippet = text[max(0, source_start - radius):min(len(text), source_end + radius)]
    return re.sub(r"\s+", " ", snippet).strip()


def _candidate_texts(page: ExtractedPage) -> list[str]:
    candidates: list[str] = []
    candidates.extend(block.text for block in page.blocks)
    lines = [line.strip() for line in page.text.splitlines() if line.strip()]
    candidates.extend(" ".join(lines[i:i + 3]) for i in range(len(lines)))
    if page.words:
        candidates.append(" ".join(word.text for word in page.words))
    return candidates


def _combined_bbox(words: list[PDFWord]) -> tuple[float, float, float, float]:
    return (
        min(word.x0 for word in words),
        min(word.y0 for word in words),
        max(word.x1 for word in words),
        max(word.y1 for word in words),
    )


def _build_occurrence(
    matched: list[PDFWord], target: str, original: str, page: ExtractedPage,
) -> CatalogOccurrence:
    bbox = _combined_bbox(matched)
    block_numbers = {item.block_number for item in matched}
    nearby = [
        item for item in page.words
        if item not in matched
        and item.x1 >= bbox[0] - 80 and item.x0 <= bbox[2] + 280
        and item.y1 >= bbox[1] - 45 and item.y0 <= bbox[3] + 110
    ]
    return CatalogOccurrence(
        normalized_catalog_number=target,
        original_catalog_number=original,
        page_number=page.page_number,
        bounding_box=bbox,
        matched_words=matched.copy(),
        block_number=next(iter(block_numbers)) if len(block_numbers) == 1 else None,
        surrounding_words=nearby,
    )


def _visual_stack_match(start: int, target: str, words: list[PDFWord]) -> list[PDFWord]:
    """Reconstruct a code split into vertically stacked, non-consecutive PDF words."""
    first = words[start]
    assembled = normalize_catalog_number(first.text)
    if not assembled or not target.startswith(assembled):
        return []
    matched = [first]
    while assembled != target and len(matched) < 12:
        previous = matched[-1]
        current_box = _combined_bbox(matched)
        possible: list[tuple[float, float, PDFWord, str]] = []
        for candidate in words:
            if candidate in matched or candidate.y0 <= previous.y0 + 2:
                continue
            vertical_gap = candidate.y0 - previous.y1
            if vertical_gap > max(36.0, (previous.y1 - previous.y0) * 3.5):
                continue
            fragment = normalize_catalog_number(candidate.text)
            if not fragment or not target.startswith(assembled + fragment):
                continue
            horizontal_overlap = max(0.0, min(current_box[2], candidate.x1) - max(current_box[0], candidate.x0))
            current_center = (current_box[0] + current_box[2]) / 2
            candidate_center = (candidate.x0 + candidate.x1) / 2
            if horizontal_overlap <= 0 and abs(candidate_center - current_center) > 28:
                continue
            possible.append((candidate.y0, abs(candidate_center - current_center), candidate, fragment))
        if not possible:
            return []
        _, _, selected, fragment = min(possible, key=lambda item: (item[0], item[1]))
        matched.append(selected)
        assembled += fragment
    return matched if assembled == target else []


def find_catalog_occurrences(
    normalized_catalog_number: str,
    original_catalog_number: str,
    pages: list[ExtractedPage],
) -> list[CatalogOccurrence]:
    """Locate exact normalized catalog codes as one or more consecutive PDF words."""
    occurrences: list[CatalogOccurrence] = []
    target_length = len(normalized_catalog_number)
    for page in pages:
        words = page.words
        for start in range(len(words)):
            assembled = ""
            matched: list[PDFWord] = []
            for index in range(start, min(len(words), start + 12)):
                word = words[index]
                assembled += normalize_catalog_number(word.text)
                matched.append(word)
                if assembled == normalized_catalog_number:
                    occurrences.append(_build_occurrence(
                        matched, normalized_catalog_number, original_catalog_number, page
                    ))
                    break
                if len(assembled) >= target_length:
                    break
            visual_match = _visual_stack_match(start, normalized_catalog_number, words)
            if visual_match:
                occurrences.append(_build_occurrence(
                    visual_match, normalized_catalog_number, original_catalog_number, page
                ))
    unique: dict[tuple[int, tuple[float, float, float, float]], CatalogOccurrence] = {}
    for occurrence in occurrences:
        unique[(occurrence.page_number, occurrence.bounding_box)] = occurrence
    return list(unique.values())


def find_catalog_numbers(records: list[SAPRecord], pages: list[ExtractedPage], context_limit: int = 3) -> list[CatalogMatch]:
    results: list[CatalogMatch] = []
    prepared_pages = [
        (
            page,
            (page.text, *_compact_with_map(page.text)),
            [(source, *_compact_with_map(source)) for source in _candidate_texts(page)],
        )
        for page in pages
    ]

    for record in records:
        target = record["normalized_catalog_number"]
        catalog_occurrences = find_catalog_occurrences(target, record["original_catalog_number"], pages)
        pages_found: set[int] = set()
        occurrences: set[tuple[int, str]] = set()
        contexts: list[str] = []
        for page, primary, fallback_candidates in prepared_pages:
            source, compact, positions = primary
            candidates = [primary] if target in compact else fallback_candidates
            for source, compact, positions in candidates:
                offset = 0
                while True:
                    found_at = compact.find(target, offset)
                    if found_at < 0:
                        break
                    snippet = _context(source, positions, found_at, len(target))
                    key = (page.page_number, snippet)
                    if key not in occurrences:
                        occurrences.add(key)
                        pages_found.add(page.page_number)
                        if len(contexts) < context_limit:
                            contexts.append(f"Page {page.page_number}: {snippet}")
                    offset = found_at + max(1, len(target))
        results.append({
            "catalog_number": record["original_catalog_number"],
            "sap_price": record["sap_price"],
            "found": bool(occurrences or catalog_occurrences),
            "pages_found": sorted(pages_found | {item.page_number for item in catalog_occurrences}),
            "occurrence_count": len(catalog_occurrences) if catalog_occurrences else len(occurrences),
            "contexts": contexts,
            "occurrences": catalog_occurrences,
        })
    return results
