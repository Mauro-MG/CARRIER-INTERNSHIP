"""Desktop workflow regression tests. Requires a working Tk display."""

import copy
import tempfile
import time
import unittest
from pathlib import Path
from unittest.mock import patch

from asana_task_app import (
    ASANA_EXPORT_COLUMNS, DEFAULT_OPTIONS, AsanaTaskApp, OptionManagerDialog,
    SCHEDULE_GROUP_COLUMN,
    app_storage_dir, automatic_export_path, load_saved_options, save_options,
    field_errors, merge_values, review_notes,
)
from asana_task_widgets import RowEditorDialog
from asana_user_lookup import AsanaUser, AssigneeNotFoundError


class DesktopWorkflowTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        # ttkbootstrap owns one Style/Tcl root per process, just as the app does.
        cls.app = AsanaTaskApp()

    @classmethod
    def tearDownClass(cls):
        cls.app.destroy()

    def setUp(self):
        self.app.model.clear()
        self.app.options = copy.deepcopy(DEFAULT_OPTIONS)
        self.app.history.clear()
        self.app._exported_records = []
        self.app.current_project_path = None
        self.app.current_draft_path = None
        self.app.source_trace = {}
        self.app._sort_column = ""
        self.app.export_scope.set("All tasks")
        self.app.bulk_scope.set("Selected rows")
        self.app.bulk_field.set("Assignee")
        self.app._set_start_date("09/28/2026")
        self.app.target_date_text.set("—")
        self.app.refresh_bulk_value_widget()
        self.app.clear_filters()
        self.app.geometry("960x620")
        self.app.update()
        self.addCleanup(self.close_app)

    def close_app(self):
        # Cancel scheduled callbacks before destroying the test's Tcl window.
        for after_id in self.app.tk.call("after", "info"):
            self.app.after_cancel(after_id)
        self.app._search_after = None
        for child in self.app.winfo_children():
            if isinstance(child, (RowEditorDialog, OptionManagerDialog)):
                child.destroy()

    def seed(self):
        a = self.app.model.add({
            "Name": "Alpha_BOM/WT", "Product": "ART", "Labels": "BOM/WT", "Estimated Time": "40"
        })
        b = self.app.model.add({
            "Name": "Beta_L1 BOM", "Product": "ART", "Labels": "BOM", "Estimated Time": "0"
        })
        self.app.refresh_table()
        return a, b

    def test_export_scope_is_explicit_and_independent_of_filter(self):
        a, b = self.seed()
        self.app.tree.selection_set(str(a.row_id))
        self.assertEqual(self.app.rows_for_export(), [a, b])
        self.app.search_text.set("Beta")
        self.app.refresh_table()
        self.assertEqual(self.app.tree.get_children(), (str(b.row_id),))
        self.assertEqual(self.app.rows_for_export(), [a, b])
        self.app.export_scope.set("Selected tasks")
        self.assertEqual(self.app.rows_for_export(), [])
        self.app.select_all_rows()
        self.assertEqual(self.app.rows_for_export(), [b])

    def test_batch_task_types_and_undo_support_multiple_values(self):
        self.seed()
        original = copy.deepcopy(self.app.model.to_export_records())
        self.app.select_all_rows()
        self.app.bulk_field.set("Task Type")
        self.app.refresh_bulk_value_widget()
        self.app.bulk_mode.set("Add values")
        self.app.bulk_value_widget.input.insert(0, "Review")
        self.app.apply_bulk_edit()
        self.assertEqual([row.get("Task Type") for row in self.app.model.rows], ["SW, Review", "SW, Review"])
        self.app.undo()
        self.assertEqual(self.app.model.to_export_records(), original)

    def test_batch_scope_targets_visible_rows_then_all_tasks(self):
        a, b = self.seed()
        self.app.search_text.set("Beta")
        self.app.refresh_table()
        self.app.bulk_scope.set("Visible rows")
        self.app.bulk_field.set("Status")
        self.app.refresh_bulk_value_widget()
        self.app.bulk_value_widget.input.set("On Hold")

        self.app.apply_bulk_edit()

        self.assertEqual(a.get("Status"), "Pending")
        self.assertEqual(b.get("Status"), "On Hold")
        self.app.bulk_scope.set("All tasks")
        self.app.bulk_field.set("Priority")
        self.app.refresh_bulk_value_widget()
        self.app.bulk_value_widget.input.set("High")
        self.app.apply_bulk_edit()
        self.assertEqual([row.get("Priority") for row in self.app.model.rows], ["High", "High"])

    def test_clear_field_for_all_tasks_requires_confirmation(self):
        self.seed()
        for row in self.app.model.rows:
            row.set("Assignee", "owner@example.com")
        self.app.bulk_scope.set("All tasks")
        self.app.bulk_field.set("Assignee")
        self.app.refresh_bulk_value_widget()

        with patch("asana_task_app.messagebox.askyesno", return_value=False) as confirm:
            self.app.clear_bulk_field()
        self.assertEqual([row.get("Assignee") for row in self.app.model.rows], ["owner@example.com"] * 2)
        confirm.assert_called_once()

        with patch("asana_task_app.messagebox.askyesno", return_value=True):
            self.app.clear_bulk_field()
        self.assertEqual([row.get("Assignee") for row in self.app.model.rows], ["", ""])

    def test_review_and_sort_do_not_change_values_or_export_order(self):
        a, b = self.seed()
        original = copy.deepcopy(self.app.model.to_export_records())
        self.app.sort_by("Estimated Time")
        self.assertEqual(self.app.tree.get_children(), (str(b.row_id), str(a.row_id)))
        self.app.review_only.set(True)
        self.app.refresh_table()
        self.assertEqual(self.app.tree.get_children(), (str(b.row_id),))
        self.assertEqual(self.app.model.to_export_records(), original)
        self.assertIn("0 hours", self.app._issues[b.row_id][0])

    def test_drag_range_selection_uses_current_visible_order(self):
        high = self.app.model.add({"Name": "High", "Estimated Time": "30"})
        low = self.app.model.add({"Name": "Low", "Estimated Time": "10"})
        mid = self.app.model.add({"Name": "Mid", "Estimated Time": "20"})
        self.app.refresh_table()
        self.app.sort_by("Estimated Time")
        self.assertEqual(self.app.tree.get_children(), (str(low.row_id), str(mid.row_id), str(high.row_id)))

        self.app._select_visible_range(str(low.row_id), str(high.row_id))

        self.assertEqual(self.app.tree.selection(), (str(low.row_id), str(mid.row_id), str(high.row_id)))
        self.assertIn("3 selected", self.app.selected_count_text.get())

    def test_select_visible_is_grouped_in_a_labeled_box(self):
        self.seed()

        self.assertIs(self.app.select_visible_button.master, self.app.selection_group)
        self.assertEqual(self.app.selection_group.cget("text"), "Row selection")
        self.assertEqual(self.app.select_visible_button.cget("text"), "Select visible")
        self.assertTrue(self.app.selection_group.winfo_ismapped())
        self.assertTrue(self.app.select_visible_button.winfo_ismapped())

    def test_editor_cancel_is_a_draft_and_all_fields_fit(self):
        self.seed()
        original = copy.deepcopy(self.app.model.to_export_records())
        self.app.tree.selection_set("1")
        self.app.open_selected_row_editor()
        dialog = next(child for child in self.app.winfo_children() if isinstance(child, RowEditorDialog))
        dialog.geometry("600x530")
        self.app.update()
        self.assertEqual(set(dialog.inputs), set(ASANA_EXPORT_COLUMNS))
        self.assertLessEqual(dialog.save_button.winfo_rooty() + dialog.save_button.winfo_height(),
                             dialog.winfo_rooty() + dialog.winfo_height())
        self.assertLessEqual(dialog.save_button.winfo_rootx() + dialog.save_button.winfo_width(),
                             dialog.winfo_rootx() + dialog.winfo_width())
        dialog.inputs["Name"].input.insert(0, "Changed ")
        dialog.destroy()
        self.assertEqual(self.app.model.to_export_records(), original)

    def test_small_window_keeps_batch_actions_and_export_visible(self):
        self.seed()
        for field in ["Assignee", "Description", "Labels", "Estimated Time"]:
            self.app.bulk_field.set(field)
            self.app.refresh_bulk_value_widget()
            self.app.update()
            self.assertGreaterEqual(self.app.bulk_value_container.winfo_width(), 240)
            for widget in [self.app.apply_button, self.app.clear_field_button, self.app.export_button]:
                self.assertTrue(widget.winfo_ismapped())
                self.assertLessEqual(widget.winfo_rootx() + widget.winfo_width(),
                                     self.app.winfo_rootx() + self.app.winfo_width())
                self.assertLessEqual(widget.winfo_rooty() + widget.winfo_height(),
                                     self.app.winfo_rooty() + self.app.winfo_height())

    def test_editor_save_and_undo(self):
        a, _ = self.seed()
        self.app.tree.selection_set(str(a.row_id))
        self.app.open_selected_row_editor()
        dialog = next(child for child in self.app.winfo_children() if isinstance(child, RowEditorDialog))
        dialog.inputs["Name"].input.delete(0, "end")
        dialog.inputs["Name"].input.insert(0, "Renamed")
        dialog._save()
        self.assertEqual(self.app.model.rows[0].get("Name"), "Renamed")
        self.app.undo()
        self.assertEqual(self.app.model.rows[0].get("Name"), "Alpha_BOM/WT")

    def test_option_rename_updates_multivalue_tokens_and_can_undo(self):
        a, b = self.seed()
        a.set("Task Type", "SW, Review")
        self.app.open_option_manager()
        dialog = next(child for child in self.app.winfo_children() if isinstance(child, OptionManagerDialog))
        dialog.current_group.set("Task Type")
        dialog._refresh()
        index = self.app.options["Task Type"].index("Review")
        dialog.listbox.selection_set(index)
        dialog.input_value.set("Peer Review")
        dialog._rename()
        dialog.destroy()
        self.assertEqual(a.get("Task Type"), "SW, Peer Review")
        self.assertEqual(b.get("Task Type"), "SW")
        self.app.undo()
        self.assertEqual(self.app.model.rows[0].get("Task Type"), "SW, Review")

    def test_new_assignee_is_added_only_after_targeted_email_validation(self):
        verified = AsanaUser("user-8", "New User", "New.User@carrier.com")
        with patch.object(self.app, "_lookup_assignee_option", return_value=verified) as lookup, \
                patch.object(self.app, "_save_options_to_disk", return_value=True):
            self.app.open_option_manager()
            dialog = next(
                child for child in self.app.winfo_children()
                if isinstance(child, OptionManagerDialog)
            )
            dialog.current_group.set("Assignee")
            dialog._refresh()
            dialog.input_value.set("new.user@carrier.com")
            dialog._add()
            deadline = time.monotonic() + 3
            while dialog._lookup_running and time.monotonic() < deadline:
                self.app.update()
                time.sleep(.01)

        lookup.assert_called_once_with("new.user@carrier.com")
        self.assertIn("New.User@carrier.com", self.app.options["Assignee"])
        dialog.destroy()

    def test_targeted_assignee_lookup_does_not_require_discovery_file(self):
        verified = AsanaUser("user-8", "New User", "New.User@carrier.com")
        with tempfile.TemporaryDirectory(dir=Path.cwd()) as temp_dir, \
                patch("asana_task_app.load_upload_settings") as settings, \
                patch("asana_task_app.lookup_workspace_user_by_email", return_value=verified) as lookup, \
                patch("asana_task_app.load_discovery") as load_discovery_mock, \
                patch("asana_task_app.cache_workspace_user") as cache:
            settings.return_value.discovery_path = Path(temp_dir) / "missing-fields.json"
            settings.return_value.workspace_gid = "workspace-1"

            result = self.app._lookup_assignee_option("new.user@carrier.com")

        self.assertEqual(result, verified)
        lookup.assert_called_once()
        self.assertEqual(lookup.call_args.args, ("new.user@carrier.com",))
        self.assertEqual(lookup.call_args.kwargs["env_path"].name, ".env")
        load_discovery_mock.assert_not_called()
        cache.assert_not_called()

    def test_unknown_assignee_is_not_added(self):
        missing = "missing.user@carrier.com"
        with patch.object(
            self.app,
            "_lookup_assignee_option",
            side_effect=AssigneeNotFoundError("User not found"),
        ) as lookup, patch("asana_task_app.messagebox.showwarning") as warning:
            self.app.open_option_manager()
            dialog = next(
                child for child in self.app.winfo_children()
                if isinstance(child, OptionManagerDialog)
            )
            dialog.current_group.set("Assignee")
            dialog._refresh()
            dialog.input_value.set(missing)
            dialog._add()
            deadline = time.monotonic() + 3
            while dialog._lookup_running and time.monotonic() < deadline:
                self.app.update()
                time.sleep(.01)

        lookup.assert_called_once_with(missing)
        warning.assert_called_once()
        self.assertNotIn(missing, self.app.options["Assignee"])
        dialog.destroy()

    def test_background_load_failure_preserves_current_work(self):
        self.seed()
        original = copy.deepcopy(self.app.model.to_export_records())
        with patch("asana_task_app.generate_rows_from_project", side_effect=ValueError("Missing qBOM")), \
                patch("asana_task_app.messagebox.showerror") as error:
            self.app._start_project_load(Path("missing.csv"))
            self.wait_for_load()
            self.assertEqual(self.app.model.to_export_records(), original)
            self.assertFalse(self.app._busy)
            error.assert_called_once()

    def test_successful_background_load_and_undo(self):
        self.seed()
        original = copy.deepcopy(self.app.model.to_export_records())
        with patch("asana_task_app.generate_rows_from_project", return_value=[
                {
                    "Name": "Generated_BOM/WT",
                    "Labels": "BOM/WT",
                    "Estimated Time": "15",
                    SCHEDULE_GROUP_COLUMN: "2:new-qbom.csv",
                }]):
            self.app._start_project_load(Path("new.csv"))
            self.wait_for_load()
        self.assertEqual(self.app.model.rows[0].get("Name"), "Generated_BOM/WT")
        self.assertEqual(self.app.model.rows[0].get("Due Date"), "09/30/2026")
        self.assertEqual(self.app.target_date_text.get(), "09/30/2026")
        self.app.undo()
        self.assertEqual(self.app.model.to_export_records(), original)
        self.assertIsNone(self.app.current_project_path)

    def test_generated_qbom_rows_recalculate_due_and_target_dates(self):
        a1 = self.app.model.add({
            "Name": "A1", "Estimated Time": "4", SCHEDULE_GROUP_COLUMN: "A",
        })
        a2 = self.app.model.add({
            "Name": "A2", "Estimated Time": "5", SCHEDULE_GROUP_COLUMN: "A",
        })
        b1 = self.app.model.add({
            "Name": "B1", "Estimated Time": "8", SCHEDULE_GROUP_COLUMN: "B",
        })

        self.assertTrue(self.app.recalculate_schedule())

        self.assertEqual(a1.get("Due Date"), "09/28/2026")
        self.assertEqual(a2.get("Due Date"), "09/29/2026")
        self.assertEqual(b1.get("Due Date"), "09/29/2026")
        self.assertEqual(self.app.target_date_text.get(), "09/29/2026")

        self.app._set_start_date("10/03/2026")
        self.app.recalculate_schedule()
        self.assertEqual(self.app.start_date_entry.entry.get(), "10/05/2026")
        self.assertEqual(a1.get("Due Date"), "10/05/2026")
        self.assertEqual(self.app.target_date_text.get(), "10/06/2026")

    def wait_for_load(self):
        deadline = time.monotonic() + 5
        while self.app._busy and time.monotonic() < deadline:
            self.app.update()
            time.sleep(.01)
        self.assertFalse(self.app._busy, "Background project loading did not finish")

    def test_export_uses_asana_uploads_folder_and_dirty_state(self):
        self.seed()
        self.app.tree.selection_set("1")
        self.app.export_scope.set("Selected tasks")
        upload_dir = Path.cwd() / "test-asana-uploads"
        self.addCleanup(lambda: upload_dir.exists() and upload_dir.rmdir())
        with patch("asana_task_app.ASANA_UPLOAD_DIR", upload_dir), \
                patch("asana_task_app.filedialog.asksaveasfilename") as dialog, \
                patch("asana_task_app.export_csv") as export:
            self.app.export_selected_csv()
            dialog.assert_not_called()
            self.assertTrue(self.app.dirty)
            self.assertEqual(export.call_args.args[0], upload_dir / "asana_tasks_selected.csv")
            self.assertEqual(len(export.call_args.args[1]), 1)
            self.app.export_scope.set("All tasks")
            export.side_effect = OSError("File in use")
            with patch("asana_task_app.messagebox.showerror"):
                self.app.export_selected_csv()
            self.assertTrue(self.app.dirty)
            export.side_effect = None
            self.app.export_selected_csv()
            self.assertEqual(export.call_args.args[0], upload_dir / "asana_tasks.csv")
            self.assertFalse(self.app.dirty)

    def test_real_upload_requires_confirmation_and_runs_in_background(self):
        self.seed()
        preview = {
            "ready_for_upload": True,
            "summary": {
                "valid_requests": 2, "invalid_rows": 0, "configuration_errors": 0,
            },
            "destination": {
                "project_gid": "project-1", "project_name": "Test Project", "section_gid": None,
            },
            "requests": [
                {"client_key": "1", "name": "Alpha", "data": {"name": "Alpha"}},
                {"client_key": "2", "name": "Beta", "data": {"name": "Beta"}},
            ],
        }
        report = {
            "counts": {"created": 2},
            "results": [
                {"name": "Alpha", "status": "created", "task_gid": "1"},
                {"name": "Beta", "status": "created", "task_gid": "2"},
            ],
        }
        with patch("asana_task_app.load_upload_settings") as settings, \
                patch("asana_task_app.load_discovery", return_value={}), \
                patch("asana_task_app.build_upload_preview", return_value=preview), \
                patch("asana_task_app.messagebox.askyesno", return_value=True), \
                patch("asana_task_app.AsanaApiClient.from_env", return_value=object()) as client, \
                patch("asana_task_app.upload_preview", return_value=report) as upload, \
                patch("asana_task_app.write_upload_report"), \
                patch("asana_task_app.messagebox.showinfo") as complete:
            settings.return_value.discovery_path = Path("fields.json")
            self.app.upload_to_asana()
            deadline = time.monotonic() + 3
            while self.app._busy and time.monotonic() < deadline:
                self.app.update()
                time.sleep(.01)

        self.assertFalse(self.app._busy)
        client.assert_called_once()
        upload.assert_called_once()
        complete.assert_called_once()
        self.assertFalse(self.app.dirty)

    def test_canceling_upload_makes_no_write_call(self):
        self.seed()
        preview = {
            "ready_for_upload": True,
            "summary": {
                "valid_requests": 2, "invalid_rows": 0, "configuration_errors": 0,
            },
            "destination": {"project_gid": "p1", "project_name": "Test", "section_gid": None},
            "requests": [{"client_key": "1", "name": "Alpha", "data": {"name": "Alpha"}}],
        }
        with patch("asana_task_app.load_upload_settings") as settings, \
                patch("asana_task_app.load_discovery", return_value={}), \
                patch("asana_task_app.build_upload_preview", return_value=preview), \
                patch("asana_task_app.messagebox.askyesno", return_value=False), \
                patch("asana_task_app.AsanaApiClient.from_env") as client:
            settings.return_value.discovery_path = Path("fields.json")
            self.app.upload_to_asana()

        client.assert_not_called()
        self.assertIn("canceled", self.app.status_text.get().lower())

    def test_save_and_open_draft_restore_current_tasks(self):
        self.seed()
        with tempfile.TemporaryDirectory(dir=Path.cwd()) as temp_dir:
            draft_path = Path(temp_dir) / "shared.asana-draft.json"
            with patch("asana_task_app.filedialog.asksaveasfilename", return_value=str(draft_path)):
                self.app.save_draft_file()
            self.assertTrue(draft_path.is_file())
            self.app.model.rows[0].set("Name", "Changed after save")
            self.app.refresh_table()

            with patch("asana_task_app.filedialog.askopenfilename", return_value=str(draft_path)), \
                    patch("asana_task_app.messagebox.askyesno", return_value=True):
                self.app.open_draft_file()

            self.assertEqual(self.app.model.rows[0].get("Name"), "Alpha_BOM/WT")
            self.assertEqual(self.app.current_draft_path, draft_path)
            self.assertEqual(len(self.app.model.rows), 2)


class InputRulesTests(unittest.TestCase):
    def test_saved_options_round_trip_and_sanitize_values(self):
        with tempfile.TemporaryDirectory(dir=Path.cwd()) as temp_dir:
            options_path = Path(temp_dir) / "asana_task_options.json"
            options = copy.deepcopy(DEFAULT_OPTIONS)
            options["Assignee"] = ["new@example.com", "new@example.com", "  "]
            options["Project"] = ["XR", "Custom"]

            save_options(options, options_path)
            loaded = load_saved_options(options_path)

            self.assertEqual(loaded["Assignee"], ["new@example.com"])
            self.assertEqual(loaded["Project"], ["XR", "Custom"])

    def test_saved_options_migrate_required_statuses_and_legacy_label(self):
        with tempfile.TemporaryDirectory(dir=Path.cwd()) as temp_dir:
            options_path = Path(temp_dir) / "asana_task_options.json"
            save_options(
                {
                    "Status": ["Pending", "In Progress", "Completed"],
                    "Labels": ["BOM", "BOM/WT", "Custom"],
                },
                options_path,
            )

            loaded = load_saved_options(options_path)

            self.assertEqual(
                loaded["Status"],
                ["Pending", "In Progress", "Done", "On Hold", "Backlog"],
            )
            self.assertEqual(loaded["Labels"], ["BOM", "WTPART", "Custom"])

    def test_packaged_storage_dir_and_upload_path_use_executable_folder(self):
        with tempfile.TemporaryDirectory(dir=Path.cwd()) as temp_dir:
            exe_path = Path(temp_dir) / "AsanaTaskGenerator.exe"
            upload_dir = Path(temp_dir) / "ASANA-UPLOADS"
            with patch("asana_task_app.sys.frozen", True, create=True), \
                    patch("asana_task_app.sys.executable", str(exe_path)), \
                    patch("asana_task_app.ASANA_UPLOAD_DIR", upload_dir):
                self.assertEqual(app_storage_dir(), Path(temp_dir))
                self.assertEqual(
                    automatic_export_path(Path("Project Files/Projects/Unit#1.xlsx"), False),
                    upload_dir / "Unit#1_asana_tasks.csv",
                )

    def test_validation_does_not_round_split_or_remove_zero(self):
        for value in ["0", "0.42", "40", "41"]:
            values = {"Name": "Task", "Estimated Time": value}
            self.assertEqual(field_errors(values), [])
            review_notes(values)
            self.assertEqual(values["Estimated Time"], value)
        for value in ["nan", "inf", "-1", "text"]:
            self.assertTrue(field_errors({"Estimated Time": value}))
        self.assertTrue(field_errors({"Name": "  ", "Due Date": "02/30/2026"}))

    def test_product_is_reference_only_and_not_validated_for_asana(self):
        self.assertNotIn("Product", DEFAULT_OPTIONS)
        self.assertEqual(field_errors({"Product": ""}, DEFAULT_OPTIONS), [])
        self.assertEqual(field_errors({"Product": "Unknown"}, DEFAULT_OPTIONS), [])

    def test_multi_values_are_deduplicated_with_exact_token_matching(self):
        self.assertEqual(merge_values("BOM, BOM/WT", "BOM", "Remove values"), "BOM/WT")
        self.assertEqual(merge_values("BOM", "BOM, PRT", "Add values"), "BOM, PRT")


if __name__ == "__main__":
    unittest.main()
