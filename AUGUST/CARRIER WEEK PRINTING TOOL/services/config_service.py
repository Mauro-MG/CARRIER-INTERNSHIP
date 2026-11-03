"""Application configuration and directory initialization."""

from __future__ import annotations

import json
from copy import deepcopy
from pathlib import Path
from typing import Any


DEFAULT_CONFIG: dict[str, Any] = {
  "printer": {
    "name": "HP16F1AF (HP Smart Tank 610 series)"
  },
  "label": {
    "width_px": 288,
    "height_px": 192,
    "name": {
      "x": 145,
      "y": 35,
      "max_width": 260,
      "font_size": 13
    },
    "last_name": {
      "x": 145,
      "y": 50,
      "max_width": 260,
      "font_size": 11
    },
    "career1": {
      "x": 145,
      "y": 105,
      "max_width": 700,
      "font_size": 13
    },
    "career2": {
      "x": 145,
      "y": 120,
      "max_width": 700,
      "font_size": 11
    },
    "semester": {
      "x": 80,
      "y": 165,
      "max_width": 700,
      "font_size": 10
    },
    "folio": {
      "x": 200,
      "y": 165,
      "max_width": 700,
      "font_size": 10
    }
  }
}

def _merge_defaults(defaults: dict[str, Any], supplied: Any) -> dict[str, Any]:
    result = deepcopy(defaults)
    if not isinstance(supplied, dict):
        return result
    for key, value in supplied.items():
        if key in result and isinstance(result[key], dict):
            result[key] = _merge_defaults(result[key], value)
        elif key in result and isinstance(value, type(result[key])):
            result[key] = value
    return result


class ConfigService:
    """Load, validate, and atomically save JSON configuration."""

    def __init__(self, project_root: Path) -> None:
        self.root = project_root
        self.path = project_root / "config.json"
        self.config: dict[str, Any] = {}

    def initialize(self) -> dict[str, Any]:
        for folder in ("database", "assets", "assets/fonts", "logs", "temp"):
            (self.root / folder).mkdir(parents=True, exist_ok=True)
        self.config = self.load()
        self.save(self.config)
        return self.config

    def load(self) -> dict[str, Any]:
        try:
            supplied = json.loads(self.path.read_text(encoding="utf-8")) if self.path.exists() else {}
        except (OSError, json.JSONDecodeError):
            supplied = {}
        return _merge_defaults(DEFAULT_CONFIG, supplied)

    def save(self, config: dict[str, Any] | None = None) -> None:
        if config is not None:
            self.config = _merge_defaults(DEFAULT_CONFIG, config)
        temporary = self.path.with_suffix(".json.tmp")
        temporary.write_text(json.dumps(self.config, indent=2, ensure_ascii=False), encoding="utf-8")
        temporary.replace(self.path)

    def set_printer(self, name: str) -> None:
        self.config["printer"]["name"] = name
        self.save()
