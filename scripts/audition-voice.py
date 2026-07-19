#!/usr/bin/env python3
"""Render one species with several "Dexter" tunings side by side to A/B.

Style tuning only — this shells out to build-voice-clips.py with different
pitch / ring-mod settings and drops each result in an audition folder as
<slug>-<preset>.mp3 so you can listen back-to-back and pick one. Once you've
chosen, rebuild all 151 clips with those numbers:

  python3 scripts/build-voice-clips.py --piper-model VOICE.onnx \
      --pitch-cents P --ring-hz R --ring-depth D

Needs the same engines as build-voice-clips.py (piper/mbrola/... + sox + lame);
runs on the Mac/CI at build time, never on the phone.

  python3 scripts/audition-voice.py --piper-model en_US-ryan-medium.onnx
"""

from __future__ import annotations

import argparse
import os
import shutil
import subprocess
import sys
import tempfile
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
BUILD = ROOT / "scripts" / "build-voice-clips.py"

# Presets sweep from a clean read to a buzzy electronic one, all in Dexter's
# mid/nasal register (positive pitch, no deepening). (pitch_cents, ring_hz,
# ring_depth).
PRESETS: dict[str, tuple[int, int, int]] = {
    "flat": (0, 0, 0),
    "dexter-light": (30, 25, 40),
    "dexter": (50, 35, 55),
    "dexter-buzzy": (60, 45, 70),
}


def main() -> None:
    ap = argparse.ArgumentParser(description=__doc__)
    ap.add_argument("--slug", default="pikachu", help="species to audition")
    ap.add_argument("--engine", default="auto",
                    choices=["auto", "piper", "mbrola", "festival", "espeak"])
    ap.add_argument("--piper-model", default=None)
    ap.add_argument("--mbrola-voice", default="us2")
    ap.add_argument("--out-dir", type=Path, default=ROOT / "audition",
                    help="where the <slug>-<preset>.mp3 files land")
    ap.add_argument("--dry-run", action="store_true",
                    help="print the build commands without running them")
    args = ap.parse_args()

    out_dir: Path = args.out_dir
    out_dir.mkdir(parents=True, exist_ok=True)
    env = {**os.environ, "PYTHONPATH": str(ROOT) + os.pathsep + os.environ.get("PYTHONPATH", "")}

    for preset, (pitch, ring_hz, ring_depth) in PRESETS.items():
        with tempfile.TemporaryDirectory() as tmp:
            cmd = [
                sys.executable, str(BUILD),
                "--only", args.slug,
                "--engine", args.engine,
                "--mbrola-voice", args.mbrola_voice,
                "--pitch-cents", str(pitch),
                "--ring-hz", str(ring_hz),
                "--ring-depth", str(ring_depth),
                "--out-dir", tmp,
            ]
            if args.piper_model:
                cmd += ["--piper-model", args.piper_model]
            print(f"[{preset}] pitch={pitch} ring={ring_hz}/{ring_depth}")
            if args.dry_run:
                print("  " + " ".join(cmd))
                continue
            subprocess.run(cmd, check=True, env=env)
            src = Path(tmp) / f"{args.slug}.mp3"
            dst = out_dir / f"{args.slug}-{preset}.mp3"
            shutil.copyfile(src, dst)
            print(f"  -> {dst}")

    if not args.dry_run:
        print(f"\nAuditions in {out_dir} — listen and pick, then rebuild all 151 "
              "with those --pitch-cents/--ring-hz/--ring-depth values.")


if __name__ == "__main__":
    main()
