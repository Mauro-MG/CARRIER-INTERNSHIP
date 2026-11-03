import tempfile
import unittest
from pathlib import Path

import pandas as pd

from generate_estimated_tasks import (
    RAW_ESTIMATED_TIME_COLUMN,
    SCHEDULE_GROUP_COLUMN,
    build_tasks,
    l1_quantity_multiplier,
    load_project,
    reconcile_and_split_task_rows,
)


class EstimatedTaskGenerationTests(unittest.TestCase):
    def test_correct_l1_quantity_multiplier(self):
        self.assertEqual(l1_quantity_multiplier(1, 2, 4), 1.9)
        self.assertEqual(l1_quantity_multiplier(0, 2, 0), 0.5)
        self.assertEqual(l1_quantity_multiplier(0, 0, 4), 0.4)

    def test_project_finds_sibling_qbom_and_generates_eight_tasks(self):
        with tempfile.TemporaryDirectory(dir=Path.cwd()) as temp_dir:
            root = Path(temp_dir)
            projects = root / "Projects"
            qboms = root / "Qboms"
            projects.mkdir()
            qboms.mkdir()

            project_path = projects / "Demo.csv"
            pd.DataFrame(
                [
                    {
                        "SummaryID": "Demo",
                        "QBomSaved": "Section_A.csv",
                        "Primary L1s Qty": 1,
                        "Secondary L1s Qty": 2,
                        "Tertiary L1s Qty": 4,
                        "Product Family": "V-SERIES",
                    }
                ]
            ).to_csv(project_path, index=False)

            pd.DataFrame(
                [
                    {"UniqueID": "Section_A", "qBOM": "BOM INTAKE", "SET": "SET 1", "Modeling Hrs": 10, "Detailing Hrs": 4, "BOM Hrs": 1},
                    {"UniqueID": "Section_A", "qBOM": "BOM INTAKE", "SET": "SET 6", "Modeling Hrs": 6, "Detailing Hrs": 2, "BOM Hrs": 0.5},
                    {"UniqueID": "Section_A", "qBOM": "BOM INTAKE", "SET": "SET 8", "Modeling Hrs": 8, "Detailing Hrs": 3, "BOM Hrs": 1},
                ]
            ).to_csv(qboms / "Section_A.csv", index=False)

            project, excel = load_project(project_path)
            tasks, audit, components = build_tasks(project, project_path, excel)

            self.assertEqual(len(tasks), 8)
            self.assertEqual(tasks[SCHEDULE_GROUP_COLUMN].nunique(), 1)
            self.assertTrue(tasks[SCHEDULE_GROUP_COLUMN].iloc[0].endswith(":Section_A.csv"))
            self.assertEqual(audit[0]["Multiplier"], 1.9)
            self.assertEqual(tasks["Estimated time"].tolist(), [19, 11, 15, 7, 4, 6, 2, 3])
            self.assertEqual(tasks["Estimated time"].sum(), 67)
            self.assertEqual(len(components), 8)
            prt = components.iloc[0]
            self.assertEqual(prt["Combined base hours"], 10.0)
            self.assertEqual(prt["Primary hours"], 10.0)
            self.assertEqual(prt["Secondary hours"], 5.0)
            self.assertEqual(prt["Tertiary hours"], 4.0)
            self.assertEqual(prt["Estimated time"], 19.0)
            bom_wt = components.iloc[-1]
            self.assertEqual(bom_wt["PRT base hours"], 1.0)
            self.assertEqual(bom_wt["ASSY base hours"], 0.5)
            self.assertEqual(bom_wt["Estimated time"], 2.85)
            bom_wt_task = tasks[tasks["Name"].str.endswith("_BOM/WT")].iloc[0]
            self.assertEqual(bom_wt_task["Labels"], "WTPART")
            self.assertEqual(bom_wt_task[RAW_ESTIMATED_TIME_COLUMN], 2.85)

    def test_estimated_time_over_40_splits_into_capped_rows(self):
        with tempfile.TemporaryDirectory(dir=Path.cwd()) as temp_dir:
            root = Path(temp_dir)
            projects = root / "Projects"
            qboms = root / "Qboms"
            projects.mkdir()
            qboms.mkdir()

            project_path = projects / "Large.csv"
            pd.DataFrame(
                [
                    {
                        "SummaryID": "Large",
                        "QBomSaved": "Large_Section.csv",
                        "Primary L1s Qty": 1,
                        "Secondary L1s Qty": 0,
                        "Tertiary L1s Qty": 0,
                        "Product Family": "V-SERIES",
                    }
                ]
            ).to_csv(project_path, index=False)

            pd.DataFrame(
                [
                    {
                        "UniqueID": "Large_Section",
                        "qBOM": "LARGE SECTION",
                        "SET": "SET 1",
                        "Modeling Hrs": 45.4,
                        "Detailing Hrs": 0,
                        "BOM Hrs": 0,
                    }
                ]
            ).to_csv(qboms / "Large_Section.csv", index=False)

            project, excel = load_project(project_path)
            tasks, _, components = build_tasks(project, project_path, excel)

            prt_tasks = tasks[tasks["Name"].str.contains("_PRT")]
            self.assertEqual(prt_tasks["Name"].tolist(), [
                "Large_Large_Section_LARGE SECTION_PRT_1",
                "Large_Large_Section_LARGE SECTION_PRT_2",
            ])
            self.assertEqual(prt_tasks["Estimated time"].tolist(), [40, 5])
            self.assertEqual(prt_tasks[SCHEDULE_GROUP_COLUMN].nunique(), 1)
            self.assertTrue((tasks["Estimated time"] <= 40).all())
            self.assertEqual(components.iloc[0]["Estimated time"], 45.4)

    def test_integer_allocation_preserves_the_rounded_raw_total_before_splitting(self):
        rows = [
            {"Name": "A", "Estimated time": 1.4},
            {"Name": "B", "Estimated time": 1.4},
            {"Name": "C", "Estimated time": 1.4},
        ]

        reconciled = reconcile_and_split_task_rows(rows)

        self.assertEqual([row["Estimated time"] for row in reconciled], [2, 1, 1])
        self.assertEqual(sum(row["Estimated time"] for row in reconciled), 4)

    def test_total_is_preserved_when_reconciled_value_is_split_at_40(self):
        reconciled = reconcile_and_split_task_rows([
            {"Name": "Large", "Estimated time": 40.6},
            {"Name": "Small", "Estimated time": 0.6},
        ])

        self.assertEqual([row["Estimated time"] for row in reconciled], [40, 1, 0])
        self.assertEqual([row["Name"] for row in reconciled], ["Large_1", "Large_2", "Small"])
        self.assertEqual(reconciled[-1][RAW_ESTIMATED_TIME_COLUMN], 0.6)
        self.assertEqual(sum(row["Estimated time"] for row in reconciled), 41)


if __name__ == "__main__":
    unittest.main()
