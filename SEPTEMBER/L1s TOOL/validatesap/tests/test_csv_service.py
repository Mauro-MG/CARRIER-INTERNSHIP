import csv
import os
import shutil
import uuid
from pathlib import Path

from django.conf import settings
from django.test import SimpleTestCase

from validatesap.services.comparison import NEEDS_TO_BE_ADDED, NEEDS_TO_BE_DELETED, NO_CHANGE
from validatesap.services.csv_service import (
    CSV_FIELDS,
    CsvServiceError,
    InvalidSavedValidationError,
    InvalidTumblingNameError,
    ResultsFileExistsError,
    build_csv_rows,
    list_saved_validations,
    load_results_csv,
    result_filename,
    sanitize_filename,
    save_results_csv,
)
from validatesap.services.processing import process

from .test_services import SAP_HEADER, STANDARD_HEADER, sap_row, standard_row, valid_payload


def comparison_results(add_part="PN-ADD", delete_part="PN-DEL"):
    outcome = process(
        valid_payload(
            tumbling="30MPW017",
            adds=f"0030\t{add_part}\t2\tM",
            deletes=f"0020\t{delete_part}\t1",
            standard=f"{STANDARD_HEADER}\n{standard_row('PN-KEEP')}\n{standard_row(delete_part, '0020')}",
            sap=f"{SAP_HEADER}\n{sap_row('PN-KEEP')}\n{sap_row(delete_part, '0020')}",
        )
    )
    assert outcome.valid
    return outcome.results


class CsvServiceTests(SimpleTestCase):
    def setUp(self):
        self.directory = Path(settings.BASE_DIR) / ".test_saved_results" / uuid.uuid4().hex
        self.directory.mkdir(parents=True)

    def tearDown(self):
        shutil.rmtree(self.directory, ignore_errors=True)

    def test_filename_uses_trimmed_tumbling_name_and_csv_extension(self):
        self.assertEqual(result_filename("  30MPW017  "), "30MPW017.csv")

    def test_only_invalid_filename_characters_are_replaced(self):
        self.assertEqual(sanitize_filename('30M<P>W:01"7/\\|?*'), "30M_P_W_01_7_____")
        self.assertEqual(sanitize_filename("30-MP_W.017"), "30-MP_W.017")

    def test_missing_or_invalid_tumbling_name_is_rejected(self):
        for name in ("", "   ", "..."):
            with self.subTest(name=name), self.assertRaises(InvalidTumblingNameError):
                sanitize_filename(name)

    def test_rows_are_ordered_add_delete_no_change_and_keep_sap_ready_data(self):
        rows = build_csv_rows(comparison_results())
        statuses = [row["Status"] for row in rows]
        add_end = statuses.index("NEEDS TO BE DELETED FROM SAP")
        delete_end = statuses.index("NO CHANGE NEEDED")
        self.assertTrue(all(status == "NEEDS TO BE ADDED TO SAP" for status in statuses[:add_end]))
        self.assertTrue(all(status == "NEEDS TO BE DELETED FROM SAP" for status in statuses[add_end:delete_end]))
        self.assertTrue(all(status == "NO CHANGE NEEDED" for status in statuses[delete_end:]))
        self.assertEqual(rows[0]["SAP Ready Record"], "0030\tPN-ADD\t2\tM")
        self.assertEqual(next(row for row in rows if row["Status"] == "NEEDS TO BE DELETED FROM SAP")["SAP Ready Record"], "0020\tPN-DEL\t1")
        self.assertTrue(all(not row["SAP Ready Record"] for row in rows if row["Status"] == "NO CHANGE NEEDED"))

    def test_save_uses_utf8_bom_and_expected_columns(self):
        path = save_results_csv("30MPW017", comparison_results(), directory=self.directory)
        self.assertEqual(path.name, "30MPW017.csv")
        self.assertTrue(path.read_bytes().startswith(b"\xef\xbb\xbf"))
        with path.open(encoding="utf-8-sig", newline="") as stream:
            reader = csv.DictReader(stream)
            self.assertEqual(tuple(reader.fieldnames), CSV_FIELDS)
            self.assertGreater(len(list(reader)), 0)

    def test_no_comparison_results_cannot_be_saved(self):
        with self.assertRaises(CsvServiceError):
            save_results_csv("30MPW017", None, directory=self.directory)

    def test_existing_file_is_not_silently_overwritten(self):
        path = save_results_csv("30MPW017", comparison_results(), directory=self.directory)
        original = path.read_bytes()
        with self.assertRaises(ResultsFileExistsError):
            save_results_csv("30MPW017", comparison_results("PN-OTHER"), directory=self.directory)
        self.assertEqual(path.read_bytes(), original)

    def test_confirmed_overwrite_replaces_file(self):
        path = save_results_csv("30MPW017", comparison_results(), directory=self.directory)
        save_results_csv("30MPW017", comparison_results("PN-OTHER"), overwrite=True, directory=self.directory)
        self.assertIn("PN-OTHER", path.read_text(encoding="utf-8-sig"))

    def test_saved_file_can_reconstruct_grouped_results_and_counts(self):
        save_results_csv("30MPW017", comparison_results(), directory=self.directory)
        loaded = load_results_csv("30MPW017", directory=self.directory)
        self.assertEqual(loaded.counts[NEEDS_TO_BE_ADDED], 1)
        self.assertEqual(loaded.counts[NEEDS_TO_BE_DELETED], 1)
        self.assertGreaterEqual(loaded.counts[NO_CHANGE], 1)
        self.assertEqual(loaded.results[NEEDS_TO_BE_ADDED][0].record, "0030\tPN-ADD\t2\tM")

    def test_history_is_sorted_by_most_recent_modification(self):
        older = save_results_csv("OLDER", comparison_results(), directory=self.directory)
        newer = save_results_csv("NEWER", comparison_results(), directory=self.directory)
        os.utime(older, (100, 100))
        os.utime(newer, (200, 200))
        self.assertEqual([item.tumbling_name for item in list_saved_validations(directory=self.directory)], ["NEWER", "OLDER"])

    def test_invalid_csv_is_rejected_cleanly(self):
        (self.directory / "BROKEN.csv").write_text("Wrong,Columns\nA,B\n", encoding="utf-8-sig")
        with self.assertRaises(InvalidSavedValidationError):
            load_results_csv("BROKEN", directory=self.directory)

    def test_path_traversal_name_is_rejected(self):
        with self.assertRaises(InvalidTumblingNameError):
            load_results_csv("..", directory=self.directory)
