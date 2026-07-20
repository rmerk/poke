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


@pytest.mark.parametrize(
    "fragment,collides_with",
    [
        ("Char", ("Charmander", "Charmeleon", "Charizard")),
        ("Nido", ("Nidorina", "Nidoqueen", "Nidorino", "Nidoking")),
        ("Poli", ("Poliwag", "Poliwhirl", "Poliwrath")),
        ("Hitmon", ("Hitmonlee", "Hitmonchan", "Hitmontop")),
    ],
)
def test_colliding_fragment_never_auto_accepted(fragment: str, collides_with: tuple[str, ...]):
    """A truncated OCR read that fits several names must not silently pick one.

    partial_ratio used to return 100 for every candidate containing the
    fragment, so the winner fell out of sort order — a silent wrong ID at full
    confidence, which the product rule forbids.
    """
    result = match_name(fragment, default_species_names(), min_confidence=72)
    assert not result.accepted, f"{fragment} → {result.name} score={result.score}"
    # The real candidates should still be offered for the user to pick from.
    offered = {name for name, _ in result.candidates}
    assert offered & set(collides_with), f"{fragment} candidates were {offered}"


@pytest.mark.parametrize("fragment,expected", [("Squirt", "Squirtle")])
def test_unique_fragment_still_resolves(fragment: str, expected: str):
    """Deliberate non-goal: a fragment matching exactly one name is still accepted.

    The defect was ties, not truncation per se. "Squirt" outscores its runner-up
    by ~19 points and can only be Squirtle, so sending it to search would cost a
    good read without preventing any wrong ID.
    """
    result = match_name(fragment, default_species_names(), min_confidence=72)
    assert result.name == expected
    assert result.accepted
    assert not result.ambiguous


def test_no_partial_candidate_ties_at_full_confidence():
    """The specific regression: several candidates pinned at exactly 100."""
    result = match_name("Char", default_species_names(), min_confidence=72)
    at_hundred = [name for name, score in result.candidates if score >= 100]
    assert at_hundred == [], f"still tied at 100: {at_hundred}"


@pytest.mark.parametrize("query,expected", [("Mew", "Mew"), ("Abra", "Abra"), ("Muk", "Muk")])
def test_short_complete_names_still_win_outright(query: str, expected: str):
    """Guard the fix against over-correction.

    Mew/Mewtwo and Abra/Kadabra tie at 100 under the old scorer, but the short
    name is a complete, correct read — it must not be pushed into search.
    """
    result = match_name(query, default_species_names(), min_confidence=72)
    assert result.name == expected
    assert result.accepted, f"{query} → {result.name} score={result.score}"
    assert not result.ambiguous


def test_indistinguishable_candidates_are_ambiguous():
    """OCR strips ♀/♂, so "Nidoran" genuinely cannot be resolved to one species."""
    result = match_name("Nidoran", default_species_names(), min_confidence=72)
    assert result.score >= 72, "expected a high-scoring but undecidable match"
    assert result.ambiguous
    assert not result.accepted
    top_two = {name for name, _ in result.candidates[:2]}
    assert top_two == {"Nidoran♀", "Nidoran♂"}


def test_ambiguous_flag_is_false_on_a_clean_match():
    result = match_name("Pikachu", default_species_names(), min_confidence=72)
    assert result.accepted
    assert not result.ambiguous


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
