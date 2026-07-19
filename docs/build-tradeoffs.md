# Build Tradeoffs — Pocket Pokedex Card Scanner

Phase 0 research for a personal MVP: scan a physical TCG card, identify the Pokémon species, show a show-host-style Pokédex entry, and speak it. Goal: pick a workable stack, not a perfect long-term architecture.

**Change log:** Decision lock updated to **iPhone A1533 (iPhone 5s)** instead of Raspberry Pi Zero 2 W — owned phone-in-shell, built-in battery/camera/display/speaker.
**Change log (TTS):** TTS decision updated from live `speechSynthesis` to **pre-rendered show-style clips** bundled in `web/data/audio/` (built offline by `scripts/build-voice-clips.py`), with `speechSynthesis` kept as fallback. Motivation: match the show's robotic Pokédex voice, which system voices can't reproduce and which must sound identical on every device. Runtime stays fully offline; the same build-once pattern as the species DB.

Sources consulted: [PokéAPI fair use](https://pokeapi.co/docs/v2), Apple device A1533 = iPhone 5s (max iOS 12.x), [Web Speech API](https://developer.mozilla.org/en-US/docs/Web/API/Web_Speech_API), Tesseract.js. Benchmarks below are **estimates** unless labeled otherwise.

---

## Evaluation criteria (1–5)

| Criterion | Weight for MVP |
|-----------|----------------|
| Fit in small 3D-printed shell | High |
| Scan reliability on real TCG cards | High |
| Time-to-entry (&lt;5s cached target) | High |
| Offline / demo-without-hardware | High |
| BOM cost and parts availability | Medium |
| Implementation effort (~1 focused build) | High |
| Maintainability / dependency risk | Medium |
| Legal/attribution risk (personal use) | High |

---

## 1. Device brain

| Option | Shell fit | Scan / CPU | Offline demo | BOM | Effort | Battery | Score notes |
|--------|-----------|------------|--------------|-----|--------|---------|-------------|
| **iPhone A1533 (5s)** | 4 (known 4″ body) | 4 (camera + Safari) | 4 (cache + demo fixture) | **5 if owned** | 4 | **5** | Display/cam/mic/speaker/battery included |
| Pi Zero 2 W | 5 | 3 | 4 | 3 | 4 | 4 | Extra BOM: screen, cam, bank |
| Pi 5 4GB | 2 | 5 | 4 | 2 | 4 | 2 | Poor battery / shell volume |
| Pi companion + phone UI | 3 | 4 | 3 | 3 | 2 | 3 | Extra network complexity |

**Pick:** iPhone **A1533** (iPhone 5s) as the shell brain. Rationale: you already have battery, camera, screen, and speakers; App Store / modern Xcode targeting iOS 12 is painful in 2026, so the UI runtime is a **mobile Safari web app** (static files) sized for 4″.

**Runner-up:** Pi Zero 2 W if the 5s is too slow for OCR or Safari quirks block demos.

---

## 2. Card identification

| Option | Reliability | Latency | Offline | Cost | Effort | Legal |
|--------|-------------|---------|---------|------|--------|-------|
| **On-device OCR (Tesseract.js) + fuzzy match** | 3 (holofoil + old CPU) | 3 (estimate on 5s) | 5 | 5 | 4 | 5 |
| Native Vision (UIKit) | 4 | 4 | 5 | 5 | 2 (Xcode/iOS 12 tooling) | 5 |
| Cloud vision | 5 | 3 | 1 | 2 | 3 | 3 |
| Manual search-first | 5 | 4 | 5 | 5 | 5 | 5 |

**Pick:** Capture photo (file/`capture`) → optional Tesseract.js on name crop → fuzzy species match → **manual search fallback**. Never silently accept a wrong ID. Species-only for MVP.

---

## 3. What we identify

| Scope | User value | Complexity | MVP? |
|-------|------------|------------|------|
| **Species / name only** | High | Low | **Yes** |
| Full TCG (set, number, rarity) | Medium | High | Defer |

---

## 4. Pokémon data

| Option | Freshness | Offline | Fair use | Effort |
|--------|-----------|---------|----------|--------|
| PokéAPI live / localStorage | 4 | 1–4 | Cache required | 3 |
| **Bundled Gen 1 `species_db.json`** | 2 | **5** | Snapshot OK | 3 |

**Pick (locked):** Bundled offline Gen 1 DB at `web/data/offline/species_db.json` (and `data/offline/species_db.json` for Mac). **No live PokéAPI at runtime.** Rebuild with `scripts/build-offline-db.py` when online if the list changes. Attribution in UI.

---

## 5. Show-style narration

| Option | Quality | Device CPU | Privacy | Offline | Effort |
|--------|---------|------------|---------|---------|--------|
| **Templated flavor + facts** | 4 | 5 | 5 | 5 | 5 |
| Cloud / local LLM | 4–5 | 1–2 on 5s | 2–5 | 1–5 | 2 |

**Pick:** Templated narration (same copy strategy as before).

---

## 6. TTS

| Option | Voice quality | Show-voice match | Offline | 5s fit |
|--------|---------------|------------------|---------|--------|
| **Pre-rendered bundled clips** (`web/data/audio/`, built offline) | 4 | 4 (fixed robotic voice, tunable at build time) | 5 (playback only) | 5 (no synth CPU) |
| Web Speech API (`speechSynthesis`) | 3–4 (system voice) | 2–3 (device-dependent) | 5 (on-device) | 5 |
| Piper / espeak in Python | 4 | 3 | 5 | N/A on phone |
| Voice-cloning the show's actor | 5 | 5 | 1–5 | 1 | 

**Pick:** Pre-rendered clips as primary — narration is templated and deterministic, so every species' line is known at build time; `scripts/build-voice-clips.py` renders all of them once (Piper > festival kal_diphone > espeak-ng, plus sox pitch/normalize) and the phone just plays MP3s. `speechSynthesis` (tuned robotic profile, prefers the Fred voice) stays as fallback for missing clips. Cloning the actual voice actor's voice is rejected — not feasible offline and imitating a real person's voice is out of scope for a fan demo. Python Piper/espeak remains for Mac CLI demos only.

---

## 7. UI runtime

| Option | 4″ screen | Touch | Mac demo | Effort on A1533 |
|--------|-----------|-------|----------|-----------------|
| **Mobile Safari web app (static)** | 5 | 5 | 5 (same files) | **5** |
| Native UIKit (iOS 12) | 5 | 5 | 2 | 2 (Xcode support) |
| Python + pygame | 1 | 1 | 5 | 1 (not on iOS) |

**Pick:** Static web UI in `web/` as **primary**. Python package kept as Mac/headless pipeline + matcher tests — not the phone runtime.

---

## 8. Power & thermals

| Mode | Implication |
|------|-------------|
| **Battery (locked)** | iPhone internal battery; no separate power bank for compute. Session length = phone charge. |
| Shell | Leave camera window + charging port access; avoid blocking speakers/mic. Venting less critical than Pi. |
| Thermals | 5s under OCR load may warm; short demos OK (**estimate**). |

---

## 9. Legal / ToS / attribution (personal non-commercial)

| Topic | Guidance |
|-------|----------|
| Pokémon IP | Fan demo only; no commercial Nintendo asset redistribution. |
| Card capture | User’s own cards, local processing. |
| PokéAPI | Cache locally; attribute PokéAPI. |
| iOS | Personal Safari web app / sideloaded files; not an App Store product in MVP. |

---

## Recommendation

| | Stack |
|--|--------|
| **Primary MVP** | **iPhone A1533 (5s)** + Safari web app + **offline** Gen 1 DB + vendored Tesseract.js + fuzzy match + templated narration + `speechSynthesis` + phone battery |
| **Runner-up** | Pi Zero 2 W + pygame (previous lock) if phone path fails |
| **Defer** | Native App Store app, full TCG ID, cloud vision/LLM, CAD, LEDs, voice commands |

---

## Risks & mitigations (top 5)

1. **Holofoil glare / OCR misreads on 5s** — Name-band guide overlay; crop before OCR; confidence → search UI; diffuse light in shell.
2. **iOS 12 / Safari limits** — Prefer `input capture` over live `getUserMedia` (HTTPS hassle on LAN); avoid modern-only JS APIs; test on device.
3. **Tesseract.js CPU/RAM on 1 GB device** — Lazy-load OCR; timeout → search; demo fixture skips OCR when forced name.
4. **PokéAPI / IP** — Ship bundled offline snapshot only at runtime; attribution; no card-art redistribution.
5. **Serving to phone** — Same Wi‑Fi + `python -m http.server` (or open files via Mac share); document steps in README.

---

## BOM sketch

| Part | Notes |
|------|--------|
| **iPhone A1533 (iPhone 5s)** | Owned compute + display + camera + speaker + battery |
| Lightning cable / charger | Bench top-ups |
| 3D-printed Pokedex shell | Cutouts for camera, screen, ports; dimensions TBD from phone |
| Optional diffuser / tray lighting | Improve OCR on holofoil |
| Owned parts | **iPhone A1533** |
| **Not required** | Pi, HDMI panel, CSI camera, GPIO buttons, USB power bank for compute |

**Cost estimate (if phone owned):** roughly **$5–40** (filament + optional lighting/tray) vs **~$90–160** previous Pi BOM.

---

## Decision lock

Subsequent phases follow these unless a documented change is needed:

| Knob | Locked value |
|------|----------------|
| Compute | **iPhone A1533 (iPhone 5s)** |
| Display / orientation | Built-in 4″ Retina (portrait primary; CSS for narrow viewport) |
| Camera | Built-in rear camera via photo capture |
| Card ID approach | Tesseract.js OCR → fuzzy match → manual search |
| Data source + cache | **Bundled offline Gen 1 DB** (`web/data/offline/species_db.json`); no live PokéAPI at runtime |
| Narration | Templated show-style (no LLM in MVP) |
| TTS | **Bundled pre-rendered show-style clips** (`web/data/audio/`, rebuilt via `scripts/build-voice-clips.py`); `speechSynthesis` (robotic profile) as fallback |
| UI runtime | **Static web app in Safari** (`web/`); Python retained for Mac tests only |
| Power | **iPhone battery** |
| Network | **Offline required** — vendored OCR + local species DB; LAN-only serve OK |

---

## Build next checklist

1. Ship `web/` Pokedex UI runnable on A1533 Safari.
2. Keep Python matcher/API tests on Mac for pipeline confidence.
3. No Pi GPIO / pygame as primary path.
