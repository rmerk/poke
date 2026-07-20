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
    ambiguous: bool = False
    """Top candidate was not separated from the runner-up; never auto-accepted."""


AMBIGUITY_MARGIN = 1.0
"""How far the top score must clear the runner-up to be auto-accepted.

Deliberately small: the coverage cap below already separates the substring
collisions that used to tie ("Char", "Mew", "Abra"), so this is only a backstop
for candidates that stay genuinely indistinguishable -- e.g. "Nidoran", where
OCR cannot read the trailing female/male sign and both species tie exactly.

It cannot grow much: "Pikchu" beats "Pichu" by only 1.4 on the real name list,
and that is a match we want to keep accepting. Widening this past that gap would
push a legitimate typo read into the search UI.
"""


BUNDLED_NAMES = Path(__file__).resolve().parent.parent / "data" / "species_names.json"


def default_species_names() -> list[str]:
    """The bundled species list (all National Dex species).

    Reads data/species_names.json, which scripts/build-offline-db.py writes
    alongside species_db.json. The embedded list below is a last-resort Gen 1
    fallback for a checkout with no data/ directory -- it must not be allowed
    to silently shadow the bundled file, or the matcher would quietly accept
    only 151 names while the DB holds every species.
    """
    try:
        data = json.loads(BUNDLED_NAMES.read_text(encoding="utf-8"))
    except (OSError, ValueError):
        return _embedded_gen1_names()
    if isinstance(data, list) and data:
        return [str(n) for n in data]
    return _embedded_gen1_names()


def _embedded_gen1_names() -> list[str]:
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
    # ensure_ascii=False keeps "Flabébé"/"Nidoran♀" readable and byte-identical
    # to what scripts/build-offline-db.py writes.
    path.write_text(
        json.dumps(names, ensure_ascii=False, indent=2) + "\n", encoding="utf-8"
    )
    return names


def coverage_cap(query: str, candidate: str) -> float:
    """Ceiling for a candidate's score, given how much of it the query covers.

    ``partial_ratio`` returns 100 whenever the query is a substring of the
    candidate, and ``WRatio`` inherits that inflation. So a truncated OCR read of
    "Char" scored a flat 100 against Charmander, Charmeleon, Charizard, Chimchar
    and Charjabug at once, and the winner fell out of sort order -- a silent
    wrong ID at full confidence, which the product rule forbids.

    Damping the partial term by the length ratio restores the penalty for the
    part of the candidate the query never accounted for. The plain ``ratio``
    term is left alone, since it is already length-aware -- that is what keeps
    "Pikchu" scoring 92 against "Pikachu" while "Char" drops to 67.
    """
    if not query or not candidate:
        return 0.0
    length_ratio = min(len(query), len(candidate)) / max(len(query), len(candidate))
    return max(
        float(fuzz.ratio(query, candidate)),
        float(fuzz.partial_ratio(query, candidate)) * length_ratio,
    )


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

    # Pull a wider pool than we return: the coverage cap below only ever lowers
    # scores, so a candidate outside a scorer's top-`limit` can deserve a place
    # in the final ranking once the inflated ones are damped down.
    pool = max(limit * 5, 25)

    scores: dict[str, float] = {}
    for scorer in (fuzz.WRatio, fuzz.QRatio, fuzz.token_sort_ratio, fuzz.partial_ratio):
        for key, score, _ in process.extract(q_key, keys, scorer=scorer, limit=pool):
            display = folded[str(key)]
            prev = scores.get(display, 0.0)
            scores[display] = max(prev, float(score))

    capped = {
        name: min(score, coverage_cap(q_key, name.casefold()))
        for name, score in scores.items()
    }

    ranked = sorted(capped.items(), key=lambda kv: kv[1], reverse=True)[:limit]
    candidates = tuple((name, score) for name, score in ranked)
    if not candidates:
        return MatchResult(name="", score=0.0, accepted=False, candidates=())

    best_name, best_score = candidates[0]
    runner_up = candidates[1][1] if len(candidates) > 1 else 0.0
    ambiguous = best_score - runner_up < AMBIGUITY_MARGIN
    accepted = best_score >= min_confidence and not ambiguous
    return MatchResult(
        name=best_name,
        score=best_score,
        accepted=accepted,
        candidates=candidates,
        ambiguous=ambiguous,
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
