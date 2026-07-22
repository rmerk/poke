#!/usr/bin/env python3
"""Rebuild species_db.json for web/ and data/ from PokéAPI (needs network).

Covers every National Dex species the API knows about (1025 as of Gen 9).

Two API details drive the shape of this script:

1. ``/pokemon/{species-slug}`` 404s whenever the default form is named
   differently from the species (deoxys -> deoxys-normal, wormadam ->
   wormadam-plant, urshifu -> urshifu-single-strike, ...). Always resolve the
   default variety from the species record instead of guessing the URL.
2. The species record carries official localized names, so display names like
   "Ho-Oh", "Type: Null", "Flabébé", "Farfetch'd" and "Nidoran♀" come straight
   from the API. Do not hand-maintain a special-case table for them.

Responses are cached under data/cache/api (gitignored) so a re-run after a
network blip resumes instead of refetching ~3000 URLs. Pass --refresh to ignore
the cache.
"""

from __future__ import annotations

import argparse
import hashlib
import json
import time
import urllib.request
from pathlib import Path
from typing import Any

from poke.offline_db import (
    build_aliases,
    default_species_db_paths,
    write_species_db,
    write_species_names,
)

ROOT = Path(__file__).resolve().parent.parent
NAMES_PATHS = [ROOT / "data" / "species_names.json", ROOT / "web" / "data" / "species_names.json"]
CACHE_DIR = ROOT / "data" / "cache" / "api"
SPECIES_INDEX = "https://pokeapi.co/api/v2/pokemon-species?limit=100000"
UA = {"User-Agent": "pocket-pokedex/0.1 (offline warm)"}

# Gen 6+ type chart: attacking type -> defending type -> multiplier (absent = 1).
# Embedded so weakness lists need no /type/{name} fetches at build time.
TYPE_NAMES = (
    "Normal",
    "Fire",
    "Water",
    "Electric",
    "Grass",
    "Ice",
    "Fighting",
    "Poison",
    "Ground",
    "Flying",
    "Psychic",
    "Bug",
    "Rock",
    "Ghost",
    "Dragon",
    "Dark",
    "Steel",
    "Fairy",
)

TYPE_CHART: dict[str, dict[str, float]] = {
    "Normal": {"Rock": 0.5, "Ghost": 0.0, "Steel": 0.5},
    "Fire": {
        "Fire": 0.5,
        "Water": 0.5,
        "Grass": 2.0,
        "Ice": 2.0,
        "Bug": 2.0,
        "Rock": 0.5,
        "Dragon": 0.5,
        "Steel": 2.0,
    },
    "Water": {
        "Fire": 2.0,
        "Water": 0.5,
        "Grass": 0.5,
        "Ground": 2.0,
        "Rock": 2.0,
        "Dragon": 0.5,
    },
    "Electric": {
        "Water": 2.0,
        "Electric": 0.5,
        "Grass": 0.5,
        "Ground": 0.0,
        "Flying": 2.0,
        "Dragon": 0.5,
    },
    "Grass": {
        "Fire": 0.5,
        "Water": 2.0,
        "Grass": 0.5,
        "Poison": 0.5,
        "Ground": 2.0,
        "Flying": 0.5,
        "Bug": 0.5,
        "Rock": 2.0,
        "Dragon": 0.5,
        "Steel": 0.5,
    },
    "Ice": {
        "Fire": 0.5,
        "Water": 0.5,
        "Grass": 2.0,
        "Ice": 0.5,
        "Ground": 2.0,
        "Flying": 2.0,
        "Dragon": 2.0,
        "Steel": 0.5,
    },
    "Fighting": {
        "Normal": 2.0,
        "Ice": 2.0,
        "Poison": 0.5,
        "Flying": 0.5,
        "Psychic": 0.5,
        "Bug": 0.5,
        "Rock": 2.0,
        "Ghost": 0.0,
        "Dark": 2.0,
        "Steel": 2.0,
        "Fairy": 0.5,
    },
    "Poison": {
        "Grass": 2.0,
        "Poison": 0.5,
        "Ground": 0.5,
        "Rock": 0.5,
        "Ghost": 0.5,
        "Steel": 0.0,
        "Fairy": 2.0,
    },
    "Ground": {
        "Fire": 2.0,
        "Electric": 2.0,
        "Grass": 0.5,
        "Poison": 2.0,
        "Flying": 0.0,
        "Bug": 0.5,
        "Rock": 2.0,
        "Steel": 2.0,
    },
    "Flying": {
        "Electric": 0.5,
        "Grass": 2.0,
        "Fighting": 2.0,
        "Bug": 2.0,
        "Rock": 0.5,
        "Steel": 0.5,
    },
    "Psychic": {
        "Fighting": 2.0,
        "Poison": 2.0,
        "Psychic": 0.5,
        "Dark": 0.0,
        "Steel": 0.5,
    },
    "Bug": {
        "Fire": 0.5,
        "Grass": 2.0,
        "Fighting": 0.5,
        "Poison": 0.5,
        "Flying": 0.5,
        "Psychic": 2.0,
        "Ghost": 0.5,
        "Dark": 2.0,
        "Steel": 0.5,
        "Fairy": 0.5,
    },
    "Rock": {
        "Fire": 2.0,
        "Ice": 2.0,
        "Fighting": 0.5,
        "Ground": 0.5,
        "Flying": 2.0,
        "Bug": 2.0,
        "Steel": 0.5,
    },
    "Ghost": {"Normal": 0.0, "Psychic": 2.0, "Ghost": 2.0, "Dark": 0.5},
    "Dragon": {"Dragon": 2.0, "Steel": 0.5, "Fairy": 0.0},
    "Dark": {
        "Fighting": 0.5,
        "Psychic": 2.0,
        "Ghost": 2.0,
        "Dark": 0.5,
        "Fairy": 0.5,
    },
    "Steel": {
        "Fire": 0.5,
        "Water": 0.5,
        "Electric": 0.5,
        "Ice": 2.0,
        "Rock": 2.0,
        "Steel": 0.5,
        "Fairy": 2.0,
    },
    "Fairy": {
        "Fire": 0.5,
        "Fighting": 2.0,
        "Poison": 0.5,
        "Dragon": 2.0,
        "Dark": 2.0,
        "Steel": 0.5,
    },
}

STAT_KEYS = (
    ("hp", "hp"),
    ("attack", "attack"),
    ("defense", "defense"),
    ("special-attack", "specialAttack"),
    ("special-defense", "specialDefense"),
    ("speed", "speed"),
)


def get(url: str, *, refresh: bool = False, retries: int = 3) -> dict[str, Any]:
    """Fetch JSON with an on-disk cache so long runs are resumable."""
    key = hashlib.sha1(url.encode("utf-8")).hexdigest()
    cached = CACHE_DIR / f"{key}.json"
    if cached.exists() and not refresh:
        data = json.loads(cached.read_text(encoding="utf-8"))
        if isinstance(data, dict):
            return data

    last: Exception | None = None
    for attempt in range(retries):
        try:
            req = urllib.request.Request(url, headers=UA)
            with urllib.request.urlopen(req, timeout=30) as r:
                data = json.loads(r.read().decode())
            if not isinstance(data, dict):
                raise ValueError(f"Expected JSON object from {url}")
            CACHE_DIR.mkdir(parents=True, exist_ok=True)
            cached.write_text(json.dumps(data), encoding="utf-8")
            return data
        except Exception as exc:  # noqa: BLE001 - retried, then surfaced
            last = exc
            time.sleep(1.0 * (attempt + 1))
    raise RuntimeError(f"Failed to fetch {url}: {last}")


def title(name: str) -> str:
    return name.replace("-", " ").title()


def english(entries: list[dict[str, Any]], field: str) -> str | None:
    for e in entries:
        if (e.get("language") or {}).get("name") == "en":
            value = e.get(field)
            if value:
                return str(value)
    return None


def collect_evo_slugs(node: dict[str, Any], out: list[str]) -> None:
    if not node:
        return
    slug = (node.get("species") or {}).get("name")
    if slug:
        out.append(str(slug))
    for child in node.get("evolves_to") or []:
        collect_evo_slugs(child, out)


def extract_base_stats(pokemon: dict[str, Any]) -> dict[str, int]:
    by_name = {
        str((s.get("stat") or {}).get("name") or ""): int(s.get("base_stat") or 0)
        for s in pokemon.get("stats") or []
    }
    return {out_key: by_name.get(api_key, 0) for api_key, out_key in STAT_KEYS}


def weakness_types(defender_types: list[str]) -> list[str]:
    """Attacking types that hit this typing for ≥2× (dual-type product)."""
    weak: list[str] = []
    for atk in TYPE_NAMES:
        mult = 1.0
        row = TYPE_CHART.get(atk, {})
        for d in defender_types:
            mult *= float(row.get(d, 1.0))
        if mult >= 2.0:
            weak.append(atk)
    return weak


def build(limit: int | None, refresh: bool, delay: float) -> dict[str, Any]:
    index = get(SPECIES_INDEX, refresh=refresh)
    results = index.get("results") or []
    if limit:
        results = results[:limit]
    total = len(results)
    print(f"building {total} species")

    by_slug: dict[str, dict[str, Any]] = {}
    evo_chains: dict[str, list[str]] = {}
    evo_for_slug: dict[str, str] = {}

    for i, entry in enumerate(results):
        slug = str(entry["name"])
        species = get(str(entry["url"]), refresh=refresh)

        default_url: str | None = None
        for variety in species.get("varieties") or []:
            if variety.get("is_default"):
                default_url = ((variety.get("pokemon") or {}).get("url")) or None
                break
        if not default_url:
            print(f"  !! {slug}: no default variety, skipped")
            continue
        pokemon = get(default_url, refresh=refresh)

        chain_url = (species.get("evolution_chain") or {}).get("url")
        if chain_url:
            chain_url = str(chain_url)
            if chain_url not in evo_chains:
                names: list[str] = []
                collect_evo_slugs(get(chain_url, refresh=refresh).get("chain") or {}, names)
                evo_chains[chain_url] = names
            evo_for_slug[slug] = chain_url

        types = [
            title(t["type"]["name"])
            for t in sorted(pokemon.get("types", []), key=lambda x: x.get("slot", 0))
        ]
        abilities = [
            title(a["ability"]["name"].replace("-", " "))
            for a in pokemon.get("abilities", [])
            if not a.get("is_hidden")
        ] or [
            title(a["ability"]["name"].replace("-", " ")) for a in pokemon.get("abilities", [])
        ]

        display = english(species.get("names") or [], "name") or title(slug)
        category = english(species.get("genera") or [], "genus") or "Pokémon"

        flavor_raw = english(species.get("flavor_text_entries") or [], "flavor_text")
        flavor = (
            " ".join(flavor_raw.replace("\n", " ").replace("\f", " ").split())
            if flavor_raw
            else "No Pokédex entry available."
        )

        dex: int | None = None
        for pd in species.get("pokedex_numbers", []):
            if (pd.get("pokedex") or {}).get("name") == "national":
                dex = pd.get("entry_number")
                break

        gender_rate = species.get("gender_rate")
        if gender_rate is None:
            gender_rate = -1
        else:
            gender_rate = int(gender_rate)

        by_slug[slug] = {
            "name": slug,
            "displayName": display,
            "types": types,
            "heightM": pokemon.get("height", 0) / 10.0,
            "weightKg": pokemon.get("weight", 0) / 10.0,
            "abilities": abilities,
            "category": category,
            "flavorText": flavor,
            "evolutionNote": "",  # filled in once every display name is known
            "evolutionChain": [],  # filled in second pass
            "dexNumber": dex,
            "genderRate": gender_rate,
            "baseStats": extract_base_stats(pokemon),
            "weaknesses": weakness_types(types),
        }
        if (i + 1) % 50 == 0 or i + 1 == total:
            print(f"[{i + 1}/{total}] {display}")
        time.sleep(delay)

    # Second pass: evolution notes need display names for species that may not
    # have been fetched yet when their chain was first seen.
    def show(s: str) -> str:
        record = by_slug.get(s)
        return str(record["displayName"]) if record else title(s)

    for slug, record in by_slug.items():
        chain_url = evo_for_slug.get(slug)
        names = evo_chains.get(chain_url, []) if chain_url else []
        if not names:
            names = [slug]
        shown = [show(s) for s in names]
        record["evolutionChain"] = [
            {"slug": s, "displayName": shown[i]} for i, s in enumerate(names)
        ]
        if len(shown) <= 1:
            record["evolutionNote"] = (
                f"{shown[0]} does not evolve." if shown else "Evolution data unavailable."
            )
        else:
            record["evolutionNote"] = "Evolution: " + " → ".join(shown) + "."

    # Built in one pass at the end, not per-record: an ASCII fold shared by two
    # species (Nidoran♀/♂ -> "nidoran") must resolve to neither, and that is
    # only knowable once every display name is in hand.
    return {
        "version": 2,
        "count": len(by_slug),
        "bySlug": by_slug,
        "aliases": build_aliases(by_slug),
    }


def main() -> None:
    ap = argparse.ArgumentParser(description=__doc__)
    ap.add_argument("--limit", type=int, default=None, help="Only build the first N species")
    ap.add_argument("--refresh", action="store_true", help="Ignore the on-disk response cache")
    ap.add_argument("--delay", type=float, default=0.05, help="Seconds to sleep between species")
    args = ap.parse_args()

    payload = build(args.limit, args.refresh, args.delay)
    if not payload["bySlug"]:
        raise SystemExit("no species built")

    paths = default_species_db_paths(ROOT)
    write_species_db(payload, paths)
    for path in paths:
        print(f"wrote {path} ({path.stat().st_size} bytes, {payload['count']} species)")

    names = [str(r["displayName"]) for r in payload["bySlug"].values()]
    write_species_names(NAMES_PATHS, names)
    for path in NAMES_PATHS:
        print(f"wrote {path} ({len(names)} names)")


if __name__ == "__main__":
    main()
