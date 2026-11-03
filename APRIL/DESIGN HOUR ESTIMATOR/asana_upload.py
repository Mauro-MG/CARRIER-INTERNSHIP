"""Offline Asana upload preflight and request-payload generation.

This module intentionally contains no HTTP client and cannot contact Asana. It
turns task rows plus a previously generated discovery JSON file into a reviewable
upload-preview document that a future transport layer can submit.
"""

from __future__ import annotations

import hashlib
import json
import math
import os
from dataclasses import dataclass
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Iterable, Mapping


DISCOVERY_FORMAT = "asana-project-field-discovery"
PREVIEW_FORMAT = "asana-task-upload-preview"
PREVIEW_VERSION = 1

EXPECTED_CUSTOM_FIELDS: dict[str, dict[str, str]] = {
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

FIELD_ALIASES = {
    "Project": {"DW ALL": "DW All", "30 CF": "30CF"},
    "Status": {"Completed": "Done"},
    "Labels": {"BOM/WT": "WTPART"},
}


class UploadPreviewError(ValueError):
    """Raised when discovery/configuration is not usable for an offline preview."""


@dataclass(frozen=True)
class UploadSettings:
    discovery_path: Path
    project_gid: str = ""
    workspace_gid: str = ""
    section_gid: str = ""


def _read_env_file(path: Path) -> dict[str, str]:
    """Read non-interpolated KEY=VALUE settings without exporting secrets."""
    if not path.is_file():
        return {}
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
        key, value = key.strip(), value.strip()
        if len(value) >= 2 and value[0] == value[-1] and value[0] in {"'", '"'}:
            value = value[1:-1]
        result[key] = value
    return result


def load_upload_settings(app_dir: Path, env_path: Path | None = None) -> UploadSettings:
    """Load only non-secret upload coordinates; never read or return the token."""
    env_path = env_path or app_dir / ".env"
    file_values = _read_env_file(env_path)

    def setting(name: str, default: str = "") -> str:
        return os.environ.get(name, file_values.get(name, default)).strip()

    discovery_text = setting("ASANA_FIELDS_OUTPUT", "asana_project_fields.json")
    discovery_path = Path(discovery_text)
    if not discovery_path.is_absolute():
        discovery_path = env_path.parent / discovery_path
    return UploadSettings(
        discovery_path=discovery_path,
        project_gid=setting("ASANA_PROJECT_GID"),
        workspace_gid=setting("ASANA_WORKSPACE_GID"),
        section_gid=setting("ASANA_SECTION_GID"),
    )


def load_discovery(path: Path) -> dict[str, Any]:
    try:
        document = json.loads(path.read_text(encoding="utf-8-sig"))
    except FileNotFoundError as error:
        raise UploadPreviewError(
            f"Asana discovery JSON was not found: {path}. Run the discovery script first, "
            "then place the generated JSON beside the packaged app or update "
            "ASANA_FIELDS_OUTPUT in .env."
        ) from error
    except json.JSONDecodeError as error:
        raise UploadPreviewError(f"Discovery JSON is invalid: {error}") from error
    if not isinstance(document, dict) or document.get("format") != DISCOVERY_FORMAT:
        raise UploadPreviewError("The selected JSON is not an Asana project discovery file.")
    return document


def cache_workspace_user(path: Path, user: Any) -> None:
    """Persist one verified user in the local discovery cache for dry-run resolution."""
    document = load_discovery(path)
    gid = str(getattr(user, "gid", "") or "").strip()
    email = str(getattr(user, "email", "") or "").strip()
    name = str(getattr(user, "name", "") or "").strip()
    if not gid or not email:
        raise UploadPreviewError("The verified Asana user is missing a GID or email.")
    existing = document.get("workspace_users")
    users = [item for item in existing if isinstance(item, dict)] if isinstance(existing, list) else []
    users = [
        item for item in users
        if str(item.get("gid", "")) != gid
        and str(item.get("email", "")).casefold() != email.casefold()
    ]
    users.append({"gid": gid, "name": name, "email": email})
    users.sort(key=lambda item: str(item.get("email", "")).casefold())
    document["workspace_users"] = users

    lookup = document.get("user_lookup")
    lookup = dict(lookup) if isinstance(lookup, dict) else {}
    requested = [str(value) for value in lookup.get("requested_emails", [])]
    if not any(value.casefold() == email.casefold() for value in requested):
        requested.append(email)
    unresolved = [
        str(value) for value in lookup.get("unresolved_emails", [])
        if str(value).casefold() != email.casefold()
    ]
    lookup.update({
        "mode": "configured_assignees_only",
        "requested_emails": requested,
        "resolved_count": len(users),
        "unresolved_emails": unresolved,
    })
    document["user_lookup"] = lookup
    temporary_path = path.with_suffix(path.suffix + ".tmp")
    temporary_path.write_text(
        json.dumps(document, indent=2, ensure_ascii=False) + "\n",
        encoding="utf-8",
    )
    temporary_path.replace(path)


def options_from_discovery(document: Mapping[str, Any]) -> dict[str, list[str]]:
    """Return enabled UI option names from a cached discovery document."""
    result: dict[str, list[str]] = {}
    raw_fields = document.get("custom_fields")
    fields = [item for item in raw_fields if isinstance(item, dict)] if isinstance(raw_fields, list) else []
    for field_name in ("Priority", "Project", "Status", "Labels", "Task Type"):
        field = _matching_field(fields, field_name)
        if field is None:
            continue
        options = field.get("enum_options")
        if isinstance(options, list):
            result[field_name] = list(dict.fromkeys(
                str(option.get("name", "")).strip()
                for option in options
                if isinstance(option, dict) and option.get("enabled") is not False
                and str(option.get("name", "")).strip()
            ))
    users = document.get("workspace_users")
    if isinstance(users, list):
        result["Assignee"] = list(dict.fromkeys(
            str(user.get("email", "")).strip()
            for user in users
            if isinstance(user, dict) and str(user.get("email", "")).strip()
        ))
    return result


def _matching_field(fields: list[dict[str, Any]], app_name: str) -> dict[str, Any] | None:
    if app_name == "Estimated Time":
        native = [field for field in fields if field.get("asana_created_field") == "estimated_time"]
        if len(native) == 1:
            return native[0]
    matches = [
        field for field in fields
        if str(field.get("name", "")).casefold() == app_name.casefold()
    ]
    return matches[0] if len(matches) == 1 else None


def validate_discovery(
    document: Mapping[str, Any], settings: UploadSettings
) -> tuple[dict[str, dict[str, Any]], list[str]]:
    """Validate project coordinates and return the canonical custom-field map."""
    errors: list[str] = []
    project = document.get("project") if isinstance(document.get("project"), dict) else {}
    workspace = document.get("workspace") if isinstance(document.get("workspace"), dict) else {}
    project_gid = str(project.get("gid", ""))
    workspace_gid = str(workspace.get("gid", ""))
    if not project_gid:
        errors.append("Discovery JSON does not identify a destination project.")
    if settings.project_gid and settings.project_gid != project_gid:
        errors.append("ASANA_PROJECT_GID does not match the discovery project.")
    if settings.workspace_gid and settings.workspace_gid != workspace_gid:
        errors.append("ASANA_WORKSPACE_GID does not match the discovery workspace.")
    if project.get("archived"):
        errors.append("The destination Asana project is archived.")

    sections = document.get("sections") if isinstance(document.get("sections"), list) else []
    section_gids = {str(section.get("gid", "")) for section in sections if isinstance(section, dict)}
    if settings.section_gid and settings.section_gid not in section_gids:
        errors.append("ASANA_SECTION_GID is not a section in the discovered project.")

    raw_fields = document.get("custom_fields")
    fields = [item for item in raw_fields if isinstance(item, dict)] if isinstance(raw_fields, list) else []
    matched: dict[str, dict[str, Any]] = {}
    for app_name, expected in EXPECTED_CUSTOM_FIELDS.items():
        field = _matching_field(fields, app_name)
        if field is None:
            errors.append(f"Custom field '{app_name}' is missing or ambiguous.")
            continue
        mismatches = [
            f"{key}={field.get(key)!r} (expected {value!r})"
            for key, value in expected.items()
            if field.get(key) != value
        ]
        if mismatches:
            errors.append(f"Custom field '{app_name}' has the wrong definition: {', '.join(mismatches)}.")
            continue
        if field.get("enabled") is False or field.get("is_value_read_only"):
            errors.append(f"Custom field '{app_name}' is disabled or read-only.")
            continue
        matched[app_name] = field
    return matched, errors


def _option_index(field: Mapping[str, Any]) -> dict[str, dict[str, str]]:
    options = field.get("enum_options")
    if not isinstance(options, list):
        return {}
    return {
        str(option.get("name", "")).casefold(): {
            "gid": str(option.get("gid", "")),
            "name": str(option.get("name", "")),
        }
        for option in options
        if isinstance(option, dict) and option.get("enabled") is not False
        and option.get("gid") and option.get("name")
    }


def _canonical_value(field_name: str, value: str) -> str:
    stripped = value.strip()
    return FIELD_ALIASES.get(field_name, {}).get(stripped, stripped)


def _resolve_option(
    field_name: str,
    raw_value: str,
    field: Mapping[str, Any],
) -> tuple[str | list[str] | None, list[str]]:
    is_multi = field.get("resource_subtype") == "multi_enum"
    values = [part.strip() for part in raw_value.split(",") if part.strip()] if is_multi else [raw_value.strip()]
    values = [_canonical_value(field_name, value) for value in values if value]
    if not values:
        return None, []
    options = _option_index(field)
    gids: list[str] = []
    errors: list[str] = []
    for value in dict.fromkeys(values):
        option = options.get(value.casefold())
        if option is None:
            errors.append(f"{field_name} option '{value}' is not enabled in Asana.")
        else:
            gids.append(option["gid"])
    if errors:
        return None, errors
    return (gids if is_multi else gids[0]), []


def _parse_due_on(value: str) -> str | None:
    text = value.strip()
    if not text:
        return None
    for pattern in ("%m/%d/%Y", "%Y-%m-%d", "%m/%d/%y"):
        try:
            return datetime.strptime(text, pattern).date().isoformat()
        except ValueError:
            continue
    raise ValueError(f"Due Date '{text}' is invalid.")


def _finite_number(value: object) -> float | None:
    try:
        number = float(str(value).strip())
    except (TypeError, ValueError):
        return None
    return number if math.isfinite(number) else None


def estimated_time_minutes(row: Mapping[str, Any]) -> int | None:
    """Convert displayed hours/fallback decimal hours to ceiling whole minutes."""
    hours = _finite_number(row.get("Estimated Time", ""))
    if hours is None:
        return None
    if hours < 0:
        raise ValueError("Estimated Time cannot be negative.")
    raw_hours = _finite_number(
        row.get("_Raw Estimated Hours", row.get("_Raw Estimated Time", ""))
    )
    effective_hours = raw_hours if hours == 0 and raw_hours is not None and 0 < raw_hours < 1 else hours
    return int(math.ceil(effective_hours * 60 - 1e-12))


def _user_index(document: Mapping[str, Any]) -> dict[str, dict[str, str]]:
    users = document.get("workspace_users")
    if not isinstance(users, list):
        return {}
    return {
        str(user.get("email", "")).casefold(): {
            "gid": str(user.get("gid", "")),
            "name": str(user.get("name", "")),
            "email": str(user.get("email", "")),
        }
        for user in users
        if isinstance(user, dict) and user.get("email") and user.get("gid")
    }


def _row_mapping(row: Any) -> Mapping[str, Any]:
    values = row if isinstance(row, Mapping) else getattr(row, "values", row)
    if not isinstance(values, Mapping):
        raise TypeError("Each task row must be a mapping or expose a mapping in .values.")
    return values


def _client_key(project_gid: str, row_identity: int, values: Mapping[str, Any]) -> str:
    stable = json.dumps(
        {"project_gid": project_gid, "row_identity": row_identity, "values": dict(values)},
        sort_keys=True,
        ensure_ascii=False,
        default=str,
    ).encode("utf-8")
    return hashlib.sha256(stable).hexdigest()[:24]


def build_upload_preview(
    rows: Iterable[Any],
    discovery: Mapping[str, Any],
    settings: UploadSettings,
    *,
    source: Mapping[str, Any] | None = None,
) -> dict[str, Any]:
    """Build an offline, non-executable review document for future POST /tasks calls."""
    fields, configuration_errors = validate_discovery(discovery, settings)
    project = discovery.get("project") if isinstance(discovery.get("project"), dict) else {}
    workspace = discovery.get("workspace") if isinstance(discovery.get("workspace"), dict) else {}
    project_gid = str(project.get("gid", ""))
    users = _user_index(discovery)
    raw_sections = discovery.get("sections")
    sections = [item for item in raw_sections if isinstance(item, dict)] if isinstance(raw_sections, list) else []
    selected_section = next(
        (item for item in sections if str(item.get("gid", "")) == settings.section_gid),
        None,
    )
    requests: list[dict[str, Any]] = []
    row_errors: list[dict[str, Any]] = []

    for row_number, original in enumerate(rows, start=1):
        values = _row_mapping(original)
        row_identity = int(getattr(original, "row_id", row_number))
        name = str(values.get("Name", "")).strip()
        errors: list[str] = []
        if not name:
            errors.append("Name is required.")
        data: dict[str, Any] = {"name": name, "projects": [project_gid] if project_gid else []}
        description = str(values.get("Description", "")).strip()
        if description:
            data["notes"] = description
        try:
            due_on = _parse_due_on(str(values.get("Due Date", "")))
            if due_on:
                data["due_on"] = due_on
        except ValueError as error:
            errors.append(str(error))

        assignee_email = str(values.get("Assignee", "")).strip()
        if assignee_email:
            user = users.get(assignee_email.casefold())
            if user is None:
                if "workspace_users" not in discovery:
                    errors.append(
                        "Assignees cannot be resolved because discovery was not run with --include-users."
                    )
                else:
                    errors.append(f"Assignee '{assignee_email}' was not found in the workspace users.")
            else:
                data["assignee"] = user["gid"]

        custom_fields: dict[str, Any] = {}
        for field_name in ("Priority", "Project", "Status", "Labels", "Task Type"):
            field = fields.get(field_name)
            if field is None:
                continue
            resolved, option_errors = _resolve_option(
                field_name, str(values.get(field_name, "")), field
            )
            errors.extend(option_errors)
            if resolved is not None:
                custom_fields[str(field["gid"])] = resolved

        estimated_field = fields.get("Estimated Time")
        if estimated_field is not None:
            try:
                minutes = estimated_time_minutes(values)
                if minutes is not None:
                    custom_fields[str(estimated_field["gid"])] = minutes
            except ValueError as error:
                errors.append(str(error))
        ecn = str(values.get("ECN", "")).strip()
        if ecn and (ecn_field := fields.get("ECN")) is not None:
            custom_fields[str(ecn_field["gid"])] = ecn
        if custom_fields:
            data["custom_fields"] = custom_fields

        if errors:
            row_errors.append({"row": row_number, "name": name, "errors": errors})
            continue
        requests.append(
            {
                "row": row_number,
                "name": name,
                "client_key": _client_key(project_gid, row_identity, values),
                "method": "POST",
                "path": "/tasks",
                "data": data,
                "section_gid_after_create": settings.section_gid or None,
            }
        )

    all_errors = list(configuration_errors)
    ready = not all_errors and not row_errors and len(requests) > 0
    return {
        "format": PREVIEW_FORMAT,
        "version": PREVIEW_VERSION,
        "generated_at": datetime.now(timezone.utc).isoformat(),
        "mode": "offline-dry-run",
        "network_requests_performed": 0,
        "ready_for_upload": ready,
        "destination": {
            "workspace_gid": str(workspace.get("gid", "")),
            "workspace_name": workspace.get("name"),
            "project_gid": project_gid,
            "project_name": project.get("name"),
            "section_gid": settings.section_gid or None,
            "section_name": selected_section.get("name") if selected_section else None,
        },
        "summary": {
            "input_rows": len(requests) + len(row_errors),
            "valid_requests": len(requests),
            "invalid_rows": len(row_errors),
            "configuration_errors": len(all_errors),
        },
        "configuration_errors": all_errors,
        "row_errors": row_errors,
        "source": dict(source or {}),
        "requests": requests,
        "excluded_by_policy": {
            "Product": "Blocked in Asana and intentionally set manually by the user.",
            "Target Date": "Project-level calculated date; not copied to every task.",
            "native_completed": "Status 'Done' does not automatically complete the native task.",
        },
    }


def write_upload_preview(path: Path, document: Mapping[str, Any]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(
        json.dumps(document, indent=2, ensure_ascii=False) + "\n",
        encoding="utf-8",
    )
