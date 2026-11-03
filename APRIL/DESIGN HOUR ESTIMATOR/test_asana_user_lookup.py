import io
import json
import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch
from urllib.error import HTTPError

from asana_user_lookup import (
    AssigneeLookupError,
    AssigneeNotFoundError,
    lookup_workspace_user_by_email,
)


class FakeResponse:
    def __init__(self, document):
        self.body = json.dumps(document).encode("utf-8")

    def __enter__(self):
        return self

    def __exit__(self, *_args):
        return False

    def read(self):
        return self.body


class AsanaUserLookupTests(unittest.TestCase):
    def write_env(self, directory):
        path = Path(directory) / ".env"
        path.write_text(
            "ASANA_ACCESS_TOKEN=test-token\nASANA_WORKSPACE_GID=workspace-1\n",
            encoding="utf-8",
        )
        return path

    def test_looks_up_only_submitted_email_and_returns_canonical_user(self):
        with tempfile.TemporaryDirectory(dir=Path.cwd()) as temp_dir:
            env_path = self.write_env(temp_dir)
            with patch(
                "asana_user_lookup.urlopen",
                return_value=FakeResponse({
                    "data": {"gid": "user-7", "name": "Person", "email": "Person@carrier.com"}
                }),
            ) as request:
                user = lookup_workspace_user_by_email("person@carrier.com", env_path=env_path)

        self.assertEqual(user.gid, "user-7")
        self.assertEqual(user.email, "Person@carrier.com")
        url = request.call_args.args[0].full_url
        self.assertIn("/workspaces/workspace-1/users/person%40carrier.com", url)
        self.assertNotIn("/workspaces/workspace-1/users?", url)

    def test_404_rejects_unknown_email(self):
        with tempfile.TemporaryDirectory(dir=Path.cwd()) as temp_dir:
            env_path = self.write_env(temp_dir)
            error = HTTPError(
                "https://example.invalid", 404, "Not Found", {},
                io.BytesIO(b'{"errors":[{"message":"user: Not a recognized ID"}]}'),
            )
            with patch("asana_user_lookup.urlopen", side_effect=error):
                with self.assertRaises(AssigneeNotFoundError):
                    lookup_workspace_user_by_email("missing@carrier.com", env_path=env_path)

    def test_invalid_email_is_rejected_without_network(self):
        with patch("asana_user_lookup.urlopen") as request:
            with self.assertRaises(AssigneeLookupError):
                lookup_workspace_user_by_email("not-an-email", env_path=Path("missing.env"))
        request.assert_not_called()


if __name__ == "__main__":
    unittest.main()
