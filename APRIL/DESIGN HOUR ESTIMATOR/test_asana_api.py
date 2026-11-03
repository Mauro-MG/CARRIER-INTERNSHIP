import json
import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch

from asana_api import AsanaApiClient, load_journal, upload_preview


class FakeResponse:
    def __init__(self, document):
        self.body = json.dumps(document).encode("utf-8")

    def __enter__(self):
        return self

    def __exit__(self, *_args):
        return False

    def read(self):
        return self.body


class FakeClient:
    def __init__(self):
        self.created = []
        self.section_calls = []

    def create_task(self, data):
        self.created.append(data)
        number = len(self.created)
        return {
            "gid": f"task-{number}",
            "name": data["name"],
            "permalink_url": f"https://app.asana.com/0/task-{number}",
        }

    def add_task_to_section(self, section_gid, task_gid, *, insert_after=""):
        self.section_calls.append((section_gid, task_gid, insert_after))


def preview_fixture():
    return {
        "ready_for_upload": True,
        "destination": {"project_gid": "project-1", "project_name": "Test Project"},
        "requests": [
            {
                "client_key": "key-1", "name": "Task 1", "section_gid_after_create": "section-1",
                "data": {"name": "Task 1", "projects": ["project-1"]},
            },
            {
                "client_key": "key-2", "name": "Task 2", "section_gid_after_create": "section-1",
                "data": {"name": "Task 2", "projects": ["project-1"]},
            },
        ],
    }


class AsanaApiTests(unittest.TestCase):
    def test_create_task_posts_wrapped_payload_with_bearer_token(self):
        response = FakeResponse({
            "data": {"gid": "task-1", "name": "One", "permalink_url": "https://example/task-1"}
        })
        with patch("asana_api.urlopen", return_value=response) as request:
            task = AsanaApiClient("secret").create_task({"name": "One", "projects": ["p1"]})

        self.assertEqual(task["gid"], "task-1")
        sent_request = request.call_args.args[0]
        self.assertEqual(sent_request.method, "POST")
        self.assertEqual(sent_request.headers["Authorization"], "Bearer secret")
        self.assertEqual(
            json.loads(sent_request.data.decode("utf-8")),
            {"data": {"name": "One", "projects": ["p1"]}},
        )

    def test_upload_journal_prevents_duplicates_and_preserves_section_order(self):
        client = FakeClient()
        with tempfile.TemporaryDirectory(dir=Path.cwd()) as temp_dir:
            journal_path = Path(temp_dir) / "journal.json"
            first = upload_preview(preview_fixture(), client, journal_path=journal_path)
            second = upload_preview(preview_fixture(), client, journal_path=journal_path)
            journal = load_journal(journal_path)

        self.assertEqual(first["counts"], {"created": 2})
        self.assertEqual(second["counts"], {"skipped_existing": 2})
        self.assertEqual(len(client.created), 2)
        self.assertEqual(client.section_calls, [
            ("section-1", "task-1", ""),
            ("section-1", "task-2", "task-1"),
        ])
        self.assertEqual(len(journal["entries"]), 2)

    def test_not_ready_preview_is_never_sent(self):
        client = FakeClient()
        preview = preview_fixture()
        preview["ready_for_upload"] = False
        with tempfile.TemporaryDirectory(dir=Path.cwd()) as temp_dir:
            with self.assertRaisesRegex(Exception, "preflight is not ready"):
                upload_preview(preview, client, journal_path=Path(temp_dir) / "journal.json")
        self.assertEqual(client.created, [])


if __name__ == "__main__":
    unittest.main()
