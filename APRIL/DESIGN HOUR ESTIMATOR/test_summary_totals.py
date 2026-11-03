import unittest
from io import BytesIO
from unittest.mock import patch

import pandas as pd

from app import (
    app,
    calculate_summary_row,
    get_saved_project_summary,
    normalize_comment,
    rebuild_summary_from_cache,
)


class SavedProjectSummaryTests(unittest.TestCase):
    def test_dhe_summary_uses_current_l1_weight_factors(self):
        summary = calculate_summary_row(
            {
                "QBomSaved": "weights.csv",
                "Product Family": "TEST",
                "Modeling Hrs": 100,
                "Detailing Hrs": 80,
                "BOM Hrs": 20,
                "QC Hrs": 40,
            },
            phase=0,
            primaryquantity=1,
            secondaryquantity=2,
            tertiaryquantity=3,
        )

        # Effective multiplier: 1*1.00 + 2*0.25 + 3*0.10 = 1.80.
        self.assertEqual(summary["Modelling hours * Quantity"], 180)
        self.assertEqual(summary["Detailling Hours * Quantity"], 144)
        self.assertEqual(summary["BOM Hours * Quantity"], 36)
        self.assertEqual(summary["QC Hours * Quantity"], 72)
        self.assertEqual(summary["Design Hours * Quantity"], 360)
        self.assertEqual(summary["Total Hours (Primary L1s) * Quantity"], 240)
        self.assertEqual(summary["Secondary L1s"], 120)
        self.assertEqual(summary["Tertiary L1s"], 72)

    def test_complexity_reset_clears_estimator_comments(self):
        with app.test_client() as client:
            response = client.post(
                "/",
                data={
                    "action": "reset_complexity",
                    "team": "Sustaining",
                    "product_family": "SRT CH 3-5",
                    "qbom": "BOM BASEPAN O",
                    "row_count": "1",
                    "part_name_0": "HARNESS ASSY",
                    "set_0": "SET 8",
                    "low_qty_0": "2",
                    "med_qty_0": "1",
                    "complex_qty_0": "1",
                    "comments_0": "Remove this comment",
                    "save_file_name": "Project1",
                },
            )

        body = response.get_data(as_text=True)
        self.assertEqual(response.status_code, 200)
        self.assertNotIn("Remove this comment", body)
        self.assertIn('name="comments_0"', body)
        self.assertIn('value=""', body)

    def test_estimator_recalculation_preserves_save_name(self):
        with app.test_client() as client:
            response = client.post(
                "/",
                data={"action": "recalculate", "save_file_name": "Project1"},
            )

        self.assertEqual(response.status_code, 200)
        self.assertIn('value="Project1"', response.get_data(as_text=True))

    def test_summary_update_preserves_save_name(self):
        with app.test_client() as client:
            response = client.post(
                "/summary",
                data={"action": "update_summary", "save_file_name": "Summary_Project1"},
            )

        self.assertEqual(response.status_code, 200)
        self.assertIn('value="Summary_Project1"', response.get_data(as_text=True))

    def test_summary_cache_preserves_save_name(self):
        with app.test_client() as client:
            with client.session_transaction() as session:
                session["summary_cache"] = {"save_file_name": "Cached_Summary"}

            response = client.get("/summary")

        self.assertEqual(response.status_code, 200)
        self.assertIn('value="Cached_Summary"', response.get_data(as_text=True))

    def test_missing_comments_default_to_empty_string(self):
        self.assertEqual(normalize_comment(None), "")
        self.assertEqual(normalize_comment(float("nan")), "")
        self.assertEqual(normalize_comment(pd.NA), "")

    def test_loading_summary_prefills_project_name_and_missing_comments(self):
        csv_data = (
            "SummaryID,QBomSaved,Primary L1s Qty,Secondary L1s Qty,Tertiary L1s Qty\n"
            "loaded_project,,1,0,0\n"
        )

        with app.test_client() as client:
            response = client.post(
                "/summary",
                data={
                    "action": "load_csv",
                    "csv_file": (BytesIO(csv_data.encode("utf-8")), "loaded_project.csv"),
                },
                content_type="multipart/form-data",
            )

        body = response.get_data(as_text=True)
        self.assertEqual(response.status_code, 200)
        self.assertIn('value="loaded_project"', body)
        self.assertNotIn('value="nan"', body)

    def test_summary_comments_are_restored_from_cache(self):
        rows = rebuild_summary_from_cache({"comments_0": "Keep this note"})

        self.assertEqual(rows[0]["Comments"], "Keep this note")
        self.assertEqual(rows[1]["Comments"], "")

    def test_totals_row_is_not_counted_in_l1_calculations(self):
        rows = [
            {
                "UniqueID": "project",
                "Product Family": "SRT CH 3-5",
                "Modeling Hrs": 6.58,
                "Detailing Hrs": 6.58,
                "BOM Hrs": 1.74,
                "QC Hrs": 3.73,
                "TotalDesignHrs": 14.89,
                "Total Hrs": 18.62,
            },
            {
                "UniqueID": " totals ",
                "Product Family": "",
                "Modeling Hrs": 6.58,
                "Detailing Hrs": 6.58,
                "BOM Hrs": 1.74,
                "QC Hrs": 3.73,
                "TotalDesignHrs": 14.89,
                "Total Hrs": 18.62,
            },
        ]

        with patch("app.os.path.exists", return_value=True), patch(
            "app.pd.read_csv", return_value=pd.DataFrame(rows)
        ):
            project = get_saved_project_summary("unused", "project.csv")
            summary = calculate_summary_row(project, 0, 1, 1, 1)

        self.assertEqual(project["Total Hrs"], 18.62)
        self.assertEqual(summary["Total Hours (Primary L1s) * Quantity"], 18.63)
        self.assertEqual(summary["Secondary L1s"], 4.66)
        self.assertEqual(summary["Tertiary L1s"], 1.86)


if __name__ == "__main__":
    unittest.main()
