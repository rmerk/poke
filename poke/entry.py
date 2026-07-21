"""Build show-host-style Pokédex narration and structured facts."""

from __future__ import annotations

import re
from dataclasses import dataclass

from poke.api_client import PokemonData

# Old-game flavor text SHOUTS the species noun; render it as the proper word.
_SHOUT_POKEMON = re.compile(r"POK[éÉ]MON")


def _clean_flavor(text: str) -> str:
    """Tidy raw flavor text for on-screen display. Mirrors web/js/entry.js:cleanFlavor.

    Speech normalization is a separate, richer pass — see poke/tts_text.py.
    """
    return re.sub(r"\s+", " ", _SHOUT_POKEMON.sub("Pokémon", text or "")).strip()


@dataclass(frozen=True)
class DexEntry:
    title: str
    dex_number: int | None
    types_line: str
    category: str
    height_weight: str
    narration: str
    description: str
    facts: tuple[str, ...]
    attribution: str = "Data: PokéAPI snapshot (offline). Fan demo only."


def build_entry(data: PokemonData) -> DexEntry:
    types_line = " / ".join(data.types) if data.types else "Unknown"
    hw = f"{data.height_m:.1f} m · {data.weight_kg:.1f} kg"
    dex_bit = f"National No. {data.dex_number}. " if data.dex_number else ""
    abilities = ", ".join(data.abilities) if data.abilities else "Unknown"

    narration = (
        f"{data.display_name}! {dex_bit}"
        f"The {data.category}. "
        f"This Pokémon is {types_line} type, standing {data.height_m:.1f} meters tall "
        f"and weighing {data.weight_kg:.1f} kilograms. "
        f"{data.flavor_text} "
        f"{data.evolution_note}"
    )
    # Keep TTS in a comfortable 15–40s band for typical voices (estimate).
    if len(narration) > 520:
        narration = narration[:500].rsplit(" ", 1)[0] + "…"

    facts = (
        f"Type: {types_line}",
        f"Category: {data.category}",
        f"Height / Weight: {hw}",
        f"Ability: {abilities}",
        data.evolution_note,
    )

    return DexEntry(
        title=data.display_name,
        dex_number=data.dex_number,
        types_line=types_line,
        category=data.category,
        height_weight=hw,
        narration=narration.strip(),
        description=_clean_flavor(data.flavor_text) or data.evolution_note,
        facts=facts,
    )
