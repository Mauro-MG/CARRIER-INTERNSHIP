from django.test import SimpleTestCase

from validatesap.services.comparison import NEEDS_TO_BE_ADDED, NEEDS_TO_BE_DELETED, NO_CHANGE
from validatesap.services.normalization import normalize_part_number
from validatesap.services.parsers import extract_tumbling_name, parse_dataset
from validatesap.services.processing import process


STANDARD_HEADER = "Level\tItem\tPart Number\tDescription\tQuantity"
SAP_HEADER = "Level\tItem\tPart Number\tDescription\tQty\tUnit\tPGr\tSC1\tSC2"


def standard_row(part, item="0010", quantity="1", description="Component"):
    return f"1\t{item}\t{part}\t{description}\t{quantity}"


def sap_row(part, item="0010", quantity="1", sc1="", sc2="", description="Component"):
    return f"1\t{item}\t{part}\t{description}\t{quantity}\tEA\t001\t{sc1}\t{sc2}"


def valid_payload(**overrides):
    payload = {
        "tumbling": "",
        "adds": "",
        "deletes": "",
        "standard": f"{STANDARD_HEADER}\n{standard_row('PN-KEEP')}",
        "sap": f"{SAP_HEADER}\n{sap_row('PN-KEEP')}",
    }
    payload.update(overrides)
    return payload


class NormalizationTests(SimpleTestCase):
    def test_part_matching_ignores_case_and_all_pasted_whitespace(self):
        self.assertEqual(normalize_part_number("  pn - 10\t01 "), "PN-1001")

    def test_original_record_is_preserved(self):
        original = "0010\t Pn-10 01 \t2\tR"
        parsed = parse_dataset("adds", original)
        self.assertEqual(parsed.records[0].original_line, original)
        self.assertEqual(parsed.records[0].normalized_part_number, "PN-1001")

    def test_tumbling_name_is_extracted_from_inline_label(self):
        self.assertEqual(extract_tumbling_name("Tumbling Name: 30MPW017"), "30MPW017")

    def test_tumbling_name_is_extracted_from_tabular_label(self):
        self.assertEqual(extract_tumbling_name("Tumbling Name\t30MPW021"), "30MPW021")

    def test_tumbling_name_falls_back_to_first_parsed_value(self):
        self.assertEqual(extract_tumbling_name("  38MURA005  "), "38MURA005")


class ProcessingTests(SimpleTestCase):
    def test_valid_inputs_produce_all_three_exclusive_categories(self):
        payload = valid_payload(
            adds="0010\tPN-ADD\t1\tR",
            deletes="0020\tPN-DEL\t1",
            standard=f"{STANDARD_HEADER}\n{standard_row('PN-KEEP')}\n{standard_row('PN-DEL', '0020')}",
            sap=f"{SAP_HEADER}\n{sap_row('PN-KEEP')}\n{sap_row('PN-DEL', '0020')}",
        )
        outcome = process(payload)
        self.assertTrue(outcome.valid)
        self.assertEqual([item.normalized_part_number for item in outcome.results[NEEDS_TO_BE_ADDED]], ["PN-ADD"])
        self.assertEqual([item.normalized_part_number for item in outcome.results[NEEDS_TO_BE_DELETED]], ["PN-DEL"])
        self.assertEqual([item.normalized_part_number for item in outcome.results[NO_CHANGE]], ["PN-KEEP"])

        categorized = [item.normalized_part_number for items in outcome.results.values() for item in items]
        self.assertEqual(len(categorized), len(set(categorized)))

    def test_delete_rule_has_priority_when_part_exists(self):
        outcome = process(valid_payload(deletes="0010\tPN-KEEP\t1"))
        self.assertTrue(outcome.valid)
        self.assertEqual(outcome.results[NEEDS_TO_BE_DELETED][0].normalized_part_number, "PN-KEEP")
        self.assertFalse(outcome.results[NO_CHANGE])

    def test_add_is_no_change_when_already_in_standard_or_sap(self):
        outcome = process(valid_payload(adds="0010\tpn-keep\t1\tR"))
        self.assertTrue(outcome.valid)
        self.assertFalse(outcome.results[NEEDS_TO_BE_ADDED])
        self.assertEqual(outcome.results[NO_CHANGE][0].normalized_part_number, "PN-KEEP")

    def test_delete_is_no_change_when_absent_from_standard_and_sap(self):
        outcome = process(valid_payload(deletes="0990\tPN-ABSENT\t1"))
        self.assertTrue(outcome.valid)
        self.assertEqual({item.normalized_part_number for item in outcome.results[NO_CHANGE]}, {"PN-ABSENT", "PN-KEEP"})

    def test_empty_adds_and_deletes_are_valid_empty_states(self):
        outcome = process(valid_payload())
        self.assertTrue(outcome.valid)
        self.assertEqual(outcome.results[NEEDS_TO_BE_ADDED], [])
        self.assertEqual(outcome.results[NEEDS_TO_BE_DELETED], [])

    def test_windows_line_endings_and_headers_are_supported(self):
        outcome = process(
            valid_payload(
                standard=f"{STANDARD_HEADER}\r\n{standard_row('PN-KEEP')}",
                sap=f"{SAP_HEADER}\r\n{sap_row('PN-KEEP', sc1='50.0', sc2='50')}",
            )
        )
        self.assertTrue(outcome.valid)

    def test_add_delete_conflict_is_blocking_and_produces_no_results(self):
        outcome = process(valid_payload(adds="0010\tPN-X\t1\tR", deletes="0010\tpn-x\t1"))
        self.assertFalse(outcome.valid)
        self.assertIsNone(outcome.results)
        self.assertIn("add_delete_conflict", {error.code for error in outcome.errors})

    def test_duplicate_sap_part_is_blocking(self):
        sap = f"{SAP_HEADER}\n{sap_row('PN-KEEP')}\n{sap_row(' pn-keep ', '0020')}"
        outcome = process(valid_payload(sap=sap))
        self.assertFalse(outcome.valid)
        self.assertIn("duplicate_part_number", {error.code for error in outcome.errors})

    def test_malformed_row_and_missing_part_number_are_reported(self):
        outcome = process(valid_payload(adds="0010\t\t1"))
        codes = {error.code for error in outcome.errors}
        self.assertFalse(outcome.valid)
        self.assertIn("malformed_row", codes)
        self.assertIn("missing_part_number", codes)

    def test_missing_required_item_is_reported(self):
        outcome = process(valid_payload(deletes="\tPN-KEEP\t1"))
        self.assertFalse(outcome.valid)
        self.assertIn("missing_required_field", {error.code for error in outcome.errors})

    def test_non_numeric_and_non_positive_quantities_are_blocking(self):
        outcome = process(
            valid_payload(
                standard=f"{STANDARD_HEADER}\n{standard_row('PN-KEEP', quantity='not-a-number')}",
                sap=f"{SAP_HEADER}\n{sap_row('PN-KEEP', quantity='0')}",
            )
        )
        self.assertFalse(outcome.valid)
        self.assertGreaterEqual(sum(error.code == "invalid_quantity" for error in outcome.errors), 2)

    def test_invalid_sap_source_pair_is_blocking(self):
        outcome = process(valid_payload(sap=f"{SAP_HEADER}\n{sap_row('PN-KEEP', sc1='50', sc2='0')}"))
        self.assertFalse(outcome.valid)
        self.assertIn("invalid_source_pair", {error.code for error in outcome.errors})

    def test_invalid_add_source_is_blocking(self):
        outcome = process(valid_payload(adds="0010\tPN-ADD\t1\tX"))
        self.assertFalse(outcome.valid)
        self.assertIn("invalid_add_source", {error.code for error in outcome.errors})

    def test_required_standard_and_sap_inputs_are_enforced(self):
        outcome = process({"tumbling": "", "adds": "", "deletes": "", "standard": "", "sap": ""})
        self.assertFalse(outcome.valid)
        self.assertEqual(sum(error.code == "missing_dataset" for error in outcome.errors), 2)

    def test_tumbling_is_parsed_but_only_receives_no_change(self):
        outcome = process(valid_payload(tumbling="PN-TUMBLE"))
        self.assertTrue(outcome.valid)
        self.assertIn("PN-TUMBLE", {item.normalized_part_number for item in outcome.results[NO_CHANGE]})
