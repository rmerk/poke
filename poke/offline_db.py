"""Offline Gen 1 species_db paths and writers."""

from __future__ import annotations

import json
from pathlib import Path
from typing import Any


def default_species_db_paths(root: Path) -> list[Path]:
    """Web (phone UI) and Mac (Python pipeline) snapshots — keep in sync."""
    return [
        root / "web" / "data" / "offline" / "species_db.json",
        root / "data" / "offline" / "species_db.json",
    ]


def write_species_db(payload: dict[str, Any], paths: list[Path]) -> list[Path]:
    """Write the same species_db payload to every path. Returns paths written."""
    body = json.dumps(payload, separators=(",", ":"))
    for path in paths:
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_text(body, encoding="utf-8")
    return list(paths)
