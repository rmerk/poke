#!/usr/bin/env python3
"""Pre-render the show-style Pokédex voice clips into web/data/audio/.

Like build-offline-db.py, this runs on the Mac (or CI) at build time only —
the phone plays the bundled MP3s fully offline. Rerun whenever the narration
template (poke/entry.py / web/js/entry.js) or species_db.json changes; the
manifest narration hashes let tests/test_voice_clips.py catch stale clips.

Engines (most show-like first):
  piper     natural deadpan read — needs --piper-model (download separately)
  mbrola    espeak-ng frontend + mbrola US male diphone voice (apt: mbrola
            mbrola-us2) — smoother than festival; default when available
  festival  kal_diphone, the classic robotic male voice (apt: festival
            festvox-kallpc16k)
  espeak    espeak-ng, most synthetic-sounding fallback
"""

from __future__ import annotations

import argparse
import hashlib
import json
import re
import shutil
import subprocess
import tempfile
from pathlib import Path

from poke.api_client import record_to_pokemon_data
from poke.entry import build_entry

ROOT = Path(__file__).resolve().parent.parent
DB_PATH = ROOT / "data" / "offline" / "species_db.json"
DEFAULT_OUT = ROOT / "web" / "data" / "audio"
MP3_KBPS = "24"
MP3_RATE_KHZ = "16"


# espeak/piper spell all-caps tokens letter by letter, and PokeAPI flavor text
# keeps the old all-caps convention ("POKéMON", "MAGIKARP", "THUNDER WAVE").
_ALLCAPS_RE = re.compile(r"\b([A-Z]{2,})('s|s)?\b")
# "National No. 25" must read "Number", but only when a figure follows.
_NUMBER_ABBR_RE = re.compile(r"\bNo\.\s*(?=\d)")
# Any casing of Poke/Pokemon, with or without the accent.
_POKEMON_RE = re.compile(r"\bPOK[EÉée]MON\b", re.IGNORECASE)
_POKE_RE = re.compile(r"\bPOK[Éé]\b", re.IGNORECASE)
# Title-casing this one yields "Ko"; it means "knock out".
_KO_RE = re.compile(r"\bKO\b")


def tts_text(narration: str) -> str:
    """Normalize narration for the synthesizers (they read ASCII best)."""
    s = narration.replace("→", " to ").replace("…", ".")
    s = s.replace("♀", " female").replace("♂", " male")
    # Before the accent is folded away, so "POKéMON" is caught as one token.
    s = _POKEMON_RE.sub("Pokemon", s)
    s = _POKE_RE.sub("Poke", s)
    s = _KO_RE.sub("knock out", s)
    s = _ALLCAPS_RE.sub(lambda m: m.group(1).title() + (m.group(2) or ""), s)
    s = _NUMBER_ABBR_RE.sub("Number ", s)
    s = s.replace("é", "e").replace("È", "E").replace("’", "'")
    return " ".join(s.split())


def check_piper_runnable() -> None:
    """A piper built for the wrong arch dies with SIGABRT mid-render; fail early
    with something actionable instead (macOS ships both x86_64 and arm64 builds,
    and an x86_64 piper can't load Homebrew's arm64 libespeak-ng)."""
    found = shutil.which("piper")
    if not found:
        raise SystemExit("piper not found on PATH")
    probe = subprocess.run(["piper", "--help"], capture_output=True)
    if probe.returncode != 0:
        detail = probe.stderr.decode("utf-8", "replace").strip().splitlines()
        raise SystemExit(
            f"piper at {found} is not runnable:\n"
            + "\n".join(detail[:3])
            + "\nInstall a piper matching this machine's architecture, or put a "
            "working one earlier on PATH."
        )


def synth_wav(
    text: str, wav: Path, engine: str, piper_model: str | None, mbrola_voice: str
) -> None:
    if engine == "piper":
        if not piper_model:
            raise SystemExit("--engine piper requires --piper-model")
        subprocess.run(
            ["piper", "--model", piper_model, "--output_file", str(wav)],
            input=text.encode("utf-8"),
            check=True,
        )
    elif engine == "mbrola":
        subprocess.run(
            [
                "espeak-ng", "-v", f"mb-{mbrola_voice}", "-s", "150",
                "-w", str(wav), text,
            ],
            check=True,
        )
    elif engine == "festival":
        subprocess.run(
            ["text2wave", "-eval", "(voice_kal_diphone)", "-o", str(wav)],
            input=text.encode("utf-8"),
            check=True,
        )
    elif engine == "espeak":
        bin_name = "espeak-ng" if shutil.which("espeak-ng") else "espeak"
        subprocess.run(
            [bin_name, "-v", "en-us", "-s", "150", "-p", "30", "-w", str(wav), text],
            check=True,
        )
    else:
        raise SystemExit(f"Unknown engine: {engine}")


def robotize(wav_in: Path, wav_out: Path, pitch_cents: int) -> None:
    """Deepen slightly toward the show's register and normalize loudness."""
    args = ["sox", str(wav_in), str(wav_out)]
    if pitch_cents:
        args += ["pitch", str(pitch_cents)]
    args += ["norm", "-3"]
    subprocess.run(args, check=True)


def encode_mp3(wav: Path, mp3: Path) -> None:
    subprocess.run(
        [
            "lame", "--quiet", "-m", "m", "-b", MP3_KBPS,
            "--resample", MP3_RATE_KHZ, str(wav), str(mp3),
        ],
        check=True,
    )


def pick_engine(requested: str, piper_model: str | None, mbrola_voice: str) -> str:
    if requested != "auto":
        return requested
    if piper_model:
        return "piper"
    mbrola_db = Path("/usr/share/mbrola") / mbrola_voice / mbrola_voice
    if shutil.which("espeak-ng") and shutil.which("mbrola") and mbrola_db.exists():
        return "mbrola"
    if shutil.which("text2wave"):
        return "festival"
    if shutil.which("espeak-ng") or shutil.which("espeak"):
        return "espeak"
    raise SystemExit("No TTS engine found (need piper, mbrola, festival, or espeak-ng).")


def main() -> None:
    ap = argparse.ArgumentParser(description=__doc__)
    ap.add_argument("--engine", choices=["auto", "piper", "mbrola", "festival", "espeak"],
                    default="auto")
    ap.add_argument("--piper-model", default=None, help="Path to a Piper .onnx voice model")
    ap.add_argument("--mbrola-voice", default="us2",
                    help="mbrola voice db name (us1/us2/us3)")
    ap.add_argument("--pitch-cents", type=int, default=-100,
                    help="sox pitch shift toward the show's low register (0 = off)")
    ap.add_argument("--out-dir", type=Path, default=DEFAULT_OUT)
    ap.add_argument("--only", nargs="*", default=None, help="Limit to these slugs")
    args = ap.parse_args()

    engine = pick_engine(args.engine, args.piper_model, args.mbrola_voice)
    if engine == "mbrola":
        engine_label = f"mbrola:{args.mbrola_voice}"
    elif engine == "piper" and args.piper_model:
        engine_label = f"piper:{Path(args.piper_model).stem}"
    else:
        engine_label = engine
    if engine == "piper":
        check_piper_runnable()
    has_sox = shutil.which("sox") is not None
    if not shutil.which("lame"):
        raise SystemExit("lame not found (needed for MP3 encoding).")
    if not has_sox:
        print("sox not found — skipping pitch/normalize post-processing")

    payload = json.loads(DB_PATH.read_text(encoding="utf-8"))
    by_slug: dict[str, dict] = payload["bySlug"]
    slugs = args.only or sorted(by_slug)

    out_dir: Path = args.out_dir
    out_dir.mkdir(parents=True, exist_ok=True)
    manifest_path = out_dir / "manifest.json"
    manifest: dict = {"version": 1, "engine": engine_label, "pitchCents": args.pitch_cents,
                      "bySlug": {}}
    if manifest_path.exists() and args.only:
        manifest = json.loads(manifest_path.read_text(encoding="utf-8"))

    with tempfile.TemporaryDirectory() as tmp:
        tmp_dir = Path(tmp)
        for i, slug in enumerate(slugs):
            record = by_slug.get(slug)
            if record is None:
                raise SystemExit(f"Unknown slug: {slug}")
            narration = build_entry(record_to_pokemon_data(record)).narration
            raw_wav = tmp_dir / f"{slug}.raw.wav"
            fx_wav = tmp_dir / f"{slug}.fx.wav"
            synth_wav(tts_text(narration), raw_wav, engine, args.piper_model,
                      args.mbrola_voice)
            if has_sox:
                robotize(raw_wav, fx_wav, args.pitch_cents)
            else:
                fx_wav = raw_wav
            mp3 = out_dir / f"{slug}.mp3"
            encode_mp3(fx_wav, mp3)
            manifest["bySlug"][slug] = {
                "file": mp3.name,
                "sha1": hashlib.sha1(narration.encode("utf-8")).hexdigest(),
            }
            print(f"[{i + 1}/{len(slugs)}] {slug} ({mp3.stat().st_size // 1024} KB)")

    manifest["count"] = len(manifest["bySlug"])
    manifest_path.write_text(json.dumps(manifest, indent=2, sort_keys=True) + "\n",
                             encoding="utf-8")
    total = sum(p.stat().st_size for p in out_dir.glob("*.mp3"))
    print(f"wrote {manifest['count']} clips + manifest to {out_dir} "
          f"({total / 1024 / 1024:.1f} MB total)")


if __name__ == "__main__":
    main()
