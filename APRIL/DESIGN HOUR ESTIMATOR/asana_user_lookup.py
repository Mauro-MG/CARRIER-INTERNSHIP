"""Targeted Asana assignee lookup by workspace and email.

This module never enumerates workspace users. It calls only the single-user
workspace endpoint for the email explicitly submitted by the operator.
"""

from __future__ import annotations

import json
import re
from dataclasses import dataclass
from pathlib import Path
from urllib.error import HTTPError, URLError
from urllib.parse import quote, urlencode
from urllib.request import Request, urlopen


API_BASE = "https://app.asana.com/api/1.0"
EMAIL_PATTERN = re.compile(r"^[^@\s]+@[^@\s]+\.[^@\s]+$")


class AssigneeLookupError(RuntimeError):
    """A configuration, authorization, connection, or response problem."""


class AssigneeNotFoundError(AssigneeLookupError):
    """The submitted email is not a user in the configured workspace."""


@dataclass(frozen=True)
class AsanaUser:
    gid: str
    name: str
    email: str


def _env_values(path: Path) -> dict[str, str]:
    if not path.is_file():
        raise AssigneeLookupError(f"Environment file was not found: {path}")
    result: dict[str, str] = {}
    for raw_line in path.read_text(encoding="utf-8-sig").splitlines():
        line = raw_line.strip()
        if not line or line.startswith("#"):
            continue
        if line.startswith("export "):
            line = line[7:].lstrip()
        if "=" not in line:
            continue
        key, value = line.split("=", 1)
        value = value.strip()
        if len(value) >= 2 and value[0] == value[-1] and value[0] in {"'", '"'}:
            value = value[1:-1]
        result[key.strip()] = value
    return result


def _api_error(body: bytes) -> str:
    try:
        document = json.loads(body.decode("utf-8", errors="replace"))
        errors = document.get("errors", []) if isinstance(document, dict) else []
        messages = [
            str(item.get("message", "")).strip()
            for item in errors if isinstance(item, dict) and item.get("message")
        ]
        if messages:
            return "; ".join(messages)
    except json.JSONDecodeError:
        pass
    return "No additional details were returned."


def lookup_workspace_user_by_email(
    email: str,
    *,
    env_path: Path,
    timeout: float = 20.0,
) -> AsanaUser:
    """Resolve exactly one email without requesting the workspace user list."""
    requested_email = email.strip()
    if not EMAIL_PATTERN.fullmatch(requested_email):
        raise AssigneeLookupError("Enter a valid email address before adding the assignee.")
    settings = _env_values(env_path)
    token = settings.get("ASANA_ACCESS_TOKEN", "").strip()
    workspace_gid = settings.get("ASANA_WORKSPACE_GID", "").strip()
    if not token:
        raise AssigneeLookupError("ASANA_ACCESS_TOKEN is missing from .env.")
    if not workspace_gid:
        raise AssigneeLookupError("ASANA_WORKSPACE_GID is missing from .env.")

    path = (
        f"/workspaces/{quote(workspace_gid, safe='')}/users/"
        f"{quote(requested_email, safe='')}"
    )
    query = urlencode({"opt_fields": "gid,name,email"})
    request = Request(
        f"{API_BASE}{path}?{query}",
        method="GET",
        headers={
            "Accept": "application/json",
            "Authorization": f"Bearer {token}",
            "User-Agent": "Design-Hour-Estimator-Assignee-Lookup/1.0",
        },
    )
    try:
        with urlopen(request, timeout=timeout) as response:
            body = response.read()
    except HTTPError as error:
        try:
            error_body = error.read()
        finally:
            error.close()
        details = _api_error(error_body)
        if error.code == 404:
            raise AssigneeNotFoundError(
                f"'{requested_email}' is not an Asana user in this workspace."
            ) from error
        raise AssigneeLookupError(
            f"Asana returned HTTP {error.code} while checking the email: {details}"
        ) from error
    except URLError as error:
        raise AssigneeLookupError(f"Could not connect to Asana: {error.reason}") from error
    except TimeoutError as error:
        raise AssigneeLookupError("The Asana email lookup timed out.") from error

    try:
        document = json.loads(body.decode("utf-8"))
    except json.JSONDecodeError as error:
        raise AssigneeLookupError("Asana returned invalid JSON for the email lookup.") from error
    data = document.get("data") if isinstance(document, dict) else None
    if not isinstance(data, dict) or not data.get("gid"):
        raise AssigneeLookupError("Asana returned an unexpected user response.")
    returned_email = str(data.get("email", "")).strip()
    if not returned_email:
        raise AssigneeLookupError("Asana did not return an email for the matched user.")
    return AsanaUser(
        gid=str(data["gid"]),
        name=str(data.get("name", "")).strip(),
        email=returned_email,
    )
