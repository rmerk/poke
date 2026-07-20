---
description: Pocket Pokedex workspace memory — offline A1533 Safari app and dual Gen 1 DB paths.
applyTo: "web/**/*,poke/**/*,scripts/build-offline-db.py,docs/build-tradeoffs.md"
---

# Pocket Pokedex Memory

Offline iPhone A1533 Safari MVP with a Mac test pipeline sharing one Gen 1 snapshot.

## Keep web and Mac species_db in lockstep

`poke.offline_db.default_species_db_paths` + `write_species_db` are the only writers for Gen 1 offline data. Rebuild via `scripts/build-offline-db.py` (needs network once); never edit only one of `web/data/offline/species_db.json` or `data/offline/species_db.json`.

## Phone UX contracts from the tradeoff lock

- Primary UI is `web/` in Safari; Python is Mac/tests only.
- OCR → fuzzy match → search on low confidence or timeout (15s soft); never silent wrong ID.
- Demo Pikachu uses forced name and skips OCR.
- No live PokéAPI at runtime; vendored Tesseract under `web/vendor/`.
