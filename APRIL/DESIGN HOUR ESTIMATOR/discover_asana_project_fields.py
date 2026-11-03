"""Read Asana project metadata and save a field/option mapping for the desktop app.

This utility is deliberately read-only. It never writes to Asana and never puts
the access token in its JSON output.
"""

from __future__ import annotations

import argparse
import json
import os
import sys
from datetime import datetime, timezone
from pathlib import Path
from typing import Any
from urllib.error import HTTPError, URLError
from urllib.parse import quote, urlencode
from urllib.request import Request, urlopen


API_BASE = "https://app.asana.com/api/1.0"
DISCOVERY_FORMAT = "asana-project-field-discovery"
DISCOVERY_VERSION = 1

EXPECTED_CUSTOM_FIELDS = {
    "Priority": {"resource_subtype": "enum"},
    "Project": {"resource_subtype": "enum"},
    "Status": {"resource_subtype": "enum"},
    "Labels": {"resource_subtype": "enum"},
    "Estimated Time": {
        "resource_subtype": "number",
        "format": "duration",
        "asana_created_field": "estimated_time",
    },
    "ECN": {"resource_subtype": "text"},
    "Task Type": {"resource_subtype": "multi_enum"},
}

NATIVE_TASK_FIELDS = {
    "Name": "name",
    "Description": "notes",
    "Assignee": "assignee",
    "Due Date": "due_on",
}

CUSTOM_FIELD_OPT_FIELDS = ",".join(
    [
        "gid",
        "is_important",
        "custom_field.gid",
        "custom_field.name",
        "custom_field.resource_subtype",
        "custom_field.representation_type",
        "custom_field.format",
        "custom_field.precision",
        "custom_field.asana_created_field",
        "custom_field.is_formula_field",
        "custom_field.is_value_read_only",
        "custom_field.is_global_to_workspace",
        "custom_field.enabled",
        "custom_field.enum_options.gid",
        "custom_field.enum_options.name",
        "custom_field.enum_options.enabled",
        "custom_field.enum_options.color",
    ]
)


class DiscoveryError(RuntimeError):
    """A safe, user-facing discovery failure."""


def load_dotenv(path: Path, *, override: bool = False) -> dict[str, str]:
    """Load a small, interpolation-free subset of .env syntax."""
    if not path.is_file():
        raise DiscoveryError(f"Environment file was not found: {path}")
    loaded: dict[str, str] = {}
    for line_number, raw_line in enumerate(path.read_text(encoding="utf-8-sig").splitlines(), start=1):
        line = raw_line.strip()
        if not line or line.startswith("#"):
            continue
        if line.startswith("export "):
            line = line[7:].lstrip()
        if "=" not in line:
            raise DiscoveryError(f"Invalid .env entry on line {line_number}: expected KEY=VALUE.")
        key, value = line.split("=", 1)
        key = key.strip()
        value = value.strip()
        if not key or not key.replace("_", "").isalnum() or key[0].isdigit():
            raise DiscoveryError(f"Invalid .env key on line {line_number}: {key!r}.")
        if len(value) >= 2 and value[0] == value[-1] and value[0] in {"'", '"'}:
            value = value[1:-1]
        loaded[key] = value
        if override or key not in os.environ:
            os.environ[key] = value
    return loaded


def require_setting(name: str) -> str:
    value = os.environ.get(name, "").strip()
    if not value:
        raise DiscoveryError(f"Set {name} in .env before running discovery.")
    return value


def error_message_from_body(body: bytes) -> str:
    try:
        document = json.loads(body.decode("utf-8", errors="replace"))
        errors = document.get("errors", []) if isinstance(document, dict) else []
        messages = [str(item.get("message", "")).strip() for item in errors if isinstance(item, dict)]
        if messages:
            return "; ".join(message for message in messages if message)
    except json.JSONDecodeError:
        pass
    return body.decode("utf-8", errors="replace").strip() or "No error details returned."


class AsanaClient:
    def __init__(self, token: str, *, timeout: float = 30.0) -> None:
        self._token = token
        self._timeout = timeout

    def get(self, path: str, params: dict[str, Any] | None = None) -> dict[str, Any]:
        query = urlencode(params or {}, doseq=True)
        url = f"{API_BASE}{path}" + (f"?{query}" if query else "")
        request = Request(
            url,
            method="GET",
            headers={
                "Accept": "application/json",
                "Authorization": f"Bearer {self._token}",
                "User-Agent": "Design-Hour-Estimator-Asana-Discovery/1.0",
            },
        )
        try:
            with urlopen(request, timeout=self._timeout) as response:
                payload = response.read()
        except HTTPError as error:
            details = error_message_from_body(error.read())
            raise DiscoveryError(f"Asana returned HTTP {error.code} for {path}: {details}") from error
        except URLError as error:
            raise DiscoveryError(f"Could not connect to Asana for {path}: {error.reason}") from error
        except TimeoutError as error:
            raise DiscoveryError(f"Asana request timed out for {path}.") from error
        try:
            document = json.loads(payload.decode("utf-8"))
        except json.JSONDecodeError as error:
            raise DiscoveryError(f"Asana returned invalid JSON for {path}.") from error
        if not isinstance(document, dict) or "data" not in document:
            raise DiscoveryError(f"Asana returned an unexpected response for {path}.")
        return document

    def get_all(self, path: str, params: dict[str, Any] | None = None) -> list[dict[str, Any]]:
        items: list[dict[str, Any]] = []
        page_params = dict(params or {})
        page_params.setdefault("limit", 100)
        while True:
            document = self.get(path, page_params)
            data = document.get("data")
            if not isinstance(data, list):
                raise DiscoveryError(f"Asana returned a non-list collection for {path}.")
            items.extend(item for item in data if isinstance(item, dict))
            next_page = document.get("next_page")
            offset = next_page.get("offset") if isinstance(next_page, dict) else None
            if not offset:
                return items
            page_params["offset"] = offset


def compact_user(user: dict[str, Any]) -> dict[str, Any]:
    return {
        key: user.get(key)
        for key in ("gid", "name", "email")
        if user.get(key) not in (None, "")
    }


def load_assignee_emails(
    options_path: Path,
    explicit_emails: list[str] | None = None,
) -> list[str]:
    """Load only the small assignee list needed by the desktop application."""
    if explicit_emails:
        candidates = explicit_emails
    else:
        env_value = os.environ.get("ASANA_ASSIGNEE_EMAILS", "").strip()
        if env_value:
            candidates = env_value.replace(";", ",").split(",")
        else:
            try:
                options = json.loads(options_path.read_text(encoding="utf-8-sig"))
            except (FileNotFoundError, json.JSONDecodeError, OSError):
                options = {}
            raw_assignees = options.get("Assignee", []) if isinstance(options, dict) else []
            candidates = raw_assignees if isinstance(raw_assignees, list) else []
    cleaned = [str(email).strip() for email in candidates if str(email).strip()]
    return list(dict.fromkeys(cleaned))


def normalize_enum_options(options: object) -> list[dict[str, Any]]:
    if not isinstance(options, list):
        return []
    normalized = []
    for option in options:
        if not isinstance(option, dict):
            continue
        normalized.append(
            {
                "gid": str(option.get("gid", "")),
                "name": str(option.get("name", "")),
                "enabled": bool(option.get("enabled", False)),
                "color": option.get("color"),
            }
        )
    return normalized


def normalize_custom_field(setting: dict[str, Any]) -> dict[str, Any] | None:
    field = setting.get("custom_field")
    if not isinstance(field, dict) or not field.get("gid"):
        return None
    return {
        "setting_gid": str(setting.get("gid", "")),
        "is_important": bool(setting.get("is_important", False)),
        "gid": str(field.get("gid", "")),
        "name": str(field.get("name", "")),
        "resource_subtype": field.get("resource_subtype"),
        "representation_type": field.get("representation_type"),
        "format": field.get("format"),
        "precision": field.get("precision"),
        "asana_created_field": field.get("asana_created_field"),
        "is_formula_field": bool(field.get("is_formula_field", False)),
        "is_value_read_only": bool(field.get("is_value_read_only", False)),
        "is_global_to_workspace": bool(field.get("is_global_to_workspace", False)),
        "enabled": field.get("enabled", True) is not False,
        "enum_options": normalize_enum_options(field.get("enum_options")),
    }


def field_matches_requirement(field: dict[str, Any], requirement: dict[str, str]) -> bool:
    if field.get("resource_subtype") != requirement["resource_subtype"]:
        return False
    if "format" in requirement and field.get("format") != requirement["format"]:
        return False
    return not field.get("is_formula_field") and not field.get("is_value_read_only")


def candidate_fields(
    app_name: str,
    fields: list[dict[str, Any]],
) -> list[dict[str, Any]]:
    exact = [field for field in fields if field.get("name", "").casefold() == app_name.casefold()]
    if app_name == "Estimated Time":
        native_estimate = [
            field for field in fields if field.get("asana_created_field") == "estimated_time"
        ]
        exact = list({field["gid"]: field for field in native_estimate + exact}.values())
    return exact


def build_suggested_matches(fields: list[dict[str, Any]]) -> dict[str, dict[str, Any]]:
    matches: dict[str, dict[str, Any]] = {}
    for app_name, requirement in EXPECTED_CUSTOM_FIELDS.items():
        candidates = candidate_fields(app_name, fields)
        compatible = [field for field in candidates if field_matches_requirement(field, requirement)]
        if len(compatible) == 1:
            status = "matched"
            selected_gid: str | None = compatible[0]["gid"]
        elif not candidates:
            status = "missing"
            selected_gid = None
        elif not compatible:
            status = "wrong_type_or_read_only"
            selected_gid = None
        else:
            status = "ambiguous"
            selected_gid = None
        matches[app_name] = {
            "status": status,
            "selected_gid": selected_gid,
            "expected": requirement,
            "candidates": [
                {
                    "gid": field["gid"],
                    "name": field["name"],
                    "resource_subtype": field.get("resource_subtype"),
                    "format": field.get("format"),
                    "asana_created_field": field.get("asana_created_field"),
                    "is_value_read_only": field.get("is_value_read_only"),
                }
                for field in candidates
            ],
        }
    return matches


def discover_project(
    client: AsanaClient,
    project_gid: str,
    *,
    configured_workspace_gid: str = "",
    configured_section_gid: str = "",
    include_users: bool = False,
    assignee_emails: list[str] | None = None,
) -> dict[str, Any]:
    safe_project_gid = quote(project_gid, safe="")
    user_document = client.get(
        "/users/me",
        {"opt_fields": "gid,name,email,workspaces.gid,workspaces.name"},
    )
    project_document = client.get(
        f"/projects/{safe_project_gid}",
        {
            "opt_fields": (
                "gid,name,archived,permalink_url,workspace.gid,workspace.name,"
                "team.gid,team.name"
            )
        },
    )
    project = project_document["data"]
    if not isinstance(project, dict):
        raise DiscoveryError("Asana returned an invalid project object.")
    workspace = project.get("workspace")
    if not isinstance(workspace, dict) or not workspace.get("gid"):
        raise DiscoveryError("The project response did not include its workspace GID.")
    workspace_gid = str(workspace["gid"])
    if configured_workspace_gid and configured_workspace_gid != workspace_gid:
        raise DiscoveryError(
            "ASANA_WORKSPACE_GID does not match the selected project's workspace "
            f"({configured_workspace_gid} != {workspace_gid})."
        )

    raw_settings = client.get_all(
        f"/projects/{safe_project_gid}/custom_field_settings",
        {"opt_fields": CUSTOM_FIELD_OPT_FIELDS},
    )
    fields = [normalized for setting in raw_settings if (normalized := normalize_custom_field(setting))]
    fields.sort(key=lambda item: (item["name"].casefold(), item["gid"]))
    sections = client.get_all(
        f"/projects/{safe_project_gid}/sections",
        {"opt_fields": "gid,name,created_at"},
    )
    normalized_sections = [
        {
            "gid": str(section.get("gid", "")),
            "name": str(section.get("name", "")),
            "created_at": section.get("created_at"),
        }
        for section in sections
    ]
    if configured_section_gid and configured_section_gid not in {
        section["gid"] for section in normalized_sections
    }:
        raise DiscoveryError(
            "ASANA_SECTION_GID is not a section in the selected project."
        )

    result: dict[str, Any] = {
        "format": DISCOVERY_FORMAT,
        "version": DISCOVERY_VERSION,
        "fetched_at": datetime.now(timezone.utc).isoformat(),
        "api_base": API_BASE,
        "authenticated_user": compact_user(user_document["data"]),
        "workspace": {
            "gid": workspace_gid,
            "name": workspace.get("name"),
        },
        "project": {
            "gid": str(project.get("gid", "")),
            "name": project.get("name"),
            "archived": bool(project.get("archived", False)),
            "permalink_url": project.get("permalink_url"),
            "team": project.get("team"),
        },
        "configured_section_gid": configured_section_gid,
        "native_task_fields": NATIVE_TASK_FIELDS,
        "custom_fields": fields,
        "suggested_app_matches": build_suggested_matches(fields),
        "sections": normalized_sections,
    }
    if include_users:
        requested_emails = list(dict.fromkeys(
            email.strip() for email in (assignee_emails or []) if email.strip()
        ))
        if not requested_emails:
            authenticated_email = str(user_document["data"].get("email", "")).strip()
            requested_emails = [authenticated_email] if authenticated_email else []
        users: list[dict[str, Any]] = []
        unresolved: list[str] = []
        safe_workspace_gid = quote(workspace_gid, safe="")
        for email in requested_emails:
            try:
                user = client.get(
                    f"/workspaces/{safe_workspace_gid}/users/{quote(email, safe='')}",
                    {"opt_fields": "gid,name,email"},
                ).get("data")
            except DiscoveryError as error:
                if "HTTP 404" not in str(error):
                    raise
                unresolved.append(email)
                continue
            if isinstance(user, dict) and user.get("gid"):
                users.append(compact_user(user))
            else:
                unresolved.append(email)
        result["workspace_users"] = users
        result["user_lookup"] = {
            "mode": "configured_assignees_only",
            "requested_emails": requested_emails,
            "resolved_count": len(users),
            "unresolved_emails": unresolved,
        }
    return result


def write_discovery(path: Path, document: dict[str, Any]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open("w", encoding="utf-8") as output_file:
        json.dump(document, output_file, indent=2, ensure_ascii=False)
        output_file.write("\n")


def print_summary(document: dict[str, Any], output_path: Path) -> None:
    project = document["project"]
    matches = document["suggested_app_matches"]
    counts: dict[str, int] = {}
    for match in matches.values():
        status = str(match["status"])
        counts[status] = counts.get(status, 0) + 1
    status_text = ", ".join(f"{status}: {count}" for status, count in sorted(counts.items()))
    print(f"Project: {project.get('name')} ({project.get('gid')})")
    print(f"Custom fields: {len(document['custom_fields'])}; sections: {len(document['sections'])}")
    print(f"App field matches: {status_text}")
    if isinstance(document.get("user_lookup"), dict):
        lookup = document["user_lookup"]
        print(
            f"Assignees: {lookup.get('resolved_count', 0)} resolved; "
            f"{len(lookup.get('unresolved_emails', []))} unresolved"
        )
    print(f"Saved discovery mapping to: {output_path.resolve()}")


def parse_args(argv: list[str] | None = None) -> argparse.Namespace:
    parser = argparse.ArgumentParser(
        description="Read all custom fields and options from one Asana project.",
    )
    parser.add_argument("--env-file", type=Path, default=Path(__file__).resolve().with_name(".env"))
    parser.add_argument("--output", type=Path, help="Override ASANA_FIELDS_OUTPUT.")
    parser.add_argument(
        "--include-users",
        action="store_true",
        help="Resolve only configured app assignees and export their GIDs/emails.",
    )
    parser.add_argument(
        "--assignee-email",
        action="append",
        default=[],
        help="Email to resolve with --include-users; repeat for multiple users.",
    )
    parser.add_argument(
        "--options-file",
        type=Path,
        default=Path(__file__).resolve().with_name("asana_task_options.json"),
        help="App options file used to find assignee emails when no email flags are supplied.",
    )
    return parser.parse_args(argv)


def main(argv: list[str] | None = None) -> int:
    args = parse_args(argv)
    try:
        env_path = args.env_file.resolve()
        load_dotenv(env_path)
        token = require_setting("ASANA_ACCESS_TOKEN")
        project_gid = require_setting("ASANA_PROJECT_GID")
        workspace_gid = os.environ.get("ASANA_WORKSPACE_GID", "").strip()
        section_gid = os.environ.get("ASANA_SECTION_GID", "").strip()
        output_setting = os.environ.get("ASANA_FIELDS_OUTPUT", "asana_project_fields.json").strip()
        output_path = args.output or Path(output_setting)
        if not output_path.is_absolute():
            output_path = env_path.parent / output_path

        assignee_emails = load_assignee_emails(args.options_file, args.assignee_email)
        document = discover_project(
            AsanaClient(token),
            project_gid,
            configured_workspace_gid=workspace_gid,
            configured_section_gid=section_gid,
            include_users=args.include_users,
            assignee_emails=assignee_emails,
        )
        write_discovery(output_path, document)
        print_summary(document, output_path)
        return 0
    except (DiscoveryError, OSError) as error:
        print(f"Discovery failed: {error}", file=sys.stderr)
        return 1


if __name__ == "__main__":
    raise SystemExit(main())
