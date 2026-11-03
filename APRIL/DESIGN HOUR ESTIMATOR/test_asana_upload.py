import copy
import json
import tempfile
import unittest
from pathlib import Path

from asana_upload import (
    UploadSettings,
    build_upload_preview,
    cache_workspace_user,
    estimated_time_minutes,
    options_from_discovery,
    validate_discovery,
)
from asana_user_lookup import AsanaUser


def enum_field(name, gid, subtype="enum", options=()):
    return {
        "gid": gid,
        "name": name,
        "resource_subtype": subtype,
        "enabled": True,
        "is_value_read_only": False,
        "enum_options": [
            {"gid": option_gid, "name": option_name, "enabled": True}
            for option_name, option_gid in options
        ],
    }


def discovery_fixture():
    return {
        "format": "asana-project-field-discovery",
        "version": 1,
        "workspace": {"gid": "workspace-1", "name": "Carrier"},
        "project": {"gid": "project-1", "name": "NPD Design MTH", "archived": False},
        "sections": [{"gid": "section-1", "name": "Untitled section"}],
        "workspace_users": [
            {"gid": "user-1", "name": "Jessica", "email": "Jessica@example.com"}
        ],
        "custom_fields": [
            enum_field("Product", "field-product", options=[("ART", "product-art")]),
            enum_field("Priority", "field-priority", options=[("High", "priority-high")]),
            enum_field(
                "Project", "field-project",
                options=[("DW All", "project-dw-all"), ("DOAS", "project-doas")],
            ),
            enum_field(
                "Status", "field-status",
                options=[("Pending", "status-pending"), ("Done", "status-done")],
            ),
            enum_field(
                "Labels", "field-labels",
                options=[("BOM", "label-bom"), ("WTPART", "label-wtpart")],
            ),
            {
                "gid": "field-estimate",
                "name": "Estimated time",
                "resource_subtype": "number",
                "format": "duration",
                "asana_created_field": "estimated_time",
                "enabled": True,
                "is_value_read_only": False,
                "enum_options": [],
            },
            {
                "gid": "field-ecn", "name": "ECN", "resource_subtype": "text",
                "enabled": True, "is_value_read_only": False, "enum_options": [],
            },
            enum_field(
                "Task Type", "field-task-type", subtype="multi_enum",
                options=[("Task", "type-task"), ("Review", "type-review")],
            ),
        ],
    }


class UploadPreviewTests(unittest.TestCase):
    def setUp(self):
        self.discovery = discovery_fixture()
        self.settings = UploadSettings(
            discovery_path=Path("asana_project_fields.json"),
            project_gid="project-1",
            workspace_gid="workspace-1",
            section_gid="section-1",
        )

    def test_builds_resolved_offline_payload_with_aliases_and_minutes(self):
        preview = build_upload_preview(
            [{
                "Name": "Design task",
                "Description": "Generated from qBOM",
                "Assignee": "jessica@example.com",
                "Due Date": "09/30/2026",
                "Product": "ART",
                "Priority": "High",
                "Project": "DW ALL",
                "Status": "Completed",
                "Labels": "BOM/WT",
                "Estimated Time": "0",
                "_Raw Estimated Hours": "0.32",
                "ECN": "ECN-7",
                "Task Type": "Task, Review",
            }],
            self.discovery,
            self.settings,
        )

        self.assertTrue(preview["ready_for_upload"])
        self.assertEqual(preview["network_requests_performed"], 0)
        request = preview["requests"][0]
        self.assertEqual(request["path"], "/tasks")
        self.assertEqual(request["section_gid_after_create"], "section-1")
        self.assertEqual(request["data"]["assignee"], "user-1")
        self.assertEqual(request["data"]["due_on"], "2026-09-30")
        custom = request["data"]["custom_fields"]
        self.assertNotIn("field-product", custom)
        self.assertEqual(custom["field-project"], "project-dw-all")
        self.assertEqual(custom["field-status"], "status-done")
        self.assertEqual(custom["field-labels"], "label-wtpart")
        self.assertEqual(custom["field-estimate"], 20)
        self.assertEqual(custom["field-task-type"], ["type-task", "type-review"])
        self.assertNotIn("Target Date", request["data"])

    def test_missing_user_discovery_blocks_assigned_rows(self):
        discovery = copy.deepcopy(self.discovery)
        del discovery["workspace_users"]

        preview = build_upload_preview(
            [{"Name": "Assigned", "Assignee": "Jessica@example.com"}],
            discovery,
            self.settings,
        )

        self.assertFalse(preview["ready_for_upload"])
        self.assertEqual(preview["summary"]["invalid_rows"], 1)
        self.assertIn("--include-users", preview["row_errors"][0]["errors"][0])

    def test_wrong_field_type_is_a_configuration_error(self):
        discovery = copy.deepcopy(self.discovery)
        next(field for field in discovery["custom_fields"] if field["name"] == "Labels")[
            "resource_subtype"
        ] = "multi_enum"

        fields, errors = validate_discovery(discovery, self.settings)

        self.assertNotIn("Labels", fields)
        self.assertTrue(any("Labels" in error and "wrong definition" in error for error in errors))

    def test_estimate_conversion_rounds_minutes_up(self):
        self.assertEqual(estimated_time_minutes({"Estimated Time": "4"}), 240)
        self.assertEqual(estimated_time_minutes({"Estimated Time": "0.333"}), 20)
        self.assertEqual(
            estimated_time_minutes({"Estimated Time": "0", "_Raw Estimated Hours": "0.42"}),
            26,
        )

    def test_cached_discovery_supplies_only_enabled_options_and_users(self):
        disabled = {"gid": "old", "name": "Old", "enabled": False}
        self.discovery["custom_fields"][0]["enum_options"].append(disabled)

        options = options_from_discovery(self.discovery)

        self.assertNotIn("Product", options)
        self.assertEqual(options["Assignee"], ["Jessica@example.com"])

    def test_product_is_not_required_or_inserted_into_upload_payload(self):
        preview = build_upload_preview(
            [{"Name": "Missing product"}], self.discovery, self.settings
        )

        self.assertTrue(preview["ready_for_upload"])
        custom = preview["requests"][0]["data"].get("custom_fields", {})
        self.assertNotIn("field-product", custom)
        self.assertIn("Product", preview["excluded_by_policy"])

    def test_verified_user_is_added_to_small_local_discovery_cache(self):
        discovery = copy.deepcopy(self.discovery)
        discovery.pop("workspace_users")
        with tempfile.TemporaryDirectory(dir=Path.cwd()) as temp_dir:
            path = Path(temp_dir) / "fields.json"
            path.write_text(json.dumps(discovery), encoding="utf-8")

            cache_workspace_user(
                path,
                AsanaUser(gid="user-9", name="New Person", email="new@carrier.com"),
            )

            saved = json.loads(path.read_text(encoding="utf-8"))
        self.assertEqual(saved["workspace_users"], [{
            "gid": "user-9", "name": "New Person", "email": "new@carrier.com"
        }])
        self.assertEqual(saved["user_lookup"]["resolved_count"], 1)

    def test_client_key_is_stable_when_same_table_row_is_uploaded_in_a_subset(self):
        class Row:
            row_id = 8
            values = {"Name": "Stable", "Product": "ART"}

        selected = build_upload_preview([Row()], self.discovery, self.settings)
        all_rows = build_upload_preview(
            [
                {"Name": "Earlier", "Product": "ART"},
                Row(),
            ],
            self.discovery,
            self.settings,
        )

        self.assertEqual(
            selected["requests"][0]["client_key"],
            all_rows["requests"][1]["client_key"],
        )


if __name__ == "__main__":
    unittest.main()
