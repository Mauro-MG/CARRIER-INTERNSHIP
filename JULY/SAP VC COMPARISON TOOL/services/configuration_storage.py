from __future__ import annotations

import json
import re
from datetime import datetime
from pathlib import Path
from typing import Any

from services.search_token_resolver import get_search_mode, search_mode_label


CONFIGURATION_DIR = Path("product_configurations")


def sanitize_product_type(product_type: str) -> str:
    sanitized = re.sub(r"[^A-Za-z0-9_-]+", "", product_type.strip().upper())
    return sanitized or "PRODUCT"


def configuration_filename(configuration: dict[str, Any]) -> str:
    product_type = sanitize_product_type(str(configuration.get("product_type", "")))
    configuration_date = str(configuration.get("configuration_date", "undated")).strip()
    version = str(configuration.get("version", "1")).strip()
    safe_version = re.sub(r"[^A-Za-z0-9_-]+", "", version) or "1"
    return f"{product_type}_{configuration_date}_v{safe_version}.json"


def save_configuration(
    configuration: dict[str, Any],
    *,
    overwrite: bool = False,
    configuration_dir: str | Path | None = None,
) -> str:
    base_dir = _configuration_dir(configuration_dir)
    base_dir.mkdir(parents=True, exist_ok=True)
    path = base_dir / configuration_filename(configuration)
    if path.exists() and not overwrite:
        raise FileExistsError(f"Configuration already exists: {path.name}")
    path.write_text(json.dumps(configuration, indent=2), encoding="utf-8")
    return str(path)


def load_configuration(file_path: str | Path) -> dict[str, Any]:
    path = Path(file_path)
    return json.loads(path.read_text(encoding="utf-8"))


def load_configuration_by_name(file_name: str, *, configuration_dir: str | Path | None = None) -> dict[str, Any]:
    return load_configuration(resolve_configuration_path(file_name, configuration_dir=configuration_dir))


def list_configurations(*, configuration_dir: str | Path | None = None) -> list[dict[str, Any]]:
    base_dir = _configuration_dir(configuration_dir)
    if not base_dir.exists():
        return []

    summaries: list[dict[str, Any]] = []
    for path in sorted(base_dir.glob("*.json")):
        try:
            configuration = load_configuration(path)
        except (OSError, json.JSONDecodeError):
            continue
        summaries.append(
            {
                "file_name": path.name,
                "file_path": str(path),
                "product_type": configuration.get("product_type", ""),
                "configuration_date": configuration.get("configuration_date", ""),
                "version": configuration.get("version", ""),
                "search_mode": get_search_mode(configuration),
                "search_mode_label": search_mode_label(get_search_mode(configuration)),
                "configured_positions": configuration.get("configured_positions", []),
                "updated_at": configuration.get("updated_at", ""),
            }
        )
    return summaries


def delete_configuration(file_name: str, *, configuration_dir: str | Path | None = None) -> None:
    path = resolve_configuration_path(file_name, configuration_dir=configuration_dir)
    path.unlink()


def duplicate_configuration(file_name: str, *, configuration_dir: str | Path | None = None) -> str:
    configuration = load_configuration_by_name(file_name, configuration_dir=configuration_dir)
    configuration["version"] = next_available_version(configuration, configuration_dir=configuration_dir)
    now = datetime.now().replace(microsecond=0).isoformat()
    configuration["created_at"] = now
    configuration["updated_at"] = now
    return save_configuration(configuration, overwrite=False, configuration_dir=configuration_dir)


def next_available_version(configuration: dict[str, Any], *, configuration_dir: str | Path | None = None) -> int | str:
    base_version = configuration.get("version", 1)
    try:
        candidate_version = int(base_version) + 1
    except (TypeError, ValueError):
        candidate_version = f"{base_version}-copy"

    while True:
        candidate = dict(configuration)
        candidate["version"] = candidate_version
        path = _configuration_dir(configuration_dir) / configuration_filename(candidate)
        if not path.exists():
            return candidate_version
        if isinstance(candidate_version, int):
            candidate_version += 1
        else:
            candidate_version = f"{candidate_version}-copy"


def resolve_configuration_path(file_name: str, *, configuration_dir: str | Path | None = None) -> Path:
    safe_name = Path(file_name).name
    if not safe_name or Path(safe_name).suffix.lower() != ".json":
        raise ValueError("Configuration file must be a JSON file.")
    path = (_configuration_dir(configuration_dir) / safe_name).resolve()
    base_dir = _configuration_dir(configuration_dir).resolve()
    if path.parent != base_dir:
        raise ValueError("Invalid configuration file path.")
    return path


def _configuration_dir(configuration_dir: str | Path | None = None) -> Path:
    return Path(configuration_dir) if configuration_dir is not None else CONFIGURATION_DIR
