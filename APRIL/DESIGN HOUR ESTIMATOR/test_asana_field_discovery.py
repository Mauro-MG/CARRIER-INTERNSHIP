import json
import os
import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch

from discover_asana_project_fields import (
    DISCOVERY_FORMAT,
    DiscoveryError,
    build_suggested_matches,
    discover_project,
    load_assignee_emails,
    load_dotenv,
    write_discovery,
)


class FakeAsanaClient:
    def get(self, path, params=None):
        if path == "/users/me":
            return {"data": {"gid": "11", "name": "Uploader", "email": "uploader@example.com"}}
        if path == "/projects/222":
            return {
                "data": {
                    "gid": "222",
                    "name": "Automation Test",
                    "archived": False,
                    "workspace": {"gid": "111", "name": "Engineering"},
                    "team": {"gid": "333", "name": "Design"},
                }
            }
        if path == "/workspaces/111/users/uploader%40example.com":
            return {"data": {"gid": "11", "name": "Uploader", "email": "uploader@example.com"}}
        raise AssertionError(f"Unexpected GET {path}")

    def get_all(self, path, params=None):
        if path == "/projects/222/custom_field_settings":
            return [
                {
                    "gid": "setting-product",
                    "custom_field": {
                        "gid": "field-product",
                        "name": "Product",
                        "resource_subtype": "enum",
                        "enum_options": [
                            {"gid": "option-art", "name": "ART", "enabled": True, "color": "blue"}
                        ],
                    },
                },
                {
                    "gid": "setting-estimate",
                    "custom_field": {
                        "gid": "field-estimate",
                        "name": "Estimated time",
                        "resource_subtype": "number",
                        "format": "duration",
                        "asana_created_field": "estimated_time",
                    },
                },
            ]
        if path == "/projects/222/sections":
            return [{"gid": "section-1", "name": "Incoming"}]
        raise AssertionError(f"Unexpected GET collection {path}")


class AsanaFieldDiscoveryTests(unittest.TestCase):
    def test_dotenv_loads_values_without_overwriting_real_environment(self):
        with tempfile.TemporaryDirectory(dir=Path.cwd()) as temp_dir:
            path = Path(temp_dir) / ".env"
            path.write_text(
                "# comment\nASANA_ACCESS_TOKEN='secret value'\nASANA_PROJECT_GID=222\n",
                encoding="utf-8",
            )
            with patch.dict(os.environ, {"ASANA_PROJECT_GID": "existing"}, clear=False):
                loaded = load_dotenv(path)
                self.assertEqual(loaded["ASANA_ACCESS_TOKEN"], "secret value")
                self.assertEqual(os.environ["ASANA_PROJECT_GID"], "existing")

    def test_matcher_detects_compatible_ambiguous_and_wrong_type_fields(self):
        fields = [
            {
                "gid": "1", "name": "Product", "resource_subtype": "enum",
                "format": None, "is_formula_field": False, "is_value_read_only": False,
            },
            {
                "gid": "2", "name": "Priority", "resource_subtype": "text",
                "format": None, "is_formula_field": False, "is_value_read_only": False,
            },
            {
                "gid": "3", "name": "Status", "resource_subtype": "enum",
                "format": None, "is_formula_field": False, "is_value_read_only": False,
            },
            {
                "gid": "4", "name": "status", "resource_subtype": "enum",
                "format": None, "is_formula_field": False, "is_value_read_only": False,
            },
        ]
        matches = build_suggested_matches(fields)
        self.assertNotIn("Product", matches)
        self.assertEqual(matches["Priority"]["status"], "wrong_type_or_read_only")
        self.assertEqual(matches["Status"]["status"], "ambiguous")
        self.assertEqual(matches["Task Type"]["status"], "missing")

    def test_discovery_collects_fields_options_sections_and_optional_users(self):
        document = discover_project(
            FakeAsanaClient(),
            "222",
            configured_workspace_gid="111",
            configured_section_gid="section-1",
            include_users=True,
            assignee_emails=["uploader@example.com"],
        )

        self.assertEqual(document["format"], DISCOVERY_FORMAT)
        self.assertEqual(document["project"]["gid"], "222")
        self.assertEqual(document["workspace"]["gid"], "111")
        self.assertEqual(document["custom_fields"][0]["name"], "Estimated time")
        product = next(field for field in document["custom_fields"] if field["name"] == "Product")
        self.assertEqual(product["enum_options"][0]["gid"], "option-art")
        self.assertEqual(document["suggested_app_matches"]["Estimated Time"]["selected_gid"], "field-estimate")
        self.assertEqual(document["sections"][0]["gid"], "section-1")
        self.assertEqual(document["workspace_users"][0]["email"], "uploader@example.com")
        self.assertEqual(document["user_lookup"]["resolved_count"], 1)
        self.assertEqual(document["user_lookup"]["mode"], "configured_assignees_only")

    def test_assignee_email_loader_uses_small_options_list_or_explicit_override(self):
        with tempfile.TemporaryDirectory(dir=Path.cwd()) as temp_dir:
            path = Path(temp_dir) / "options.json"
            path.write_text(
                json.dumps({"Assignee": ["one@example.com", "two@example.com"]}),
                encoding="utf-8",
            )
            with patch.dict(os.environ, {}, clear=False):
                os.environ.pop("ASANA_ASSIGNEE_EMAILS", None)
                self.assertEqual(
                    load_assignee_emails(path),
                    ["one@example.com", "two@example.com"],
                )
            self.assertEqual(
                load_assignee_emails(path, ["only@example.com"]),
                ["only@example.com"],
            )

    def test_workspace_or_section_mismatch_fails_before_writing(self):
        with self.assertRaisesRegex(DiscoveryError, "does not match"):
            discover_project(FakeAsanaClient(), "222", configured_workspace_gid="wrong")
        with self.assertRaisesRegex(DiscoveryError, "not a section"):
            discover_project(FakeAsanaClient(), "222", configured_section_gid="wrong")

    def test_written_mapping_never_contains_access_token(self):
        document = discover_project(FakeAsanaClient(), "222")
        with tempfile.TemporaryDirectory(dir=Path.cwd()) as temp_dir:
            path = Path(temp_dir) / "mapping.json"
            write_discovery(path, document)
            saved_text = path.read_text(encoding="utf-8")
            saved = json.loads(saved_text)
        self.assertEqual(saved["project"]["gid"], "222")
        self.assertNotIn("access_token", saved_text.casefold())


if __name__ == "__main__":
    unittest.main()
