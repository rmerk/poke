"""Matcher tests with intentional OCR typos."""

from __future__ import annotations

import json
from pathlib import Path

import pytest

from poke.config import load_config, project_root
from poke.match import default_species_names, match_from_config, match_name


@pytest.fixture
def config():
    return load_config(project_root() / "config.yaml")


def test_exact_pikachu():
    result = match_name("Pikachu", default_species_names(), min_confidence=72)
    assert result.accepted
    assert result.name == "Pikachu"
    assert result.score >= 90


@pytest.mark.parametrize(
    "typo,expected",
    [
        ("Pikchu", "Pikachu"),
        ("Pikachuu", "Pikachu"),
        ("Plkachu", "Pikachu"),
        ("CHARZARD", "Charizard"),
        ("Bulbasor", "Bulbasaur"),
        ("Squirtie", "Squirtle"),
    ],
)
def test_ocr_typos(typo: str, expected: str):
    result = match_name(typo, default_species_names(), min_confidence=72)
    assert result.name == expected
    assert result.accepted, f"{typo} → {result.name} score={result.score}"


def test_low_confidence_gibberish_not_accepted():
    result = match_name("Xzqwvuts", default_species_names(), min_confidence=72)
    assert not result.accepted


def test_empty_query_not_accepted():
    result = match_name("   ", default_species_names())
    assert not result.accepted
    assert result.score == 0


def test_match_from_config(config):
    result = match_from_config("Pikachu", config)
    assert result.accepted
    assert result.name == "Pikachu"


def test_fixture_expected_name(config):
    expected = config["demo"]["fixture_expected_name"]
    assert expected == "Pikachu"
    fixture = project_root() / config["demo"]["fixture_image"]
    assert fixture.exists(), "fixtures/pikachu_card.png must exist"


def test_species_file_roundtrip(tmp_path: Path, config):
    path = tmp_path / "names.json"
    path.write_text(json.dumps(["Pikachu", "Eevee"]), encoding="utf-8")
    config = dict(config)
    config["paths"] = {"species_names": str(path)}
    # load via match_from_config path resolution — use absolute via _root
    config["_root"] = str(tmp_path)
    config["paths"] = {"species_names": "names.json"}
    from poke.match import load_species_names

    names = load_species_names(config)
    assert names == ["Pikachu", "Eevee"]
