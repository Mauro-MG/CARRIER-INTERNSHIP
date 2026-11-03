import csv
import json
import tempfile
import unittest
from datetime import date
from pathlib import Path

from asana_task_app import (
    ASANA_EXPORT_COLUMNS,
    DEFAULT_OPTIONS,
    DRAFT_FORMAT,
    MANIFEST_FORMAT,
    RAW_ESTIMATED_TIME_COLUMN,
    SCHEDULE_GROUP_COLUMN,
    TaskTableModel,
    add_workdays,
    build_draft_document,
    build_export_manifest,
    calculate_qbom_schedule,
    export_csv,
    load_draft_document,
    review_notes,
    write_json_document,
)


class AsanaTaskAppTests(unittest.TestCase):
    def test_canonical_asana_headers_have_exact_names_capitalization_and_order(self):
        self.assertEqual(
            ASANA_EXPORT_COLUMNS,
            [
                "Name",
                "Description",
                "Assignee",
                "Due Date",
                "Priority",
                "Project",
                "Status",
                "Labels",
                "Estimated Time",
                "ECN",
                "Task Type",
            ],
        )
        self.assertEqual(len(ASANA_EXPORT_COLUMNS), len(set(ASANA_EXPORT_COLUMNS)))

    def test_export_csv_uses_requested_headers_only(self):
        with tempfile.TemporaryDirectory(dir=Path.cwd()) as temp_dir:
            output_path = Path(temp_dir) / "asana.csv"
            model = TaskTableModel()
            model.add(
                {
                    "Name": "Internal generated task name",
                    "Assignee": "JessicaJanett.Gonzalez@carrier.com",
                    "Product": "ART",
                    "Priority": "High",
                    "Due Date": "2026-09-14",
                    "Project": "DOAS",
                    "Status": "Pending",
                    "Labels": "PRT",
                    "Estimated Time": "40.0",
                    "Task Type": "SW",
                    "Description": "",
                }
            )

            export_csv(output_path, model.to_export_records())

            with output_path.open(newline="", encoding="utf-8-sig") as csv_file:
                reader = csv.DictReader(csv_file)
                self.assertEqual(reader.fieldnames, ASANA_EXPORT_COLUMNS)
                rows = list(reader)

            self.assertEqual(len(rows), 1)
            self.assertEqual(rows[0]["Name"], "Internal generated task name")
            self.assertEqual(rows[0]["Assignee"], "JessicaJanett.Gonzalez@carrier.com")
            self.assertEqual(rows[0]["Due Date"], "09/14/2026")
            self.assertEqual(rows[0]["Estimated Time"], "40")
            self.assertEqual(rows[0]["Description"], "")
            self.assertNotIn("Product", reader.fieldnames)

    def test_export_maps_legacy_bom_wt_label_to_asana_wtpart(self):
        with tempfile.TemporaryDirectory(dir=Path.cwd()) as temp_dir:
            output_path = Path(temp_dir) / "asana.csv"
            model = TaskTableModel()
            model.add({"Name": "Weight task", "Labels": "BOM/WT"})

            export_csv(output_path, model.to_export_records())

            with output_path.open(newline="", encoding="utf-8-sig") as csv_file:
                row = next(csv.DictReader(csv_file))

            self.assertEqual(row["Labels"], "WTPART")
            self.assertNotIn("Target Date", ASANA_EXPORT_COLUMNS)

    def test_zero_hour_decimal_fallback_exports_ceiling_integer_minutes(self):
        with tempfile.TemporaryDirectory(dir=Path.cwd()) as temp_dir:
            output_path = Path(temp_dir) / "asana.csv"
            model = TaskTableModel()
            model.add({
                "Name": "Small task",
                "Product": "ART",
                "Estimated Time": "0",
                SCHEDULE_GROUP_COLUMN: "A",
                RAW_ESTIMATED_TIME_COLUMN: "0.32",
            })

            records = model.to_export_records()
            export_csv(output_path, records)

            with output_path.open(newline="", encoding="utf-8-sig") as csv_file:
                row = next(csv.DictReader(csv_file))
            self.assertEqual(records[0]["Estimated Time"], "20 min")
            self.assertEqual(row["Estimated Time"], "20 min")

    def test_versioned_draft_round_trip_restores_tasks_options_and_source(self):
        with tempfile.TemporaryDirectory(dir=Path.cwd()) as temp_dir:
            draft_path = Path(temp_dir) / "shared.asana-draft.json"
            document = build_draft_document(
                [{
                    "Name": "Task A",
                    "Product": "ART",
                    "Estimated Time": "12",
                    SCHEDULE_GROUP_COLUMN: "2:Section_A.csv",
                    RAW_ESTIMATED_TIME_COLUMN: "11.75",
                }],
                DEFAULT_OPTIONS,
                {"path": "Projects/Example.xlsx", "sha256": "abc123"},
                schedule={"start_date": "09/28/2026", "target_date": "09/29/2026"},
                history_actions=["batch edit Status"],
            )
            write_json_document(draft_path, document)

            tasks, options, source, schedule = load_draft_document(draft_path)

            self.assertEqual(document["format"], DRAFT_FORMAT)
            self.assertEqual(tasks[0]["Name"], "Task A")
            self.assertEqual(tasks[0]["Product"], "ART")
            self.assertNotIn("Product", options)
            self.assertEqual(source["sha256"], "abc123")
            self.assertEqual(tasks[0][SCHEDULE_GROUP_COLUMN], "2:Section_A.csv")
            self.assertEqual(tasks[0][RAW_ESTIMATED_TIME_COLUMN], "11.75")
            self.assertEqual(schedule["target_date"], "09/29/2026")

    def test_qbom_schedule_runs_lanes_in_parallel_and_tasks_in_sequence(self):
        model = TaskTableModel()
        lane_a = [
            model.add({"Name": "A1", "Estimated Time": "4", SCHEDULE_GROUP_COLUMN: "A"}),
            model.add({"Name": "A2", "Estimated Time": "5", SCHEDULE_GROUP_COLUMN: "A"}),
            model.add({"Name": "A3", "Estimated Time": "8", SCHEDULE_GROUP_COLUMN: "A"}),
        ]
        lane_b = [
            model.add({"Name": "B1", "Estimated Time": "6", SCHEDULE_GROUP_COLUMN: "B"}),
            model.add({"Name": "B2", "Estimated Time": "3", SCHEDULE_GROUP_COLUMN: "B"}),
        ]
        zero = model.add({"Name": "C0", "Estimated Time": "0", SCHEDULE_GROUP_COLUMN: "C"})

        due_dates, target_date, lane_totals = calculate_qbom_schedule(
            model.rows,
            date(2026, 9, 28),
        )

        self.assertEqual([due_dates[row.row_id] for row in lane_a], [
            "09/28/2026", "09/29/2026", "09/30/2026",
        ])
        self.assertEqual([due_dates[row.row_id] for row in lane_b], [
            "09/28/2026", "09/29/2026",
        ])
        self.assertEqual(due_dates[zero.row_id], "09/28/2026")
        self.assertEqual(target_date, date(2026, 9, 30))
        self.assertEqual(lane_totals, {"A": 17.0, "B": 9.0, "C": 0.0})

    def test_schedule_skips_weekends_and_first_large_task_uses_hour_logic(self):
        model = TaskTableModel()
        first = model.add({"Name": "First", "Estimated Time": "8", SCHEDULE_GROUP_COLUMN: "A"})
        second = model.add({"Name": "Second", "Estimated Time": "5", SCHEDULE_GROUP_COLUMN: "A"})

        due_dates, target_date, _ = calculate_qbom_schedule(model.rows, date(2026, 10, 2))

        self.assertEqual(due_dates[first.row_id], "10/05/2026")
        self.assertEqual(due_dates[second.row_id], "10/06/2026")
        self.assertEqual(target_date, date(2026, 10, 6))
        self.assertEqual(add_workdays(date(2026, 10, 3), 0), date(2026, 10, 5))

    def test_zero_integer_estimates_use_raw_decimal_minutes_for_scheduling(self):
        model = TaskTableModel()
        rows = [
            model.add({
                "Name": f"Small {index}",
                "Product": "ART",
                "Estimated Time": "0",
                SCHEDULE_GROUP_COLUMN: "A",
                RAW_ESTIMATED_TIME_COLUMN: "0.42",
            })
            for index in range(15)
        ]

        due_dates, target_date, lane_totals = calculate_qbom_schedule(
            model.rows,
            date(2026, 9, 28),
        )

        self.assertEqual(due_dates[rows[12].row_id], "09/28/2026")
        self.assertEqual(due_dates[rows[13].row_id], "09/29/2026")
        self.assertEqual(due_dates[rows[14].row_id], "09/29/2026")
        self.assertEqual(target_date, date(2026, 9, 29))
        self.assertAlmostEqual(lane_totals["A"], 6.5)
        self.assertIn("26 min", review_notes(rows[0].values)[0])

    def test_export_manifest_links_csv_by_hash_and_schema(self):
        with tempfile.TemporaryDirectory(dir=Path.cwd()) as temp_dir:
            output_path = Path(temp_dir) / "asana.csv"
            manifest_path = output_path.with_suffix(".manifest.json")
            records = [{"Name": "Task A", "Product": "ART", "Estimated Time": "4"}]
            export_csv(output_path, records)
            write_json_document(
                manifest_path,
                build_export_manifest(output_path, records, "All tasks", {"name": "Project.xlsx"}),
            )

            with manifest_path.open(encoding="utf-8") as manifest_file:
                manifest = json.load(manifest_file)

            self.assertEqual(manifest["format"], MANIFEST_FORMAT)
            self.assertEqual(manifest["task_count"], 1)
            self.assertEqual(manifest["estimated_time_total"], 4)
            self.assertEqual(
                manifest["estimation_weights"],
                {"primary": 1.0, "secondary": 0.25, "tertiary": 0.1},
            )
            self.assertEqual(manifest["scope"], "All tasks")
            self.assertEqual([field["name"] for field in manifest["schema"]], ASANA_EXPORT_COLUMNS)
            self.assertEqual(len(manifest["csv_sha256"]), 64)


if __name__ == "__main__":
    unittest.main()
