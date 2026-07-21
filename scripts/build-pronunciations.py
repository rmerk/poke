#!/usr/bin/env python3
"""Generate poke/pronunciations.py from Serebii's pronunciation guide.

Like build-offline-db.py, this runs on the Mac (or CI) at build time only and
touches the network exactly once (pages cache under data/cache/pronunciation/).
The output — a `slug`-free, display-name-keyed respelling map — is baked into
the repo so neither the phone nor scripts/build-voice-clips.py needs a network
call or espeak at clip time.

Why this exists
---------------
poke/tts_text.py hands names straight to the synthesizer, which guesses at
Pokemon names ("Arceus" -> "AR-see-us", "Groudon" -> "GROW-don"). Serebii
publishes an authoritative English respelling for every species; this script
scrapes it and turns each respelling into a piper/espeak-friendly pseudo-word.

The transform (validated against espeak-ng's phonemizer, piper's frontend)
------------------------------------------------------------------------------
Serebii writes "ray-KWAY-zuh" (CAPS = stressed syllable, hyphens = syllables).
Fed verbatim, espeak spells the CAPS syllables letter-by-letter ("CHAR" ->
"C-H-A-R"), so we:
  1. lowercase and strip every non-letter -> one pseudo-word ("raykwayzuh").
     A single word lets espeak assign ONE natural stress + reduced vowels,
     which sounds far less robotic than the per-syllable stress that hyphens or
     spaces force.
  2. replace "yoo" -> "ew": espeak reads the /juː/ digraph "yoo" as /aɪ.../
     ("kyoo" -> "kai-oh"), but "ew" gives a clean /juː/ ("mew", "kew", "pew").
     This alone fixes Mewtwo, Kyurem, Mimikyu, Eiscue, Pyukumuku, Cutiefly, ...

Only names where espeak's DEFAULT reading already diverges from the guide are
kept (the "divergent" set): overriding a name espeak nails would be churn and
risk. A short SKIP set drops the handful the pseudo-word regresses — espeak
softens a hard G to a J across the merged syllables ("Gigalith" -> "jih-gah-
lith"); there the raw name is already correct, so we leave it alone.

Re-run whenever the species list changes; then rerun scripts/build-voice-clips.py
so the bundled clips speak the new text.
"""

from __future__ import annotations

import argparse
import html
import json
import re
import subprocess
import unicodedata
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
DB_PATH = ROOT / "data" / "offline" / "species_db.json"
OUT_PATH = ROOT / "poke" / "pronunciations.py"
CACHE_DIR = ROOT / "data" / "cache" / "pronunciation"
BASE_URL = "https://www.serebii.net/pokemon/pronunciation/gen{gen}pokemon.shtml"
GENERATIONS = range(1, 10)

# Serebii omits a respelling for a few punctuation-heavy names; take the value
# from its sibling entry (Farfetch'd) or its plain reading.
FALLBACK = {
    "farfetchd": "FAR-fetched",
    "sirfetchd": "SIR-fetched",
    "mr-mime": "MIS-ter-MIME",
    "mr-rime": "MIS-ter-RYME",
    "mime-jr": "mime-JOO-nyur",
    "type-null": "Type-Null",
}

# Names where the merged pseudo-word makes espeak soften a hard G to a J (or
# otherwise reads worse than the bare name). The raw name is already right for
# these, so we ship no override.
SKIP = frozenset(
    {
        "Gigalith",
        "Gimmighoul",
        "Okidogi",
        "Roggenrola",
        "Scraggy",
        "Vigoroth",
        "Cinderace",
    }
)

_NAME_RE = re.compile(r'<a href="/pokemon/([a-z0-9-]+)/">\s*([^<]+?)\s*</a>', re.I)
_TD_RE = re.compile(r'<td[^>]*class="fooinfo"[^>]*>(.*?)</td>', re.S | re.I)
_TAG_RE = re.compile(r"<[^>]+>")
_RESPELL_RE = re.compile(r"[A-Za-z'’ .\-/()]+")


def _clean(s: str) -> str:
    return html.unescape(_TAG_RE.sub("", s)).strip()


def _norm(name: str) -> str:
    """Fold a name to an ascii key for cross-referencing Serebii vs the DB."""
    n = html.unescape(name).lower().strip().replace("♀", "-f").replace("♂", "-m")
    n = unicodedata.normalize("NFKD", n).encode("ascii", "ignore").decode()
    return re.sub(r"[^a-z0-9]+", "", n)


def _fetch(gen: int, refresh: bool) -> str:
    CACHE_DIR.mkdir(parents=True, exist_ok=True)
    cached = CACHE_DIR / f"gen{gen}.html"
    if cached.exists() and not refresh:
        return cached.read_text(encoding="utf-8", errors="replace")
    url = BASE_URL.format(gen=gen)
    out = subprocess.run(
        ["curl", "-sSL", "-A", "Mozilla/5.0", url],
        capture_output=True,
        check=True,
    )
    text = out.stdout.decode("utf-8", "replace")
    cached.write_text(text, encoding="utf-8")
    return text


def scrape(refresh: bool) -> tuple[dict[str, str], dict[str, str]]:
    """Return (by_serebii_slug, by_normalized_name) -> respelling."""
    by_slug: dict[str, str] = {}
    by_name: dict[str, str] = {}
    for gen in GENERATIONS:
        page = _fetch(gen, refresh)
        cells = [(m.start(), _clean(m.group(1))) for m in _TD_RE.finditer(page)]
        for nm in _NAME_RE.finditer(page):
            slug, name = nm.group(1), _clean(nm.group(2))
            pron = None
            for pos, text in cells:
                if pos < nm.end() or not text or text.startswith("#"):
                    continue
                if _RESPELL_RE.fullmatch(text):  # the pronunciation cell
                    pron = text
                    break
            if pron:
                by_slug.setdefault(slug, pron)
                by_name.setdefault(_norm(name), pron)
    return by_slug, by_name


def spoken_form(respelling: str) -> str:
    """Serebii respelling -> a single espeak-friendly pseudo-word."""
    s = unicodedata.normalize("NFKD", respelling.lower())
    s = s.encode("ascii", "ignore").decode()
    s = re.sub(r"[^a-z]+", "", s)
    s = s.replace("yoo", "ew")
    # Merging syllables can pile up a letter ("PORE-ee-gon" -> "poreeegon"),
    # which espeak reads as an extra syllable ("por-ee-EH-gon"). No English
    # word triples a letter, so clamp any run to two ("poreegon").
    return re.sub(r"(.)\1\1+", r"\1\1", s)


def _ipa(text: str) -> str:
    out = subprocess.run(
        ["espeak-ng", "-q", "--ipa", text], capture_output=True, text=True
    )
    return out.stdout.strip()


def build_map(refresh: bool) -> dict[str, str]:
    by_slug, by_name = scrape(refresh)
    db = json.loads(DB_PATH.read_text(encoding="utf-8"))["bySlug"]
    mapping: dict[str, str] = {}
    for slug, record in db.items():
        display = record["displayName"]
        respelling = (
            by_slug.get(slug)
            or by_name.get(_norm(display))
            or by_name.get(_norm(slug))
            or FALLBACK.get(slug)
        )
        if not respelling:
            continue
        # The key is the name as it appears in narration; ♀/♂ are stripped
        # because tts_text expands them to " female"/" male" first, leaving the
        # bare "Nidoran" token to match.
        key = display.replace("♀", "").replace("♂", "").strip()
        spoken = spoken_form(respelling)
        if not spoken or key in mapping:
            continue
        # Keep only names espeak reads differently from the guide, and drop the
        # handful the pseudo-word regresses.
        if key in SKIP or _ipa(re.sub(r"[♀♂]", "", key)) == _ipa(spoken):
            continue
        mapping[key] = spoken
    return dict(sorted(mapping.items()))


def render_module(mapping: dict[str, str]) -> str:
    lines = [
        '"""Pokemon name -> espeak-friendly respelling, spoken-only.',
        "",
        "GENERATED by scripts/build-pronunciations.py from Serebii's pronunciation",
        "guide. Do not hand-edit; rerun the script. Keyed by the display name as it",
        "appears in narration; values are lowercase pseudo-words tuned for piper's",
        "espeak-ng frontend. Only names espeak mispronounces by default are listed.",
        '"""',
        "",
        "from __future__ import annotations",
        "",
        f"# {len(mapping)} entries",
        "PRONUNCIATIONS: dict[str, str] = {",
    ]
    for key, spoken in mapping.items():
        lines.append(f"    {key!r}: {spoken!r},")
    lines.append("}")
    return "\n".join(lines) + "\n"


def main() -> None:
    ap = argparse.ArgumentParser(description=__doc__)
    ap.add_argument(
        "--refresh", action="store_true", help="bypass the page cache and refetch"
    )
    args = ap.parse_args()
    mapping = build_map(args.refresh)
    OUT_PATH.write_text(render_module(mapping), encoding="utf-8")
    print(f"wrote {len(mapping)} pronunciations to {OUT_PATH.relative_to(ROOT)}")


if __name__ == "__main__":
    main()
