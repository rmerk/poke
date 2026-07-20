# CLAUDE.md

Guidance for AI assistants working in this repository.

## What this is

**Pocket Pokedex** — a personal, non-commercial fan MVP. Scan a physical Pokémon
TCG card, identify the **species** (name only), show a show-host-style Pokédex
entry, and speak it aloud.

The **primary target is an iPhone A1533 (iPhone 5s, max iOS 12.x)** running a
static **Safari web app**, housed in a 3D-printed Pokédex shell. The App
Store / native path was rejected because iOS 12 tooling is painful in 2026 (see
`docs/build-tradeoffs.md`).

**Everything runs fully offline at runtime.** No PokéAPI, no CDN. Gen 1 species
data and the Tesseract OCR engine are bundled into the repo. The network is only
touched *once*, offline, when rebuilding the bundled DB.

> This is a fan/personal demo. Not affiliated with Nintendo / TPC / Game Freak.
> Data is an offline snapshot originally derived from [PokéAPI](https://pokeapi.co).

## Two codebases, one project

There are **two independent implementations** of the same pipeline. They share
data and conventions but no code:

| Path | Role | Language | Runs where |
|------|------|----------|------------|
| `web/` | **PRIMARY** — the actual product | Vanilla JS (ES2017), no framework, no build step | iPhone Safari (offline) |
| `poke/` | Secondary — matcher/OCR tests + headless bench demos | Python 3.11+ | Mac / CI (not the phone) |

**When making feature changes, treat `web/` as canonical.** The Python package
exists to give pipeline confidence (fuzzy match, OCR, entry building) via tests
on a Mac. Do **not** assume Python changes reach the phone — they don't.

The pipeline is the same on both sides:

```
photo → crop name band → OCR (Tesseract) → fuzzy match to Gen 1 names
     → if confident: look up species in offline DB → build show-host entry → speak
     → if NOT confident: open search UI (never a silent wrong ID)
```

## Repository layout

```
web/                         PRIMARY offline Safari app
  index.html                 Screens: idle / busy / preview / search / entry / error
  css/app.css                Red Pokédex styling, 4" viewport
  js/
    app.js                   UI controller + screen state machine (IIFE, window globals)
    ocr.js       → PokeOcr   Tesseract.js worker, name-band crop, 15s timeout → search
    match.js     → PokeMatch Levenshtein + partial-ratio fuzzy match (iOS 12 friendly)
    api.js       → PokeApi   Loads offline species_db.json, resolves by slug/alias
    entry.js     → PokeEntry Builds the templated show-host narration
    tts.js       → PokeTts   Bundled voice clips (audio) + speechSynthesis fallback
    globals.d.ts             Shared TS types for checkJs
  jsconfig.json              tsc --checkJs config (strict)
  data/offline/species_db.json   Bundled Gen 1 DB (phone copy)
  data/species_names.json        Species name list (phone copy)
  data/audio/                    Pre-rendered show-style voice clips (<slug>.mp3
                                 + manifest.json with narration hashes; phone only)
  vendor/tesseract/          Vendored Tesseract.js + WASM + eng.traineddata (no CDN)
  fixtures/pikachu_card.png  Demo fixture image

poke/                        Secondary Python pipeline (Mac / tests)
  __main__.py                CLI entrypoint (argparse); headless by default
  config.py                  Loads config.yaml, path resolution
  capture.py                 Camera capture (OpenCV) or fixture load
  ocr.py                     OpenCV preprocess + pytesseract name extraction
  match.py                   rapidfuzz multi-scorer match; default Gen 1 name list
  identify.py                OCR text → match → resolved name (or None → search)
  api_client.py              Offline species_db lookup; optional live PokéAPI w/ cache
  entry.py                   Templated show-host DexEntry builder
  tts_text.py                Narration → synthesizer text (all-caps, accents,
                             "No." → "Number"); used by build-voice-clips.py
  tts.py                     Piper preferred, espeak-ng fallback (Mac/Pi only)
  ui.py                      Optional pygame bench UI (NOT used on the phone)
  gpio_input.py              Optional Raspberry Pi GPIO buttons (legacy/no-op off-Pi)

scripts/
  serve-web.sh               Serve web/ over LAN via python http.server (default :8080)
  build-offline-db.py        Rebuild species_db.json from PokéAPI (needs network ONCE)
  build-voice-clips.py       Re-render web/data/audio/ voice clips from the offline DB
                             (--only <slug> for one clip, then --refresh-manifest
                             to rehash the rest without re-rendering them)
                             (build-time only; piper > mbrola us2 > festival kal > espeak-ng.
                             Shipped clips: piper en_US-ryan-medium, --pitch-cents -100)

data/offline/species_db.json Bundled Gen 1 DB (Mac copy — mirror of web/ copy)
data/species_names.json      Species name list (Mac copy)
config.yaml                  Config for the PYTHON pipeline only (not the web app)
docs/build-tradeoffs.md      DECISION LOCK — read before changing the stack
tests/                       pytest suite for the Python pipeline
fixtures/                    Python-side fixture image + expected.json
```

## The offline species DB (most important shared artifact)

`species_db.json` is the single source of truth for Pokémon data at runtime.
**Two identical copies must stay in sync:** `web/data/offline/species_db.json`
(phone) and `data/offline/species_db.json` (Mac). Never hand-edit one without
the other.

Shape (see `web/js/globals.d.ts` for the full type):

```json
{
  "version": 1,
  "count": 151,
  "bySlug": { "pikachu": { "name": "pikachu", "displayName": "Pikachu",
                           "types": ["Electric"], "heightM": 0.4, "weightKg": 6.0,
                           "abilities": [...], "category": "Mouse Pokémon",
                           "flavorText": "...", "evolutionNote": "...", "dexNumber": 25 } },
  "aliases": { "pikachu": "pikachu", "raichu": "raichu" }   // casefolded name/slug → slug
}
```

**To regenerate** (the only time the network is used): `python3 scripts/build-offline-db.py`.
It reads `data/species_names.json`, fetches from PokéAPI, and writes **both**
copies via `poke/offline_db.py:write_species_db`. If you change species coverage,
edit `data/species_names.json` then rerun this script — do not edit the DB by hand.

## Key conventions & invariants

- **Offline is mandatory at runtime.** The web app never fetches from the
  network. The Python pipeline defaults to offline (`offline.enabled: true`); live
  PokéAPI is opt-in only via `--online`. Don't introduce runtime CDN/API calls.
- **Never a silent wrong ID.** If OCR/match confidence is below threshold
  (`min_confidence`, default **72** on a 0–100 scale, mirrored as `MIN_CONF` in
  `web/js/ocr.js`), the UI must fall back to search with candidates — never
  auto-accept. This is a core product rule from the tradeoffs doc.
- **OCR must never hang.** `web/js/ocr.js` enforces a 15s timeout that opens
  search on expiry. The 1GB iOS 12 device is the constraint.
- **Demo path skips OCR.** "Demo Pikachu" loads the fixture and *forces* the name
  Pikachu (`DEMO_FORCE_NAME`), bypassing OCR — a reliable demo on weak hardware.
- **iOS 12 / Safari compatibility.** `web/js/` targets **ES2017**, uses `var` and
  IIFEs with `window.*` globals (`PokeApi`, `PokeMatch`, `PokeEntry`, `PokeOcr`,
  `PokeTts`), no ES modules, no framework, no build/bundle step. Avoid
  modern-only JS APIs. `jsconfig.json` enforces this via strict `checkJs`.
- **Narration is templated, not LLM-generated.** `entry.js` / `entry.py` build the
  show-host string from DB fields; keep both in sync. Narration is capped (~520
  chars → truncated at ~500) to keep TTS in a comfortable duration band.
- **The Pokédex voice is pre-rendered.** `web/data/audio/<slug>.mp3` clips (one
  robotic show-style voice, built by `scripts/build-voice-clips.py`) are the
  primary speech path; `speechSynthesis` (tuned robotic profile in `tts.js`) is
  the fallback only. If narration templates, `poke/tts_text.py`, or
  `species_db.json` change, rerun the script — `tests/test_voice_clips.py`
  compares both the narration hash and `ttsSha1` (the hash of the text actually
  handed to the synthesizer) and fails on stale clips. Rebuild with the same
  engine the clips were made with; `manifest.json`'s `engine` field records it
  and the test pins it to `piper:en_US-ryan-medium`, otherwise the voice
  silently changes mid-set. Re-rendering needs `pip install -e ".[tts]"` plus a
  voice model (`~/.piper/en_US-ryan-medium.onnx`); note a standalone x86_64
  `piper` binary cannot load Homebrew's arm64 `libespeak-ng` on Apple Silicon,
  which is what `check_piper_runnable()` catches.
- **Attribution stays in the UI.** Every entry carries a PokéAPI + fan-demo
  attribution line. Don't remove it.
- **Python types are strict.** mypy runs with `disallow_incomplete_defs`,
  `check_untyped_defs`, etc. Keep full type annotations; frozen dataclasses are
  the norm for result objects.
- **Name-band crop region** is `[x, y, w, h]` fractions, default
  `[0.08, 0.04, 0.55, 0.14]`, shared between `poke/ocr.py` (from config) and
  `web/js/ocr.js` (hardcoded default). Keep them consistent.

## Development workflows

### Web app (primary)

```bash
./scripts/serve-web.sh          # serves web/ on LAN at :8080 (prints Mac + phone URLs)
# Phone + Mac on same LAN → Safari → http://<mac-lan-ip>:8080
```

Live deploy: pushing to `main` publishes `web/` to GitHub Pages
(`.github/workflows/pages.yml`) → https://rmerk.github.io/poke/. There is **no
build step** — the deployed files are exactly what's in `web/`.

### Python pipeline (secondary / tests)

```bash
python3 -m venv .venv && source .venv/bin/activate
pip install -e ".[dev,ocr]"

python -m poke --demo --no-tts                 # fixture → OCR → entry to stdout (offline)
python -m poke --ui --demo --no-tts            # optional pygame bench UI (not the phone)
python -m poke --force-name Pikachu --no-tts   # skip OCR, look up a name
python -m poke --online --force-name Pikachu   # allow live PokéAPI (opt-in only)
python -m poke --warm-offline Pikachu          # fetch into data/offline snapshot (network)
```

The Python CLI is **headless by default**; `--ui` is a Mac-only pygame bench, not
the phone runtime.

### Checks (match CI exactly — `.github/workflows/ci.yml`)

```bash
mypy                                                        # Python typecheck
npx -y -p typescript@5.6.3 tsc -p web/jsconfig.json --noEmit  # web JS typecheck (checkJs)
pytest                                                      # Python tests
```

CI runs all three on every PR and on push to `main`. Run them locally before
pushing. Note: `tests/test_ocr_fixture.py` is skipped unless the `tesseract`
binary is on PATH; CI installs it via the `[ocr]` extra + system package.

## When you change things — checklists

**Adding/changing species data:** edit `data/species_names.json` → run
`scripts/build-offline-db.py` → confirm **both** `species_db.json` copies updated
→ run `scripts/build-voice-clips.py` (clips track the DB) → run `pytest`.

**Changing narration (`entry.js` / `entry.py`):** keep both in sync, then rerun
`scripts/build-voice-clips.py` so the bundled clips speak the new text
(`tests/test_voice_clips.py` will fail until you do).

**Changing the pipeline (match/OCR/entry logic):** the change likely needs to be
made in **both** `web/js/` and `poke/` to keep parity. Update tests in `tests/`.
Run the full check suite.

**Changing the stack / a locked decision** (device, offline requirement, data
source, TTS engine, UI runtime): update `docs/build-tradeoffs.md` — it is the
decision lock and its "Decision lock" table is authoritative. Don't silently
diverge from it.

**Touching `web/js/`:** stay ES2017, `var`, `window` globals, no modules/build.
Update `web/js/globals.d.ts` if you add/change a public API shape, and keep
`tsc --checkJs` green.

## Git / contribution

- Development branch for this work: `claude/claude-md-documentation-z1l7de`.
- Push with `git push -u origin <branch>`; do not push to `main` directly.
- CI (mypy + tsc + pytest) must pass. GitHub Pages deploys from `main`.
- Do **not** open a PR unless explicitly asked.
