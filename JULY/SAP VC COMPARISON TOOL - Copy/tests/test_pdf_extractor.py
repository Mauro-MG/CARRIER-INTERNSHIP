from decimal import Decimal

from services.pdf_extractor import ExtractedPage, PDFWord, TextBlock, find_catalog_numbers


def test_finds_single_line_and_wrapped_catalog_numbers() -> None:
    text = "Standard option 30RC-2522S-1----- available\nOption 30RC_LG_COND\nFAN_001 description"
    page = ExtractedPage(
        page_number=9,
        text=text,
        blocks=[TextBlock((0, 0, 100, 20), text)],
        words=[
            PDFWord((0, 0, 10, 10), "30RC-2522S-1-----", 0, 0, 0),
            PDFWord((0, 12, 10, 22), "30RC_LG_COND", 0, 1, 0),
            PDFWord((0, 24, 10, 34), "FAN_001", 0, 2, 0),
        ],
    )
    records = [
        {"original_catalog_number": "30RC-2522S-1-----", "normalized_catalog_number": "30RC-2522S-1-----", "sap_price": Decimal("398043"), "original_price_text": "398043", "source_row": 1},
        {"original_catalog_number": "30RC_LG_CONDFAN_001", "normalized_catalog_number": "30RC_LG_CONDFAN_001", "sap_price": Decimal("15436"), "original_price_text": "15436", "source_row": 2},
    ]
    matches = find_catalog_numbers(records, [page])
    assert [match["found"] for match in matches] == [True, True]
    assert matches[1]["pages_found"] == [9]
    assert matches[1]["contexts"]
