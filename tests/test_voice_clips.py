"""Bundled voice clips must cover every species and match current narration."""

from __future__ import annotations

import hashlib
import json
from pathlib import Path

import pytest

from poke.api_client import record_to_pokemon_data
from poke.entry import build_entry

ROOT = Path(__file__).resolve().parent.parent
AUDIO_DIR = ROOT / "web" / "data" / "audio"
DB_PATH = ROOT / "data" / "offline" / "species_db.json"
MANIFEST = AUDIO_DIR / "manifest.json"


@pytest.mark.skipif(not MANIFEST.exists(), reason="voice clips not built")
def test_clips_cover_all_species_with_fresh_narration() -> None:
    payload = json.loads(DB_PATH.read_text(encoding="utf-8"))
    manifest = json.loads(MANIFEST.read_text(encoding="utf-8"))
    by_slug = payload["bySlug"]
    clips = manifest["bySlug"]

    assert set(clips) == set(by_slug), "clip set out of sync with species_db"

    for slug, record in by_slug.items():
        narration = build_entry(record_to_pokemon_data(record)).narration
        digest = hashlib.sha1(narration.encode("utf-8")).hexdigest()
        assert clips[slug]["sha1"] == digest, (
            f"stale clip for {slug} — narration changed; "
            "rerun scripts/build-voice-clips.py"
        )
        assert (AUDIO_DIR / clips[slug]["file"]).exists(), f"missing mp3 for {slug}"
