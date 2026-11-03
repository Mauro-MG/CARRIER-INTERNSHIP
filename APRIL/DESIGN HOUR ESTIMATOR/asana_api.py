"""Real Asana task-upload transport with confirmation-friendly batch semantics."""

from __future__ import annotations

import json
import time
from dataclasses import dataclass
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Callable, Mapping
from urllib.error import HTTPError, URLError
from urllib.parse import quote
from urllib.request import Request, urlopen


API_BASE = "https://app.asana.com/api/1.0"
JOURNAL_FORMAT = "asana-task-upload-journal"
JOURNAL_VERSION = 1
REPORT_FORMAT = "asana-task-upload-report"
REPORT_VERSION = 1


class AsanaApiError(RuntimeError):
    """A definite Asana API failure."""


class AsanaAmbiguousCreateError(AsanaApiError):
    """A task create may have reached Asana, so blind retry could duplicate it."""


def _timestamp() -> str:
    return datetime.now(timezone.utc).isoformat(timespec="seconds")


def _env_values(path: Path) -> dict[str, str]:
    if not path.is_file():
        raise AsanaApiError(f"Environment file was not found: {path}")
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


def _error_details(body: bytes) -> str:
    try:
        document = json.loads(body.decode("utf-8", errors="replace"))
        errors = document.get("errors", []) if isinstance(document, dict) else []
        messages = []
        for item in errors:
            if not isinstance(item, dict):
                continue
            message = str(item.get("message", "")).strip()
            phrase = str(item.get("phrase", "")).strip()
            if message:
                messages.append(message + (f" (phrase: {phrase})" if phrase else ""))
        if messages:
            return "; ".join(messages)
    except json.JSONDecodeError:
        pass
    return "No additional details were returned."


@dataclass
class AsanaApiClient:
    token: str
    timeout: float = 30.0
    max_rate_limit_retries: int = 3

    @classmethod
    def from_env(cls, env_path: Path) -> "AsanaApiClient":
        values = _env_values(env_path)
        token = values.get("ASANA_ACCESS_TOKEN", "").strip()
        if not token:
            raise AsanaApiError("ASANA_ACCESS_TOKEN is missing from .env.")
        return cls(token=token)

    def _post(self, path: str, data: Mapping[str, Any], *, is_create: bool = False) -> Any:
        body = json.dumps({"data": dict(data)}, ensure_ascii=False).encode("utf-8")
        request = Request(
            f"{API_BASE}{path}",
            data=body,
            method="POST",
            headers={
                "Accept": "application/json",
                "Authorization": f"Bearer {self.token}",
                "Content-Type": "application/json; charset=utf-8",
                "User-Agent": "Design-Hour-Estimator-Asana-Upload/1.0",
            },
        )
        rate_limit_attempts = 0
        while True:
            try:
                with urlopen(request, timeout=self.timeout) as response:
                    response_body = response.read()
                break
            except HTTPError as error:
                try:
                    error_body = error.read()
                finally:
                    error.close()
                if error.code == 429 and rate_limit_attempts < self.max_rate_limit_retries:
                    rate_limit_attempts += 1
                    try:
                        wait_seconds = max(0.0, float(error.headers.get("Retry-After", "1")))
                    except (TypeError, ValueError):
                        wait_seconds = 1.0
                    time.sleep(wait_seconds)
                    continue
                raise AsanaApiError(
                    f"Asana returned HTTP {error.code}: {_error_details(error_body)}"
                ) from error
            except (URLError, TimeoutError) as error:
                if is_create:
                    raise AsanaAmbiguousCreateError(
                        "The connection ended while creating a task. The task may exist in Asana; "
                        "check the project before retrying this row."
                    ) from error
                reason = getattr(error, "reason", error)
                raise AsanaApiError(f"Could not connect to Asana: {reason}") from error
        try:
            document = json.loads(response_body.decode("utf-8"))
        except json.JSONDecodeError as error:
            raise AsanaApiError("Asana returned invalid JSON.") from error
        if not isinstance(document, dict) or "data" not in document:
            raise AsanaApiError("Asana returned an unexpected response.")
        return document["data"]

    def create_task(self, data: Mapping[str, Any]) -> dict[str, Any]:
        task = self._post(
            "/tasks?opt_fields=gid,name,permalink_url",
            data,
            is_create=True,
        )
        if not isinstance(task, dict) or not task.get("gid"):
            raise AsanaApiError("Asana created a task but did not return its GID.")
        return task

    def add_task_to_section(
        self,
        section_gid: str,
        task_gid: str,
        *,
        insert_after: str = "",
    ) -> None:
        data = {"task": task_gid}
        if insert_after:
            data["insert_after"] = insert_after
        self._post(
            f"/sections/{quote(section_gid, safe='')}/addTask",
            data,
        )


def load_journal(path: Path) -> dict[str, Any]:
    if not path.is_file():
        return {
            "format": JOURNAL_FORMAT,
            "version": JOURNAL_VERSION,
            "updated_at": _timestamp(),
            "entries": {},
        }
    try:
        document = json.loads(path.read_text(encoding="utf-8-sig"))
    except json.JSONDecodeError as error:
        raise AsanaApiError(f"Upload journal contains invalid JSON: {error}") from error
    if not isinstance(document, dict) or document.get("format") != JOURNAL_FORMAT:
        raise AsanaApiError("The existing upload journal has an unsupported format.")
    if not isinstance(document.get("entries"), dict):
        raise AsanaApiError("The existing upload journal has invalid entries.")
    return document


def write_journal(path: Path, document: Mapping[str, Any]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    output = dict(document)
    output["updated_at"] = _timestamp()
    temporary_path = path.with_suffix(path.suffix + ".tmp")
    temporary_path.write_text(
        json.dumps(output, indent=2, ensure_ascii=False) + "\n",
        encoding="utf-8",
    )
    temporary_path.replace(path)


def upload_preview(
    preview: Mapping[str, Any],
    client: AsanaApiClient,
    *,
    journal_path: Path,
    progress: Callable[[int, int, str], None] | None = None,
) -> dict[str, Any]:
    """Submit a validated preview sequentially and journal every created task."""
    if not preview.get("ready_for_upload"):
        raise AsanaApiError("Upload preflight is not ready; correct its errors first.")
    raw_requests = preview.get("requests")
    requests = [item for item in raw_requests if isinstance(item, dict)] if isinstance(raw_requests, list) else []
    if not requests:
        raise AsanaApiError("Upload preflight contains no task requests.")
    journal = load_journal(journal_path)
    entries = journal["entries"]
    results: list[dict[str, Any]] = []
    previous_by_section: dict[str, str] = {}
    total = len(requests)

    for index, request_data in enumerate(requests, start=1):
        key = str(request_data.get("client_key", ""))
        name = str(request_data.get("name", ""))
        section_gid = str(request_data.get("section_gid_after_create") or "")
        if progress:
            progress(index, total, name)
        existing = entries.get(key) if key else None
        if isinstance(existing, dict) and existing.get("task_gid"):
            task_gid = str(existing["task_gid"])
            if section_gid and not existing.get("section_added"):
                try:
                    client.add_task_to_section(
                        section_gid,
                        task_gid,
                        insert_after=previous_by_section.get(section_gid, ""),
                    )
                    existing["section_added"] = True
                    existing["section_updated_at"] = _timestamp()
                    write_journal(journal_path, journal)
                    status = "section_repaired"
                except AsanaApiError as error:
                    results.append({
                        "client_key": key, "name": name, "status": "partial",
                        "task_gid": task_gid, "error": str(error),
                    })
                    continue
            else:
                status = "skipped_existing"
            if section_gid and existing.get("section_added"):
                previous_by_section[section_gid] = task_gid
            results.append({
                "client_key": key, "name": name, "status": status,
                "task_gid": task_gid, "permalink_url": existing.get("permalink_url", ""),
            })
            continue

        try:
            task = client.create_task(request_data.get("data", {}))
            task_gid = str(task["gid"])
            entry = {
                "client_key": key,
                "name": name,
                "task_gid": task_gid,
                "permalink_url": str(task.get("permalink_url", "")),
                "project_gid": preview.get("destination", {}).get("project_gid", ""),
                "section_gid": section_gid or None,
                "section_added": not bool(section_gid),
                "created_at": _timestamp(),
            }
            entries[key] = entry
            write_journal(journal_path, journal)
            if section_gid:
                try:
                    client.add_task_to_section(
                        section_gid,
                        task_gid,
                        insert_after=previous_by_section.get(section_gid, ""),
                    )
                    entry["section_added"] = True
                    entry["section_updated_at"] = _timestamp()
                    write_journal(journal_path, journal)
                except AsanaApiError as error:
                    results.append({
                        "client_key": key, "name": name, "status": "partial",
                        "task_gid": task_gid, "permalink_url": entry["permalink_url"],
                        "error": f"Task created, but section placement failed: {error}",
                    })
                    continue
            if section_gid:
                previous_by_section[section_gid] = task_gid
            results.append({
                "client_key": key, "name": name, "status": "created",
                "task_gid": task_gid, "permalink_url": entry["permalink_url"],
            })
        except AsanaAmbiguousCreateError as error:
            results.append({
                "client_key": key, "name": name, "status": "ambiguous", "error": str(error),
            })
        except AsanaApiError as error:
            results.append({
                "client_key": key, "name": name, "status": "failed", "error": str(error),
            })

    counts: dict[str, int] = {}
    for result in results:
        status = str(result["status"])
        counts[status] = counts.get(status, 0) + 1
    return {
        "format": REPORT_FORMAT,
        "version": REPORT_VERSION,
        "completed_at": _timestamp(),
        "destination": dict(preview.get("destination", {})),
        "journal_path": str(journal_path),
        "counts": counts,
        "results": results,
    }


def write_upload_report(path: Path, report: Mapping[str, Any]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(
        json.dumps(dict(report), indent=2, ensure_ascii=False) + "\n",
        encoding="utf-8",
    )
