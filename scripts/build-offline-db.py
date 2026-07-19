#!/usr/bin/env python3
"""Rebuild web/data/offline/species_db.json from PokéAPI (one-time; needs network)."""

from __future__ import annotations

import json
import time
import urllib.request
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
NAMES_PATH = ROOT / "data" / "species_names.json"
OUT_PATH = ROOT / "web" / "data" / "offline" / "species_db.json"
UA = {"User-Agent": "pocket-pokedex/0.1 (offline warm)"}


def get(url: str) -> dict:
    req = urllib.request.Request(url, headers=UA)
    with urllib.request.urlopen(req, timeout=30) as r:
        data = json.loads(r.read().decode())
    if not isinstance(data, dict):
        raise ValueError(f"Expected JSON object from {url}")
    return data


def api_slug(name: str) -> str:
    special = {
        "Farfetch'd": "farfetchd",
        "Mr. Mime": "mr-mime",
        "Nidoran♀": "nidoran-f",
        "Nidoran♂": "nidoran-m",
    }
    if name in special:
        return special[name]
    s = name.strip().lower().replace(".", "").replace("'", "").replace(" ", "-")
    return s


def title(name: str) -> str:
    return name.replace("-", " ").title()


def walk_evo(node: dict, names_out: list[str]) -> None:
    if not node:
        return
    sp = (node.get("species") or {}).get("name")
    if sp:
        names_out.append(title(sp))
    for child in node.get("evolves_to") or []:
        walk_evo(child, names_out)


def main() -> None:
    names = json.loads(NAMES_PATH.read_text(encoding="utf-8"))
    by_slug: dict[str, dict] = {}
    aliases: dict[str, str] = {}

    for i, name in enumerate(names):
        slug = api_slug(name)
        pokemon = get(f"https://pokeapi.co/api/v2/pokemon/{slug}")
        species = get(pokemon["species"]["url"])
        evo = None
        evo_url = (species.get("evolution_chain") or {}).get("url")
        if evo_url:
            evo = get(evo_url)

        types = [
            title(t["type"]["name"])
            for t in sorted(pokemon.get("types", []), key=lambda x: x.get("slot", 0))
        ]
        abilities = [
            title(a["ability"]["name"].replace("-", " "))
            for a in pokemon.get("abilities", [])
            if not a.get("is_hidden")
        ] or [
            title(a["ability"]["name"].replace("-", " "))
            for a in pokemon.get("abilities", [])
        ]

        category = "Pokémon"
        for g in species.get("genera", []):
            if g.get("language", {}).get("name") == "en":
                category = g.get("genus") or category
                break

        flavor = "No Pokédex entry available."
        for ft in species.get("flavor_text_entries", []):
            if ft.get("language", {}).get("name") == "en":
                flavor = " ".join(
                    (ft.get("flavor_text") or "").replace("\n", " ").replace("\f", " ").split()
                )
                break

        evo_names: list[str] = []
        if evo:
            walk_evo(evo.get("chain") or {}, evo_names)
        if len(evo_names) <= 1:
            evo_note = f"{evo_names[0]} does not evolve." if evo_names else "Evolution data unavailable."
        else:
            evo_note = "Evolution: " + " → ".join(evo_names) + "."

        dex = None
        for entry in species.get("pokedex_numbers", []):
            if entry.get("pokedex", {}).get("name") == "national":
                dex = entry.get("entry_number")
                break

        display = name if "Nidoran" in name or name in ("Farfetch'd", "Mr. Mime") else title(pokemon["name"])
        record = {
            "name": slug,
            "displayName": display,
            "types": types,
            "heightM": pokemon.get("height", 0) / 10.0,
            "weightKg": pokemon.get("weight", 0) / 10.0,
            "abilities": abilities,
            "category": category,
            "flavorText": flavor,
            "evolutionNote": evo_note,
            "dexNumber": dex,
        }
        by_slug[slug] = record
        aliases[display.casefold()] = slug
        aliases[name.casefold()] = slug
        aliases[slug] = slug
        print(f"[{i + 1}/{len(names)}] {display}")
        time.sleep(0.05)

    OUT_PATH.parent.mkdir(parents=True, exist_ok=True)
    payload = {"version": 1, "count": len(by_slug), "bySlug": by_slug, "aliases": aliases}
    OUT_PATH.write_text(json.dumps(payload, separators=(",", ":")), encoding="utf-8")
    print(f"wrote {OUT_PATH} ({OUT_PATH.stat().st_size} bytes, {len(by_slug)} species)")


if __name__ == "__main__":
    main()
