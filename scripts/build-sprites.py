#!/usr/bin/env python3
"""Download and downscale the bundled species renders (needs network ONCE).

The web portrait shows a real Pokémon image per species, fully offline at
runtime. This script is the only place the network is touched to produce them:
it walks the same PokéAPI species index as ``build-offline-db.py`` (reusing that
script's on-disk JSON cache, so a warm cache means *only* image bytes are
fetched), pulls each default variety's **Pokémon HOME** render, downscales it to
keep the bundle small, and writes ``web/data/sprites/<slug>.png``.

Keyed by species slug — the same key the runtime uses — so form-named defaults
(deoxys -> deoxys-normal, ...) and typographic display names (Farfetch'd,
Nidoran♀) resolve without a special-case table. Missing renders are simply
skipped; the web app falls back to the Poké Ball emblem for those.

Coverage order per species: HOME render -> official artwork -> pixel sprite.

Examples:
    python3 scripts/build-sprites.py                 # all species (warm cache)
    python3 scripts/build-sprites.py --limit 12      # smoke-test the first 12
    python3 scripts/build-sprites.py --size 256      # override output box (px)
    python3 scripts/build-sprites.py --refresh       # re-download existing PNGs
"""

from __future__ import annotations

import argparse
import importlib.util
import io
import time
import urllib.request
from pathlib import Path
from typing import Any

from PIL import Image

ROOT = Path(__file__).resolve().parent.parent
SPRITE_DIR = ROOT / "web" / "data" / "sprites"


def _load_db_builder() -> Any:
    """Import build-offline-db.py by path (its name isn't a valid module id).

    Reuses its cached ``get()``, so re-running after a DB build fetches no JSON.
    """
    path = ROOT / "scripts" / "build-offline-db.py"
    spec = importlib.util.spec_from_file_location("build_offline_db", path)
    if not spec or not spec.loader:
        raise RuntimeError(f"cannot load {path}")
    mod = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(mod)
    return mod


def sprite_url(pokemon: dict[str, Any]) -> str | None:
    """Best available still render for a Pokémon record, largest first."""
    sprites = pokemon.get("sprites") or {}
    other = sprites.get("other") or {}
    home = (other.get("home") or {}).get("front_default")
    artwork = (other.get("official-artwork") or {}).get("front_default")
    return home or artwork or sprites.get("front_default")


def fetch_image(url: str, ua: dict[str, str], retries: int = 3) -> bytes:
    last: Exception | None = None
    for attempt in range(retries):
        try:
            req = urllib.request.Request(url, headers=ua)
            with urllib.request.urlopen(req, timeout=30) as r:
                return bytes(r.read())
        except Exception as exc:  # noqa: BLE001 - retried, then surfaced
            last = exc
            time.sleep(1.0 * (attempt + 1))
    raise RuntimeError(f"Failed to fetch {url}: {last}")


def save_downscaled(raw: bytes, dest: Path, size: int) -> None:
    """Fit the render inside a size×size box (aspect kept), transparent PNG."""
    img = Image.open(io.BytesIO(raw)).convert("RGBA")
    img.thumbnail((size, size), Image.LANCZOS)
    dest.parent.mkdir(parents=True, exist_ok=True)
    img.save(dest, format="PNG", optimize=True)


def main() -> None:
    ap = argparse.ArgumentParser(description=__doc__)
    ap.add_argument("--limit", type=int, default=None, help="Only fetch the first N species")
    ap.add_argument("--size", type=int, default=256, help="Output box in px (default 256)")
    ap.add_argument("--refresh", action="store_true", help="Re-download PNGs that already exist")
    ap.add_argument("--delay", type=float, default=0.02, help="Seconds to sleep between images")
    args = ap.parse_args()

    db = _load_db_builder()
    index = db.get(db.SPECIES_INDEX)
    results = index.get("results") or []
    if args.limit:
        results = results[: args.limit]
    total = len(results)
    print(f"fetching sprites for {total} species -> {SPRITE_DIR}")

    saved = skipped = missing = 0
    for i, entry in enumerate(results):
        slug = str(entry["name"])
        dest = SPRITE_DIR / f"{slug}.png"
        if dest.exists() and not args.refresh:
            skipped += 1
            continue

        species = db.get(str(entry["url"]))
        default_url = None
        for variety in species.get("varieties") or []:
            if variety.get("is_default"):
                default_url = ((variety.get("pokemon") or {}).get("url")) or None
                break
        if not default_url:
            print(f"  !! {slug}: no default variety")
            missing += 1
            continue

        url = sprite_url(db.get(default_url))
        if not url:
            print(f"  !! {slug}: no render available")
            missing += 1
            continue

        save_downscaled(fetch_image(url, db.UA), dest, args.size)
        saved += 1
        if saved % 50 == 0 or i + 1 == total:
            print(f"[{i + 1}/{total}] {slug}")
        time.sleep(args.delay)

    total_bytes = sum(p.stat().st_size for p in SPRITE_DIR.glob("*.png"))
    print(
        f"done: {saved} saved, {skipped} already present, {missing} missing; "
        f"{total_bytes / 1_048_576:.1f} MB in {SPRITE_DIR}"
    )


if __name__ == "__main__":
    main()
