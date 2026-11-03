import os
import shutil
import uuid
from pathlib import Path
from unittest.mock import patch

from django.conf import settings
from django.core.cache import cache
from django.test import SimpleTestCase, override_settings
from django.urls import reverse

from validatesap.services.csv_service import save_results_csv

from .test_csv_service import comparison_results
from .test_services import SAP_HEADER, STANDARD_HEADER, sap_row, standard_row


class SaveAndHistoryViewTests(SimpleTestCase):
    def setUp(self):
        self.directory = Path(settings.BASE_DIR) / ".test_saved_results" / uuid.uuid4().hex
        self.directory.mkdir(parents=True)
        self.settings_override = override_settings(
            SAVE_RESULTS_DIR=self.directory,
            CACHES={
                "default": {
                    "BACKEND": "django.core.cache.backends.locmem.LocMemCache",
                    "LOCATION": f"validatesap-{self._testMethodName}",
                }
            },
        )
        self.settings_override.enable()
        cache.clear()

    def tearDown(self):
        cache.clear()
        self.settings_override.disable()
        shutil.rmtree(self.directory, ignore_errors=True)

    def _payload(self, tumbling="Tumbling Name: 30MPW017", add_part="PN-NEW"):
        return {
            "tumbling": tumbling,
            "adds": f"0030\t{add_part}\t2\tR",
            "deletes": "0020\tPN-DEL\t1",
            "standard": f"{STANDARD_HEADER}\n{standard_row('PN-KEEP')}\n{standard_row('PN-DEL', '0020')}",
            "sap": f"{SAP_HEADER}\n{sap_row('PN-KEEP')}\n{sap_row('PN-DEL', '0020')}",
        }

    def _comparison_response(self, **payload_overrides):
        payload = self._payload()
        payload.update(payload_overrides)
        return self.client.post(reverse("validatesap:index"), payload)

    def test_main_page_has_secondary_history_action(self):
        response = self.client.get(reverse("validatesap:index"))
        self.assertContains(response, "View past validations")
        self.assertContains(response, reverse("validatesap:history"))

    def test_successful_comparison_with_name_has_save_button_and_sanitized_filename(self):
        response = self._comparison_response(tumbling="Tumbling Name: 30MPW:017")
        self.assertContains(response, "Save results CSV")
        self.assertContains(response, "30MPW_017.csv")
        self.assertTrue(response.context["save_token"])

    def test_missing_tumbling_name_prevents_saving_but_keeps_comparison(self):
        response = self._comparison_response(tumbling="")
        self.assertContains(response, "Comparison complete")
        self.assertContains(response, "Unable to save results because the Tumbling name could not be identified")
        self.assertNotContains(response, "Save results CSV")

    def test_failed_validation_has_no_save_snapshot(self):
        response = self._comparison_response(standard="")
        self.assertContains(response, "Validation stopped")
        self.assertIsNone(response.context["save_token"])
        self.assertNotContains(response, "Save results CSV")

    def test_save_writes_the_exact_cached_result_without_rerunning_comparison(self):
        response = self._comparison_response()
        token = response.context["save_token"]
        with patch("validatesap.views.process") as comparison:
            saved = self.client.post(reverse("validatesap:save_results"), {"result_token": token, "action": "save"})
        comparison.assert_not_called()
        self.assertContains(saved, "Results saved successfully")
        self.assertIn("PN-NEW", (self.directory / "30MPW017.csv").read_text(encoding="utf-8-sig"))

    def test_existing_file_requires_confirmation_and_cancel_does_not_overwrite(self):
        response = self._comparison_response()
        token = response.context["save_token"]
        self.client.post(reverse("validatesap:save_results"), {"result_token": token, "action": "save"})
        path = self.directory / "30MPW017.csv"
        original = path.read_bytes()

        confirmation = self.client.post(reverse("validatesap:save_results"), {"result_token": token, "action": "save"})
        self.assertContains(confirmation, "Do you want to replace the existing file?")
        cancelled = self.client.post(reverse("validatesap:save_results"), {"result_token": token, "action": "cancel"})
        self.assertContains(cancelled, "existing CSV was not changed")
        self.assertEqual(path.read_bytes(), original)

    def test_confirmed_overwrite_replaces_existing_csv(self):
        first = self._comparison_response()
        self.client.post(reverse("validatesap:save_results"), {"result_token": first.context["save_token"], "action": "save"})
        second = self._comparison_response(adds="0030\tPN-REPLACEMENT\t2\tR")
        token = second.context["save_token"]
        self.client.post(reverse("validatesap:save_results"), {"result_token": token, "action": "save"})
        replaced = self.client.post(reverse("validatesap:save_results"), {"result_token": token, "action": "overwrite"})
        self.assertContains(replaced, "Results saved successfully")
        content = (self.directory / "30MPW017.csv").read_text(encoding="utf-8-sig")
        self.assertIn("PN-REPLACEMENT", content)
        self.assertNotIn("PN-NEW,", content)

    def test_missing_or_expired_snapshot_cannot_be_saved(self):
        response = self.client.post(reverse("validatesap:save_results"), {"result_token": "missing", "action": "save"})
        self.assertEqual(response.status_code, 400)
        self.assertContains(response, "missing or has expired", status_code=400)

    def test_history_lists_csvs_newest_first_without_extension_and_with_search(self):
        older = save_results_csv("OLDER", comparison_results(), directory=self.directory)
        newer = save_results_csv("NEWER", comparison_results(), directory=self.directory)
        os.utime(older, (100, 100))
        os.utime(newer, (200, 200))
        response = self.client.get(reverse("validatesap:history"))
        content = response.content.decode()
        self.assertLess(content.index("NEWER"), content.index("OLDER"))
        self.assertNotIn("NEWER.csv", content)
        self.assertContains(response, 'placeholder="Search Tumbling..."')
        self.assertContains(response, "data-history-row")

    def test_history_empty_state_is_explanatory(self):
        response = self.client.get(reverse("validatesap:history"))
        self.assertContains(response, "No past validations have been saved yet")
        self.assertContains(response, "New validation")

    def test_history_search_finds_partial_case_insensitive_tumbling_name(self):
        save_results_csv("30MPW017", comparison_results(), directory=self.directory)
        save_results_csv("38MURA005", comparison_results(), directory=self.directory)
        response = self.client.get(reverse("validatesap:history"), {"q": "30mp"})
        self.assertContains(response, "30MPW017")
        self.assertNotContains(response, "38MURA005")

    def test_history_detail_groups_counts_and_preserves_copy_records_without_reprocessing(self):
        save_results_csv("30MPW017", comparison_results(), directory=self.directory)
        with patch("validatesap.views.process") as comparison, patch("validatesap.services.validators.validate") as validator:
            response = self.client.get(reverse("validatesap:history_detail", args=["30MPW017"]))
        comparison.assert_not_called()
        validator.assert_not_called()
        self.assertContains(response, "Past validation")
        self.assertContains(response, "Copy adds")
        self.assertContains(response, "Copy deletes")
        self.assertContains(response, "0030\tPN-ADD\t2\tM")
        self.assertContains(response, "0020\tPN-DEL\t1")
        self.assertContains(response, '<details class="no-change-panel">')
        self.assertNotContains(response, '<details class="no-change-panel" open>')

    def test_missing_history_file_is_handled(self):
        response = self.client.get(reverse("validatesap:history_detail", args=["MISSING"]))
        self.assertEqual(response.status_code, 404)
        self.assertContains(response, "could not be found", status_code=404)

    def test_invalid_history_csv_is_handled(self):
        (self.directory / "BROKEN.csv").write_text("Wrong,Columns\nA,B\n", encoding="utf-8-sig")
        response = self.client.get(reverse("validatesap:history_detail", args=["BROKEN"]))
        self.assertEqual(response.status_code, 422)
        self.assertContains(response, "invalid or incomplete", status_code=422)

    def test_path_traversal_identifier_cannot_open_files(self):
        response = self.client.get(reverse("validatesap:history_detail", args=[".."]))
        self.assertIn(response.status_code, {404, 422})
        self.assertNotContains(response, "SECRET OUTSIDE CONTENT", status_code=response.status_code)
