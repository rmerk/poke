"""Narration must reach the synthesizer pronounceable.

These cases are all drawn from the real Gen 1 narration corpus; the all-caps
rule exists because PokeAPI flavor text still shouts, and espeak/piper spell
fully-uppercase tokens letter by letter.
"""

from __future__ import annotations

import pytest

from poke.tts_text import tts_text


@pytest.mark.parametrize(
    "raw, expected",
    [
        # PokeAPI's shouting convention — title-case so they read as words.
        ("MAGIKARP", "Magikarp"),
        ("THUNDER WAVE", "Thunder Wave"),
        ("MAGNEMITEs", "Magnemites"),  # plural survives
        ("SLOWPOKE's", "Slowpoke's"),  # possessive survives
        ("POKéMON", "Pokemon"),
        ("POKé BALL", "Poke Ball"),
        # Not all-caps runs — must be left alone.
        ("It fled", "It fled"),
        ("Mr. Mime", "Mr. Mime"),
        ("I", "I"),
    ],
)
def test_shouted_flavor_text_reads_as_words(raw: str, expected: str) -> None:
    assert tts_text(raw) == expected


@pytest.mark.parametrize(
    "raw, expected",
    [
        ("National No. 25.", "National Number 25."),
        ("No, it fled.", "No, it fled."),  # only expands before a figure
    ],
)
def test_number_abbreviation(raw: str, expected: str) -> None:
    assert tts_text(raw) == expected


def test_ko_expands_to_words() -> None:
    assert tts_text("a boomerang to KO targets") == "a boomerang to knock out targets"


@pytest.mark.parametrize("acronym", ["DNA"])
def test_initialisms_are_not_title_cased(acronym: str) -> None:
    """Genuine initialisms must stay uppercase so they are spelled out.

    Title-casing DNA yields "Dna", which the synthesizer reads as a word —
    the inverse of the bug the all-caps rule was added to fix.
    """
    assert tts_text(acronym) == acronym


def test_mewtwo_dna_line_is_spelled_out() -> None:
    raw = "years of horrific gene splicing and DNA engineering experiments"
    assert "DNA" in tts_text(raw)
