from django.test import SimpleTestCase
from django.urls import reverse

from .test_services import SAP_HEADER, STANDARD_HEADER, sap_row, standard_row


class IndexViewTests(SimpleTestCase):
    def test_get_renders_all_five_paste_areas(self):
        response = self.client.get(reverse("validatesap:index"))
        self.assertEqual(response.status_code, 200)
        for field in ("tumbling", "adds", "deletes", "standard", "sap"):
            self.assertContains(response, f'name="{field}"')
        self.assertContains(response, 'name="tumbling"')
        self.assertContains(response, 'maxlength="5"')
        self.assertEqual(response.content.decode().count("<textarea"), 4)

    def test_invalid_post_retains_input_and_hides_action_results(self):
        response = self.client.post(
            reverse("validatesap:index"),
            {"tumbling": "", "adds": "0010\tPN-BAD\tbad\tR", "deletes": "", "standard": "", "sap": ""},
        )
        self.assertContains(response, "Validation stopped")
        self.assertContains(response, "PN-BAD")
        self.assertNotContains(response, "Comparison complete")

    def test_valid_post_shows_counts_and_preserves_action_record(self):
        add_line = "0030\tPN-NEW\t2\tM"
        response = self.client.post(
            reverse("validatesap:index"),
            {
                "tumbling": "",
                "adds": add_line,
                "deletes": "",
                "standard": f"{STANDARD_HEADER}\n{standard_row('PN-KEEP')}",
                "sap": f"{SAP_HEADER}\n{sap_row('PN-KEEP')}",
            },
        )
        self.assertContains(response, "Comparison complete")
        self.assertContains(response, "PN-NEW")
        self.assertContains(response, add_line)
        self.assertContains(response, "No deletions needed")
