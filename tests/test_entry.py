"""Entry builder and offline API smoke tests."""

from __future__ import annotations

from poke.api_client import PokeApiClient
from poke.config import load_config, project_root
from poke.entry import build_entry


def test_offline_pikachu_entry():
    config = load_config(project_root() / "config.yaml")
    config.setdefault("offline", {})["enabled"] = True
    client = PokeApiClient(config)
    data = client.fetch_pokemon("Pikachu")
    entry = build_entry(data)
    assert "Pikachu" in entry.title
    assert entry.narration
    assert "PokéAPI" in entry.attribution
    assert len(entry.facts) >= 3
    # Show-host style, not raw JSON
    assert "{" not in entry.narration
    assert "type" in entry.narration.lower() or "Type" in entry.facts[0]
    # Richer dossier fields (species_db v2+)
    assert entry.gender_label in ("♂", "♀", "♂ ♀", "—")
    assert entry.base_stats.hp > 0
    assert "Ground" in entry.weaknesses
    assert len(entry.evolution_chain) >= 2
    assert any(s.display_name == "Pikachu" for s in entry.evolution_chain)
    assert "Static" in entry.abilities
