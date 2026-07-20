# Pocket Pokedex

Personal MVP for an **iPhone A1533 (iPhone 5s)** in a 3D-printed shell: scan a TCG card, identify the **species**, show a show-host Pokédex entry, and speak it.

**Runs fully offline** — no PokéAPI, no CDN at runtime. All 1025 National Dex species, the pre-rendered voice clips, and the Tesseract OCR assets are bundled.

Stack lock: [`docs/build-tradeoffs.md`](docs/build-tradeoffs.md).

> Fan / personal non-commercial demo. Not affiliated with Nintendo / TPC / Game Freak. Offline snapshot originally derived from [PokéAPI](https://pokeapi.co).

## Primary: iPhone A1533 (Safari, offline)

**Live (GitHub Pages):** https://rmerk.github.io/poke/

```bash
cd /Users/rchoi/Personal/poke
./scripts/serve-web.sh
```

Local: phone + Mac on the **same LAN**. Safari → `http://<mac-lan-ip>:8080`  
Pages: Safari → the live URL (HTTPS). Runtime still uses only bundled species data + Tesseract (no PokéAPI / CDN).

| Control | Action |
|---------|--------|
| **Scan** | Camera / photo of the card name band |
| **Identify** | Local Tesseract.js → fuzzy match → offline entry |
| **Demo Pikachu** | Loads fixture → **forced Pikachu** (skips OCR) → entry |
| **Search** | Type a species name |
| **Speak** | Bundled pre-rendered clip; `speechSynthesis` fallback |

Low-confidence OCR opens search — never a silent wrong ID.

### Bundled offline assets

| Asset | Path |
|-------|------|
| Species DB (all 1025) | `web/data/offline/species_db.json` |
| Voice clips (one per species) | `web/data/audio/` |
| Tesseract.js + WASM + eng data | `web/vendor/tesseract/` |
| Fixture card | `web/fixtures/pikachu_card.png` |

Rebuild DB (needs network **once**): `python3 scripts/build-offline-db.py`  
(writes both `web/data/offline/species_db.json` and `data/offline/species_db.json`)

---

## Mac pipeline / tests (optional)

Python is for matcher/OCR tests and headless demos — **not** the phone UI. Defaults to **offline** + **headless**.

```bash
python3 -m venv .venv && source .venv/bin/activate
pip install -e ".[dev,ocr]"

# Fixture → OCR → entry (stdout), offline species DB
python -m poke --demo --no-tts

# Optional pygame bench UI (not used on the phone)
python -m poke --ui --demo --no-tts

# Allow live PokéAPI only if you opt in
python -m poke --online --force-name Pikachu --no-tts

# Typecheck + tests
mypy
npx -y -p typescript@5.6.3 tsc -p web/jsconfig.json --noEmit
pytest
```

## Layout

| Path | Role |
|------|------|
| [`web/`](web/) | **Primary** offline Safari app |
| [`docs/build-tradeoffs.md`](docs/build-tradeoffs.md) | Decision lock |
| [`poke/`](poke/) | Mac pipeline / tests |
