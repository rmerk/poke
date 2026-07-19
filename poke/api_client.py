"""PokéAPI client with on-disk cache and offline snapshot support."""

from __future__ import annotations

import json
import re
from dataclasses import dataclass
from pathlib import Path
from typing import Any

import requests

from poke.config import resolve_path


@dataclass(frozen=True)
class PokemonData:
    name: str
    display_name: str
    types: tuple[str, ...]
    height_m: float
    weight_kg: float
    abilities: tuple[str, ...]
    category: str
    flavor_text: str
    evolution_note: str
    dex_number: int | None


def _slug(name: str) -> str:
    s = name.strip().lower()
    s = s.replace("♀", "-f").replace("♂", "-m").replace(".", "").replace("'", "")
    s = s.replace(" ", "-")
    return s


def _title(name: str) -> str:
    return name.replace("-", " ").title().replace(" Mr Mime", " Mr. Mime")


class PokeApiClient:
    def __init__(self, config: dict[str, Any]) -> None:
        api = config.get("api", {})
        offline = config.get("offline", {})
        self.base_url = str(api.get("base_url", "https://pokeapi.co/api/v2")).rstrip("/")
        self.timeout = float(api.get("timeout_seconds", 15))
        self.cache_dir = resolve_path(config, api.get("cache_dir", "data/cache"))
        self.offline = bool(offline.get("enabled", True))
        self.snapshot_dir = resolve_path(config, offline.get("snapshot_dir", "data/offline"))
        self.species_db_path = resolve_path(
            config, offline.get("species_db", "data/offline/species_db.json")
        )
        self._species_db: dict[str, Any] | None = None
        self.cache_dir.mkdir(parents=True, exist_ok=True)
        self.snapshot_dir.mkdir(parents=True, exist_ok=True)
        self._session = requests.Session()
        self._session.headers.update({"User-Agent": "pocket-pokedex/0.1 (personal demo)"})

    def _cache_path(self, kind: str, key: str) -> Path:
        safe = re.sub(r"[^a-z0-9._-]+", "_", key.lower())
        return self.cache_dir / f"{kind}_{safe}.json"

    def _snapshot_path(self, kind: str, key: str) -> Path:
        safe = re.sub(r"[^a-z0-9._-]+", "_", key.lower())
        return self.snapshot_dir / f"{kind}_{safe}.json"

    def _read_json(self, path: Path) -> dict[str, Any] | None:
        if not path.exists():
            return None
        return json.loads(path.read_text(encoding="utf-8"))

    def _write_json(self, path: Path, data: dict[str, Any]) -> None:
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_text(json.dumps(data, indent=2) + "\n", encoding="utf-8")

    def _get(self, kind: str, key: str, url: str) -> dict[str, Any]:
        snap = self._snapshot_path(kind, key)
        cached = self._cache_path(kind, key)

        if self.offline:
            data = self._read_json(snap) or self._read_json(cached)
            if data is None:
                raise RuntimeError(
                    f"Offline mode: missing snapshot for {kind}/{key}. "
                    f"Expected {snap} (or warm the cache online first)."
                )
            return data

        for path in (cached, snap):
            data = self._read_json(path)
            if data is not None:
                return data

        resp = self._session.get(url, timeout=self.timeout)
        resp.raise_for_status()
        data = resp.json()
        self._write_json(cached, data)
        return data

    def _load_species_db(self) -> dict[str, Any] | None:
        if self._species_db is not None:
            return self._species_db
        if not self.species_db_path.exists():
            return None
        self._species_db = json.loads(self.species_db_path.read_text(encoding="utf-8"))
        return self._species_db

    def _from_species_db(self, name: str) -> PokemonData | None:
        payload = self._load_species_db()
        if not payload:
            return None
        by_slug = payload.get("bySlug") or {}
        aliases = payload.get("aliases") or {}
        key = name.strip()
        lower = key.casefold()
        slug = aliases.get(lower) or aliases.get(key) or _slug(key)
        # aliases map to api slug; also try direct
        record = by_slug.get(slug) or by_slug.get(lower)
        if not record and slug in by_slug:
            record = by_slug[slug]
        if not record:
            # try alias values
            for alias_key, target in aliases.items():
                if alias_key == lower or alias_key == key.casefold():
                    record = by_slug.get(target)
                    break
        if not record:
            return None
        return PokemonData(
            name=str(record["name"]),
            display_name=str(record["displayName"]),
            types=tuple(record.get("types") or ()),
            height_m=float(record.get("heightM") or 0),
            weight_kg=float(record.get("weightKg") or 0),
            abilities=tuple(record.get("abilities") or ()),
            category=str(record.get("category") or "Pokémon"),
            flavor_text=str(record.get("flavorText") or "No Pokédex entry available."),
            evolution_note=str(record.get("evolutionNote") or "Evolution data unavailable."),
            dex_number=record.get("dexNumber"),
        )

    def fetch_pokemon(self, name: str) -> PokemonData:
        if self.offline:
            from_db = self._from_species_db(name)
            if from_db is not None:
                return from_db

        slug = _slug(name)
        # Special-case API slugs for known oddities when online / legacy snapshots
        api_slug = slug
        if slug in ("farfetchd", "mr-mime", "nidoran-f", "nidoran-m"):
            api_slug = slug
        elif name.strip() == "Farfetch'd":
            api_slug = "farfetchd"
        elif name.strip() == "Mr. Mime":
            api_slug = "mr-mime"

        pokemon = self._get("pokemon", api_slug, f"{self.base_url}/pokemon/{api_slug}")
        species_url = pokemon.get("species", {}).get("url") or f"{self.base_url}/pokemon-species/{api_slug}"
        species_key = species_url.rstrip("/").split("/")[-1]
        species = self._get("species", species_key, species_url)

        types = tuple(
            t["type"]["name"].title()
            for t in sorted(pokemon.get("types", []), key=lambda x: x.get("slot", 0))
        )
        abilities = tuple(
            a["ability"]["name"].replace("-", " ").title()
            for a in pokemon.get("abilities", [])
            if not a.get("is_hidden")
        ) or tuple(
            a["ability"]["name"].replace("-", " ").title() for a in pokemon.get("abilities", [])
        )

        height_m = float(pokemon.get("height", 0)) / 10.0
        weight_kg = float(pokemon.get("weight", 0)) / 10.0

        category = "Pokémon"
        for g in species.get("genera", []):
            if g.get("language", {}).get("name") == "en":
                category = g.get("genus") or category
                break

        flavor = ""
        for ft in species.get("flavor_text_entries", []):
            if ft.get("language", {}).get("name") == "en":
                flavor = " ".join((ft.get("flavor_text") or "").replace("\n", " ").replace("\f", " ").split())
                break

        evo_note = self._evolution_note(species)
        display = _title(str(pokemon.get("name", api_slug)))
        dex = None
        for entry in species.get("pokedex_numbers", []):
            if entry.get("pokedex", {}).get("name") == "national":
                dex = int(entry.get("entry_number"))
                break

        return PokemonData(
            name=api_slug,
            display_name=display,
            types=types,
            height_m=height_m,
            weight_kg=weight_kg,
            abilities=abilities,
            category=category,
            flavor_text=flavor or "No Pokédex entry available.",
            evolution_note=evo_note,
            dex_number=dex,
        )

    def _evolution_note(self, species: dict[str, Any]) -> str:
        evo_url = (species.get("evolution_chain") or {}).get("url")
        if not evo_url:
            return "Evolution data unavailable."
        chain_id = evo_url.rstrip("/").split("/")[-1]
        try:
            chain_doc = self._get("evolution", chain_id, evo_url)
        except Exception:
            return "Evolution data unavailable."

        names: list[str] = []

        def walk(node: dict[str, Any]) -> None:
            sp = (node.get("species") or {}).get("name")
            if sp:
                names.append(_title(sp))
            for child in node.get("evolves_to") or []:
                walk(child)

        walk(chain_doc.get("chain") or {})
        if len(names) <= 1:
            return f"{names[0]} does not evolve." if names else "Evolution data unavailable."
        return "Evolution: " + " → ".join(names) + "."


def warm_offline_snapshot(client: PokeApiClient, name: str) -> Path:
    """Fetch online and copy related cache entries into the offline snapshot dir."""
    was_offline = client.offline
    client.offline = False
    try:
        client.fetch_pokemon(name)
    finally:
        client.offline = was_offline

    slug = _slug(name)
    for pattern in ("pokemon_*.json", "species_*.json", "evolution_*.json"):
        for src in client.cache_dir.glob(pattern):
            if pattern.startswith("pokemon_") and slug not in src.stem:
                continue
            dest = client.snapshot_dir / src.name
            dest.write_text(src.read_text(encoding="utf-8"), encoding="utf-8")
    return client.snapshot_dir
