"""Offline species_db + identify_card contract (review fixes)."""

from __future__ import annotations

from poke.api_client import PokeApiClient
from poke.config import load_config, project_root
from poke.identify import IdentifyResult, identify_card
from poke.match import MatchResult


def test_config_defaults_offline():
    config = load_config(project_root() / "config.yaml")
    assert config["offline"]["enabled"] is True


def test_offline_species_db_charizard_no_network():
    config = load_config(project_root() / "config.yaml")
    config["offline"]["enabled"] = True
    # Point at the bundled DB; must not need per-species pokeapi JSON files
    config["offline"]["species_db"] = "data/offline/species_db.json"
    client = PokeApiClient(config)
    data = client.fetch_pokemon("Charizard")
    assert data.display_name == "Charizard"
    assert "Fire" in data.types or "fire" in [t.lower() for t in data.types]
    assert data.flavor_text
    assert data.evolution_note


def test_identify_card_force_name_returns_resolved_name():
    config = load_config(project_root() / "config.yaml")
    result = identify_card(config, image=None, force_name="Pikachu")
    assert isinstance(result, IdentifyResult)
    assert result.resolved_name == "Pikachu"
    assert result.ocr_text == "Pikachu"
    assert isinstance(result.match, MatchResult)
    assert result.match.accepted
