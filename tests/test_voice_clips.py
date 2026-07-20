"""Bundled voice clips must cover every species and match current narration."""

from __future__ import annotations

import hashlib
import json
from pathlib import Path

import pytest

from poke.api_client import record_to_pokemon_data
from poke.entry import build_entry
from poke.tts_text import tts_text

ROOT = Path(__file__).resolve().parent.parent
AUDIO_DIR = ROOT / "web" / "data" / "audio"
DB_PATH = ROOT / "data" / "offline" / "species_db.json"
MANIFEST = AUDIO_DIR / "manifest.json"
# The shipped render settings, per the Decision lock in docs/build-tradeoffs.md:
# "Piper en_US-ryan-medium, --pitch-cents -100". Rendering with anything else
# changes how the Pokedex sounds, so a rebuild on a machine with a different
# toolchain must fail rather than quietly swap the voice mid-set.
EXPECTED_ENGINE = "piper:en_US-ryan-medium"
EXPECTED_PITCH_CENTS = -100
# The model name alone does not pin the sound. Piper 1.5.0 renders the same
# model ~2% faster than the 1.x binary the original 151 clips were built with,
# so the version is part of the voice, not just build trivia.
EXPECTED_ENGINE_VERSION = "1.5.0"


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


@pytest.mark.skipif(not MANIFEST.exists(), reason="voice clips not built")
def test_clips_match_the_text_actually_synthesized() -> None:
    """Guard the normalization layer, not just the narration template.

    tts_text() sits between narration and the synthesizer, so a pronunciation
    fix there changes the audio while leaving every raw-narration hash intact.
    That is how "DNA" shipped as "Dna": the clips were stale and CI was green.
    """
    payload = json.loads(DB_PATH.read_text(encoding="utf-8"))
    manifest = json.loads(MANIFEST.read_text(encoding="utf-8"))
    clips = manifest["bySlug"]

    for slug, record in payload["bySlug"].items():
        narration = build_entry(record_to_pokemon_data(record)).narration
        digest = hashlib.sha1(tts_text(narration).encode("utf-8")).hexdigest()
        assert clips[slug].get("ttsSha1") == digest, (
            f"stale clip for {slug} — the text handed to the synthesizer "
            "changed; rerun scripts/build-voice-clips.py"
        )


@pytest.mark.skipif(not MANIFEST.exists(), reason="voice clips not built")
def test_clips_were_rendered_with_the_shipped_voice() -> None:
    manifest = json.loads(MANIFEST.read_text(encoding="utf-8"))
    assert manifest["engine"] == EXPECTED_ENGINE, (
        f"clips were rendered with {manifest['engine']!r}, not "
        f"{EXPECTED_ENGINE!r} — the Pokedex voice would change mid-set"
    )
    assert manifest["pitchCents"] == EXPECTED_PITCH_CENTS, (
        f"clips were rendered at pitchCents={manifest['pitchCents']}, not "
        f"{EXPECTED_PITCH_CENTS} — the voice would sit in a different register"
    )
    assert manifest.get("engineVersion") == EXPECTED_ENGINE_VERSION, (
        f"clips were rendered with piper {manifest.get('engineVersion')!r}, not "
        f"{EXPECTED_ENGINE_VERSION!r} — pacing drifts between piper versions"
    )
