"""Alias building must never resolve one lookup key to two species.

The name band on a card is what OCR sees, and it cannot read the ♀/♂ sign on
the Nidoran cards. Folding those names to ASCII therefore produces the same key
for two different species, and whichever was written last silently won — the
exact "silent wrong ID" the product rule forbids.
"""

from __future__ import annotations

import json
from pathlib import Path

from poke.offline_db import ascii_key, build_aliases

ROOT = Path(__file__).resolve().parent.parent
DB_PATH = ROOT / "data" / "offline" / "species_db.json"


def _records(*pairs: tuple[str, str]) -> dict[str, dict[str, str]]:
    return {slug: {"name": slug, "displayName": display} for slug, display in pairs}


def test_ambiguous_ascii_key_is_dropped_not_arbitrarily_assigned() -> None:
    aliases = build_aliases(_records(("nidoran-f", "Nidoran♀"), ("nidoran-m", "Nidoran♂")))

    # Neither species may claim the bare key; it is genuinely ambiguous.
    assert "nidoran" not in aliases

    # The unambiguous keys still resolve.
    assert aliases["nidoran-f"] == "nidoran-f"
    assert aliases["nidoran♀"] == "nidoran-f"
    assert aliases["nidoran-m"] == "nidoran-m"
    assert aliases["nidoran♂"] == "nidoran-m"


def test_unambiguous_ascii_key_is_kept() -> None:
    aliases = build_aliases(_records(("farfetchd", "Farfetch’d"), ("flabebe", "Flabébé")))

    # OCR drops the curly apostrophe and the accents; those folds are unique,
    # so they must still resolve.
    assert aliases["farfetchd"] == "farfetchd"
    assert aliases["flabebe"] == "flabebe"


def test_ascii_fold_never_overwrites_a_canonical_name() -> None:
    """A folded alias must not hijack a key that is some other species' real name."""
    aliases = build_aliases(_records(("real", "Real"), ("other", "Réal")))

    assert aliases["real"] == "real"  # the exact name wins over the fold


def test_every_alias_in_the_bundled_db_resolves_to_a_real_species() -> None:
    payload = json.loads(DB_PATH.read_text(encoding="utf-8"))
    by_slug, aliases = payload["bySlug"], payload["aliases"]

    unknown = {k: v for k, v in aliases.items() if v not in by_slug}
    assert not unknown, f"aliases point at missing species: {sorted(unknown)[:5]}"


def test_bundled_db_has_no_ambiguous_ascii_alias() -> None:
    """Regression guard on the shipped artifact, not just the builder."""
    payload = json.loads(DB_PATH.read_text(encoding="utf-8"))
    by_slug = payload["bySlug"]

    folded: dict[str, set[str]] = {}
    for slug, record in by_slug.items():
        folded.setdefault(ascii_key(record["displayName"]), set()).add(slug)

    ambiguous = {key for key, slugs in folded.items() if len(slugs) > 1}
    claimed = ambiguous & set(payload["aliases"])
    assert not claimed, f"ambiguous keys resolve to one species: {sorted(claimed)}"


def test_two_species_sharing_one_exact_name_fails_the_build() -> None:
    """A canonical collision is a data fault, not something to break by ordering.

    build_aliases used to assert this was "unique by construction" while nothing
    checked it — the same unenforced-invariant shape as the ambiguous fold.
    """
    import pytest

    with pytest.raises(ValueError, match="claimed by both"):
        build_aliases(_records(("alpha", "Samename"), ("beta", "samename")))
