"""build-offline-db writes the species snapshot to both Mac and web paths."""

from __future__ import annotations

import json
from pathlib import Path

from poke.offline_db import write_species_db


def test_write_species_db_writes_all_output_paths(tmp_path: Path) -> None:
    paths = [
        tmp_path / "web" / "data" / "offline" / "species_db.json",
        tmp_path / "data" / "offline" / "species_db.json",
    ]
    payload = {
        "version": 1,
        "count": 1,
        "bySlug": {"pikachu": {"name": "pikachu"}},
        "aliases": {},
    }

    written = write_species_db(payload, paths)

    assert written == paths
    for path in paths:
        assert path.exists()
        assert json.loads(path.read_text(encoding="utf-8")) == payload


def test_default_species_db_paths_include_web_and_mac() -> None:
    from poke.config import project_root
    from poke.offline_db import default_species_db_paths

    paths = default_species_db_paths(project_root())
    assert paths[0].name == "species_db.json"
    assert "web" in paths[0].parts
    assert "web" not in paths[1].parts
    assert paths[1].parts[-3:] == ("data", "offline", "species_db.json")
