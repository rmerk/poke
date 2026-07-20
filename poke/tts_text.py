"""Normalize narration into the text handed to a speech synthesizer.

Lives in the package rather than inline in scripts/build-voice-clips.py so it
is importable and testable, mirroring how build-offline-db.py delegates to
poke/offline_db.py. The rendered clips are only as good as this pass: the
synthesizers read what this returns, not what entry.py built.
"""

from __future__ import annotations

import re

# PokeAPI flavor text keeps the old all-caps convention ("POKéMON", "MAGIKARP",
# "THUNDER WAVE"), and espeak/mbrola/festival spell all-caps tokens letter by
# letter. Measured against piper en_US-ryan-medium this rule is inert —
# "MAGIKARP" and "Magikarp" render identically, as do "POKEMON"/"Pokemon". What
# actually breaks piper is all-caps *plus* the accent ("POKéMON"), which
# _POKEMON_RE below already handles. Kept as insurance because pick_engine()
# falls back to espeak on any machine without piper.
_ALLCAPS_RE = re.compile(r"\b([A-Z]{2,})('s|s)?\b")
# "National No. 25" must read "Number", but only when a figure follows.
_NUMBER_ABBR_RE = re.compile(r"\bNo\.\s*(?=\d)")
# Any casing of Poke/Pokemon, with or without the accent.
_POKEMON_RE = re.compile(r"\bPOK[EÉée]MON\b", re.IGNORECASE)
_POKE_RE = re.compile(r"\bPOK[Éé]\b", re.IGNORECASE)
# Title-casing this one yields "Ko"; it means "knock out".
_KO_RE = re.compile(r"\bKO\b")
# Genuine initialisms, as opposed to PokeAPI shouting a name. These must stay
# uppercase so the synthesizer spells them out: title-casing "DNA" yields
# "Dna", which it reads as a word — the inverse of the bug _ALLCAPS_RE fixes.
_KEEP_CAPS = frozenset({"DNA"})


def _soften_caps(match: re.Match[str]) -> str:
    word, suffix = match.group(1), match.group(2) or ""
    if word in _KEEP_CAPS:
        return word + suffix
    return word.title() + suffix


def tts_text(narration: str) -> str:
    """Normalize narration for the synthesizers (they read ASCII best)."""
    s = narration.replace("→", " to ").replace("…", ".")
    s = s.replace("♀", " female").replace("♂", " male")
    # Before the accent is folded away, so "POKéMON" is caught as one token.
    s = _POKEMON_RE.sub("Pokemon", s)
    s = _POKE_RE.sub("Poke", s)
    s = _KO_RE.sub("knock out", s)
    s = _ALLCAPS_RE.sub(_soften_caps, s)
    s = _NUMBER_ABBR_RE.sub("Number ", s)
    s = s.replace("é", "e").replace("È", "E").replace("’", "'")
    return " ".join(s.split())
