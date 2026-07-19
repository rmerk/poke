"""Load and validate YAML config."""

from __future__ import annotations

from pathlib import Path
from typing import Any

import yaml


def project_root() -> Path:
    return Path(__file__).resolve().parent.parent


def load_config(path: Path | str | None = None) -> dict[str, Any]:
    cfg_path = Path(path) if path else project_root() / "config.yaml"
    with cfg_path.open(encoding="utf-8") as f:
        data = yaml.safe_load(f) or {}
    if not isinstance(data, dict):
        raise ValueError(f"Config root must be a mapping: {cfg_path}")
    data["_config_path"] = str(cfg_path.resolve())
    data["_root"] = str(project_root())
    return data


def resolve_path(config: dict[str, Any], relative: str | Path) -> Path:
    root = Path(config.get("_root", project_root()))
    p = Path(relative)
    return p if p.is_absolute() else root / p
