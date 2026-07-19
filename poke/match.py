"""Fuzzy-match OCR text to a local species name list."""

from __future__ import annotations

import json
from dataclasses import dataclass
from pathlib import Path
from typing import Any, Iterable

from rapidfuzz import fuzz, process

from poke.config import resolve_path


@dataclass(frozen=True)
class MatchResult:
    name: str
    score: float
    accepted: bool
    candidates: tuple[tuple[str, float], ...]


def default_species_names() -> list[str]:
    """Minimal Gen 1–ish list for offline demos; full list can be generated via API."""
    return [
        "Bulbasaur",
        "Ivysaur",
        "Venusaur",
        "Charmander",
        "Charmeleon",
        "Charizard",
        "Squirtle",
        "Wartortle",
        "Blastoise",
        "Caterpie",
        "Metapod",
        "Butterfree",
        "Weedle",
        "Kakuna",
        "Beedrill",
        "Pidgey",
        "Pidgeotto",
        "Pidgeot",
        "Rattata",
        "Raticate",
        "Spearow",
        "Fearow",
        "Ekans",
        "Arbok",
        "Pikachu",
        "Raichu",
        "Sandshrew",
        "Sandslash",
        "Nidoran♀",
        "Nidorina",
        "Nidoqueen",
        "Nidoran♂",
        "Nidorino",
        "Nidoking",
        "Clefairy",
        "Clefable",
        "Vulpix",
        "Ninetales",
        "Jigglypuff",
        "Wigglytuff",
        "Zubat",
        "Golbat",
        "Oddish",
        "Gloom",
        "Vileplume",
        "Paras",
        "Parasect",
        "Venonat",
        "Venomoth",
        "Diglett",
        "Dugtrio",
        "Meowth",
        "Persian",
        "Psyduck",
        "Golduck",
        "Mankey",
        "Primeape",
        "Growlithe",
        "Arcanine",
        "Poliwag",
        "Poliwhirl",
        "Poliwrath",
        "Abra",
        "Kadabra",
        "Alakazam",
        "Machop",
        "Machoke",
        "Machamp",
        "Bellsprout",
        "Weepinbell",
        "Victreebel",
        "Tentacool",
        "Tentacruel",
        "Geodude",
        "Graveler",
        "Golem",
        "Ponyta",
        "Rapidash",
        "Slowpoke",
        "Slowbro",
        "Magnemite",
        "Magneton",
        "Farfetch'd",
        "Doduo",
        "Dodrio",
        "Seel",
        "Dewgong",
        "Grimer",
        "Muk",
        "Shellder",
        "Cloyster",
        "Gastly",
        "Haunter",
        "Gengar",
        "Onix",
        "Drowzee",
        "Hypno",
        "Krabby",
        "Kingler",
        "Voltorb",
        "Electrode",
        "Exeggcute",
        "Exeggutor",
        "Cubone",
        "Marowak",
        "Hitmonlee",
        "Hitmonchan",
        "Lickitung",
        "Koffing",
        "Weezing",
        "Rhyhorn",
        "Rhydon",
        "Chansey",
        "Tangela",
        "Kangaskhan",
        "Horsea",
        "Seadra",
        "Goldeen",
        "Seaking",
        "Staryu",
        "Starmie",
        "Mr. Mime",
        "Scyther",
        "Jynx",
        "Electabuzz",
        "Magmar",
        "Pinsir",
        "Tauros",
        "Magikarp",
        "Gyarados",
        "Lapras",
        "Ditto",
        "Eevee",
        "Vaporeon",
        "Jolteon",
        "Flareon",
        "Porygon",
        "Omanyte",
        "Omastar",
        "Kabuto",
        "Kabutops",
        "Aerodactyl",
        "Snorlax",
        "Articuno",
        "Zapdos",
        "Moltres",
        "Dratini",
        "Dragonair",
        "Dragonite",
        "Mewtwo",
        "Mew",
    ]


def load_species_names(config: dict[str, Any]) -> list[str]:
    rel = config.get("paths", {}).get("species_names", "data/species_names.json")
    path = resolve_path(config, rel)
    if path.exists():
        data = json.loads(path.read_text(encoding="utf-8"))
        if isinstance(data, list) and data:
            return [str(n) for n in data]
    names = default_species_names()
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(names, indent=2) + "\n", encoding="utf-8")
    return names


def match_name(
    query: str,
    names: Iterable[str],
    *,
    min_confidence: float = 72.0,
    limit: int = 5,
) -> MatchResult:
    q = (query or "").strip()
    name_list = list(names)
    if not q:
        return MatchResult(name="", score=0.0, accepted=False, candidates=())

    # Case-fold for OCR ALL-CAPS / mixed case; keep original display names.
    folded = {n.casefold(): n for n in name_list}
    keys = list(folded.keys())
    q_key = q.casefold()

    scores: dict[str, float] = {}
    for scorer in (fuzz.WRatio, fuzz.QRatio, fuzz.token_sort_ratio, fuzz.partial_ratio):
        for key, score, _ in process.extract(q_key, keys, scorer=scorer, limit=limit):
            display = folded[str(key)]
            prev = scores.get(display, 0.0)
            scores[display] = max(prev, float(score))

    ranked = sorted(scores.items(), key=lambda kv: kv[1], reverse=True)[:limit]
    candidates = tuple((name, score) for name, score in ranked)
    if not candidates:
        return MatchResult(name="", score=0.0, accepted=False, candidates=())

    best_name, best_score = candidates[0]
    accepted = best_score >= min_confidence
    return MatchResult(
        name=best_name,
        score=best_score,
        accepted=accepted,
        candidates=candidates,
    )


def match_from_config(query: str, config: dict[str, Any]) -> MatchResult:
    names = load_species_names(config)
    min_conf = float(config.get("ocr", {}).get("min_confidence", 72))
    return match_name(query, names, min_confidence=min_conf)


def ensure_species_file(path: Path) -> Path:
    if not path.exists():
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_text(json.dumps(default_species_names(), indent=2) + "\n", encoding="utf-8")
    return path
