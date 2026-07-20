"""Offline species_db paths, alias building, and writers."""

from __future__ import annotations

import json
import unicodedata
from pathlib import Path
from typing import Any


def default_species_db_paths(root: Path) -> list[Path]:
    """Web (phone UI) and Mac (Python pipeline) snapshots — keep in sync."""
    return [
        root / "web" / "data" / "offline" / "species_db.json",
        root / "data" / "offline" / "species_db.json",
    ]


def write_species_names(paths: list[Path], names: list[str]) -> None:
    """Single writer for the species-name list, so every path emits the same bytes.

    ensure_ascii=False keeps "Flabébé"/"Nidoran♀" readable rather than \\uXXXX
    escaped. This logic previously lived in three places -- the build script and
    two callers in poke/match.py -- and they drifted: some escaped the non-ASCII
    names and some did not, so the bytes you got depended on which path wrote
    the file.
    """
    body = json.dumps(names, ensure_ascii=False, indent=2) + "\n"
    for path in paths:
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_text(body, encoding="utf-8")


def ascii_key(name: str) -> str:
    """Accent- and punctuation-stripped lookup key.

    "Flabébé" -> "flabebe", "Farfetch’d" -> "farfetchd", "Type: Null" ->
    "type null". This is what lets OCR reach names it cannot reproduce
    faithfully; it is deliberately lossy, which is why build_aliases has to
    police the collisions it creates.
    """
    decomposed = unicodedata.normalize("NFKD", name)
    stripped = "".join(c for c in decomposed if not unicodedata.combining(c))
    kept = [c if (c.isalnum() or c.isspace()) else " " for c in stripped]
    return " ".join("".join(kept).split()).casefold()


def build_aliases(by_slug: dict[str, Any]) -> dict[str, str]:
    """Map every lookup key to its species, dropping keys that mean two species.

    Canonical keys (the slug and the exact display name) are unique by
    construction and always win. The ASCII fold is lossy, so it can produce one
    key for two species: "Nidoran♀" and "Nidoran♂" both fold to "nidoran", and
    OCR cannot read the sign that tells them apart. Registering either would be
    a silent wrong ID at full confidence, so an ambiguous fold is registered for
    neither -- the caller falls through to search, which is the product rule.
    """
    aliases: dict[str, str] = {}
    for slug, record in by_slug.items():
        for key in (slug, str(record["displayName"]).casefold()):
            claimed = aliases.get(key)
            if claimed is not None and claimed != slug:
                # Two species answering to one exact name is a data fault, not
                # something to resolve by iteration order -- that is the bug this
                # function exists to prevent. Fail the build loudly.
                raise ValueError(
                    f"canonical key {key!r} claimed by both {claimed!r} and {slug!r}"
                )
            aliases[key] = slug

    folded: dict[str, set[str]] = {}
    for slug, record in by_slug.items():
        folded.setdefault(ascii_key(str(record["displayName"])), set()).add(slug)

    for key, slugs in folded.items():
        # len>1: genuinely ambiguous. Already present: a canonical name owns it.
        if len(slugs) == 1 and key and key not in aliases:
            aliases[key] = next(iter(slugs))
    return aliases


def write_species_db(payload: dict[str, Any], paths: list[Path]) -> list[Path]:
    """Write the same species_db payload to every path. Returns paths written."""
    body = json.dumps(payload, separators=(",", ":"))
    for path in paths:
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_text(body, encoding="utf-8")
    return list(paths)
