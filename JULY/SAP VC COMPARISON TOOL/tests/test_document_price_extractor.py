from decimal import Decimal
import fitz

from services.document_price_extractor import extract_document_price, looks_like_voltage
from services.pdf_extractor import extract_pdf, find_catalog_numbers


def _record(catalog: str, price: str = "1") -> dict[str, object]:
    return {
        "original_catalog_number": catalog,
        "normalized_catalog_number": catalog,
        "sap_price": Decimal(price),
        "original_price_text": price,
        "source_row": 1,
    }


def _make_synthetic_pdf() -> bytes:
    document = fitz.open()
    page = document.new_page(width=612, height=792)
    page.insert_text((70, 50), "CATALOG NUMBER", fontsize=10)
    page.insert_text((380, 50), "MASTER PRICE", fontsize=10)
    page.insert_text((70, 110), "TEST-BASE-001", fontsize=10)
    page.insert_text((230, 110), "460-3-60", fontsize=10)
    page.insert_text((390, 110), "$274,374.00", fontsize=10)

    page.insert_text((380, 190), "TEST_OPTION_001", fontsize=10)
    page.insert_text((390, 208), "6,896", fontsize=10)

    page.insert_text((380, 280), "TEST_OPTION_", fontsize=10)
    page.insert_text((380, 298), "002", fontsize=10)
    page.insert_text((390, 316), "1,866", fontsize=10)

    page.insert_text((250, 390), "TEST_AMBIG_001", fontsize=10)
    page.insert_text((390, 390), "4,000", fontsize=10)
    page.insert_text((425, 390), "5,000", fontsize=10)

    page.insert_text((250, 470), "TEST_INCLUDED_001", fontsize=10)
    page.insert_text((390, 470), "Included", fontsize=10)

    page.insert_text((70, 550), "TEST-ROW-A", fontsize=10)
    page.insert_text((390, 550), "9,000", fontsize=10)
    page.insert_text((70, 570), "TEST-ROW-B", fontsize=10)
    page.insert_text((390, 570), "8,000", fontsize=10)
    page.insert_text((70, 630), "TEST-NARROW-001", fontsize=10)
    page.insert_text((210, 630), "99,999", fontsize=10)
    page.insert_text((390, 630), "7,777", fontsize=10)
    page.insert_text((100, 680), "OTHER-A", fontsize=10)
    page.insert_text((390, 680), "30CF_CO", fontsize=10)
    page.insert_text((100, 698), "OTHER-B", fontsize=10)
    page.insert_text((390, 698), "NDENSER", fontsize=10)
    page.insert_text((100, 716), "OTHER-C", fontsize=10)
    page.insert_text((400, 716), "_004", fontsize=10)
    page.insert_text((405, 734), "1", fontsize=10)
    page.insert_text((300, 780), "Page 1", fontsize=9)
    data = document.tobytes()
    document.close()
    return data


def _results(pdf_data: bytes, catalogs: list[str]):
    pages = extract_pdf(pdf_data)
    records = [_record(catalog) for catalog in catalogs]
    matches = find_catalog_numbers(records, pages)
    all_occurrences = [occurrence for match in matches for occurrence in match["occurrences"]]
    extracted = [
        extract_document_price(catalog, match["occurrences"], pages, all_occurrences)
        for catalog, match in zip(catalogs, matches, strict=True)
    ]
    return matches, extracted


def test_rejects_voltage_pattern() -> None:
    assert looks_like_voltage("575-3-60")
    assert looks_like_voltage("208/230-3-60")


def test_same_row_prefers_currency_price_not_voltage() -> None:
    _, results = _results(_make_synthetic_pdf(), ["TEST-BASE-001"])
    assert results[0].document_price == Decimal("274374.00")
    assert results[0].selected_candidate is not None
    assert results[0].selected_candidate.strategy == "SAME_ROW"
    assert "currency formatted" in results[0].selected_candidate.reasons
    assert any("aligned under MASTER PRICE column" in reason for reason in results[0].selected_candidate.reasons)


def test_same_column_below_price() -> None:
    _, results = _results(_make_synthetic_pdf(), ["TEST_OPTION_001"])
    assert results[0].document_price == Decimal("6896")
    assert results[0].selected_candidate is not None
    assert results[0].selected_candidate.strategy == "SAME_CELL_BELOW"
    assert "selected during same cell search stage" in results[0].selected_candidate.reasons


def test_wrapped_catalog_and_price_below() -> None:
    matches, results = _results(_make_synthetic_pdf(), ["TEST_OPTION_002"])
    assert matches[0]["found"]
    assert len(matches[0]["occurrences"][0].matched_words) == 2
    assert results[0].document_price == Decimal("1866")
    assert results[0].selected_candidate is not None
    assert results[0].selected_candidate.strategy == "MULTILINE_CELL"


def test_ambiguous_nearby_prices_are_not_confirmed() -> None:
    _, results = _results(_make_synthetic_pdf(), ["TEST_AMBIG_001"])
    assert results[0].confidence == "AMBIGUOUS"


def test_included_is_preserved_as_nonnumeric() -> None:
    _, results = _results(_make_synthetic_pdf(), ["TEST_INCLUDED_001"])
    assert results[0].document_price is None
    assert results[0].document_raw_value == "Included"


def test_neighboring_row_price_ownership() -> None:
    _, results = _results(_make_synthetic_pdf(), ["TEST-ROW-A", "TEST-ROW-B"])
    assert results[0].document_price == Decimal("9000")
    assert results[1].document_price == Decimal("8000")
    assert all(result.document_raw_value != "1" for result in results)


def test_rejects_nearer_value_outside_master_price_column() -> None:
    _, results = _results(_make_synthetic_pdf(), ["TEST-NARROW-001"])
    assert results[0].document_price == Decimal("7777")
    assert results[0].document_raw_value == "7,777"
    assert all(candidate.raw_text != "99,999" for candidate in results[0].alternative_candidates)


def test_vertically_stacked_catalog_fragments_and_price_one() -> None:
    matches, results = _results(_make_synthetic_pdf(), ["30CF_CONDENSER_004"])
    assert matches[0]["found"]
    assert [word.text for word in matches[0]["occurrences"][0].matched_words] == [
        "30CF_CO", "NDENSER", "_004",
    ]
    assert results[0].document_price == Decimal("1")
    assert results[0].confidence in {"HIGH", "MEDIUM"}


def test_same_cell_stage_wins_before_same_row_candidate() -> None:
    document = fitz.open()
    page = document.new_page(width=612, height=792)
    page.insert_text((380, 50), "MASTER PRICE", fontsize=10)
    page.insert_text((350, 110), "TEST-CELL-001", fontsize=10)
    page.insert_text((430, 110), "$99,999", fontsize=10)
    page.insert_text((410, 128), "1", fontsize=10)
    data = document.tobytes()
    document.close()

    _, results = _results(data, ["TEST-CELL-001"])
    assert results[0].document_price == Decimal("1")
    assert results[0].selected_candidate is not None
    assert results[0].selected_candidate.strategy == "SAME_CELL_BELOW"
    assert any(candidate.raw_text == "$99,999" for candidate in results[0].alternative_candidates)


def test_wrapped_catalog_rejects_left_neighbor_and_uses_merged_header_cell() -> None:
    document = fitz.open()
    page = document.new_page(width=612, height=792)
    page.insert_text((375, 330), "MASTER PRICE", fontsize=10)
    page.insert_text((455, 370), "30CF_2MW_HAR", fontsize=10)
    page.insert_text((414, 388), "4", fontsize=10)
    page.insert_text((455, 388), "MONIC_001", fontsize=10)
    page.insert_text((470, 406), "$254,286", fontsize=10)
    data = document.tobytes()
    document.close()

    matches, results = _results(data, ["30CF_2MW_HARMONIC_001"])
    assert matches[0]["found"]
    assert results[0].document_price == Decimal("254286")
    assert results[0].document_raw_value == "$254,286"
    assert results[0].selected_candidate is not None
    assert results[0].selected_candidate.strategy == "MULTILINE_CELL"
    assert results[0].selected_candidate.raw_text != "4"


def test_stacked_master_price_header_finds_far_same_row_price() -> None:
    document = fitz.open()
    page = document.new_page(width=725, height=792)
    page.insert_text((570, 50), "MASTER", fontsize=10)
    page.insert_text((575, 65), "PRICE", fontsize=10)
    page.insert_text((80, 110), "30CF-5006H4--0110", fontsize=10)
    page.insert_text((350, 110), "460-3-60", fontsize=10)
    page.insert_text((565, 110), "$2,272,348", fontsize=10)
    data = document.tobytes()
    document.close()

    matches, results = _results(data, ["30CF-5006H4--0110"])
    assert matches[0]["found"]
    assert results[0].document_price == Decimal("2272348")
    assert results[0].document_raw_value == "$2,272,348"
    assert results[0].selected_candidate is not None
    assert results[0].selected_candidate.strategy == "SAME_ROW"


def test_unpasted_neighbor_catalog_ends_same_cell_search() -> None:
    document = fitz.open()
    page = document.new_page(width=612, height=792)
    page.insert_text((390, 50), "MASTER PRICE", fontsize=10)
    page.insert_text((380, 110), "TEST_ROW_001", fontsize=10)
    page.insert_text((405, 122), "19,759", fontsize=10)
    page.insert_text((380, 134), "TEST_ROW_002", fontsize=10)
    page.insert_text((405, 146), "38,826", fontsize=10)
    data = document.tobytes()
    document.close()

    _, results = _results(data, ["TEST_ROW_001"])
    assert results[0].document_price == Decimal("19759")
    assert results[0].confidence == "HIGH"
    assert results[0].selected_candidate is not None
    assert results[0].selected_candidate.strategy == "SAME_CELL_BELOW"
