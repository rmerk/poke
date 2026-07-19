# Dexter-style Pokédex voice — design

> **Revision 2 (retune to the show's register):** the earlier recipe pushed the
> voice *deep* (`--pitch-cents -100`, fallback `pitch 0.5`) — a menacing low
> robot, away from the show. Show-Dexter is **mid/nasal, clipped, with an
> electronic ring-modulator edge**, not deep. So: (a) `build-voice-clips.py`
> pitch shift now defaults to neutral (`0`) plus a tunable ring-mod tone
> (`--ring-hz` / `--ring-depth`, sox amplitude modulation); (b) the
> `speechSynthesis` fallback pitch is raised (`DEX_PITCH 0.5 → 1.15`); (c) the
> espeak fallback pitch is raised (`30 → 58`). **Piper** with a flat US male
> model (e.g. `en_US-ryan-medium`) is the primary render — closest to the show.
> Voice-cloning the actual actor stays rejected. Rebuild the 151 clips on a
> Piper machine and audition (`--only pikachu`) before a full run.
>
> **Clarity:** the first renders sounded muffled/fuzzy — that was the MP3
> encode (24 kbps / 16 kHz, Nyquist ~8 kHz), not just the engine. Defaults
> are now **48 kbps / 22.05 kHz** mono (tunable via `--mp3-kbps` /
> `--mp3-rate-khz`), and ring-mod depth is lower by default since that effect
> trades clarity for the electronic edge. Piper (vs the grainy `mbrola`
> diphone) is the other half of the clarity fix.

> **Revision (same day):** the user authorized changing the decision lock to
> get closer to the show. The lock's TTS row now reads: **bundled
> pre-rendered clips** (`web/data/audio/`, built by
> `scripts/build-voice-clips.py` at build time — same build-once-offline
> pattern as the species DB) with the tuned `speechSynthesis` profile below
> kept as fallback. Narration is templated and deterministic, so all 151
> lines are renderable ahead of time with one fixed robotic voice
> (Piper > espeak-ng+mbrola us2 > festival `kal_diphone` > espeak-ng, sox
> pitch/normalize), which
> also frees the 1 GB phone from synth CPU. Voice-cloning the show's actual
> actor remains rejected (real-person voice imitation; infeasible offline).
> `manifest.json` narration hashes + `tests/test_voice_clips.py` guard
> against stale clips. The section below is the original Web-Speech-only
> design, still accurate for the fallback tier.

Goal: make the spoken entry sound like the Pokédex from the Pokémon anime
("Dexter"): a flat, deadpan, robotic delivery.

## Constraint check (decision lock)

The TTS engine is locked to the Web Speech API (`speechSynthesis`) on the
iPhone, fully offline. Reproducing the show's voice *identically* would mean
cloning a real voice actor's voice with a neural TTS model — impossible on
iOS 12 Safari offline, and a locked-decision change. So the target is the
closest achievable **style match** within the locked stack, not a clone.

## Approach (chosen)

1. **Voice selection (`web/js/tts.js`)** — rank system voices and pick the
   most robotic one available:
   - `Fred` (classic MacInTalk voice, ships on iOS; the canonical "robot
     computer" voice and the same deadpan register as the show's Pokédex)
   - then `Alex`, `Aaron`, `Daniel`
   - then any `en-US` voice, then any `en-*` voice, else engine default.
   The pick runs on every `speak()` call because iOS populates
   `getVoices()` asynchronously; querying fresh avoids a stale empty pick
   without needing `voiceschanged` (unreliable on iOS 12).
2. **Prosody flattening** — `rate 0.95` (measured, clipped delivery) and
   `pitch 0.5` (low monotone), replacing the previous `1.05/1.05` "perky"
   settings. Applies even when only a fallback voice exists, so every
   device gets the flat robotic read.
3. **Python parity (`poke/tts.py`)** — the espeak fallback gets a matching
   low-pitch profile: new `tts.espeak_pitch` config knob (default 30,
   espeak default is 50) passed as `-p`. Piper remains the preferred
   engine per the decision lock; no engine-order change.

## Alternatives rejected

- **Ship a neural voice (Piper WASM / recorded clips)** — violates the
  locked Web Speech decision, far too heavy for a 1 GB iOS 12 device.
- **Voice cloning of the show's actor** — not feasible offline, and
  imitating a specific real person's voice is out of scope for a fan demo;
  style match only.
- **SSML prosody control** — not supported by `speechSynthesis` on iOS.

## Testing

- `tsc --checkJs` stays green; `PokeTts` public API is unchanged.
- Manual: on-device Speak button → Fred-style monotone; Mac bench
  `python -m poke --force-name Pikachu` with espeak → low-pitch robotic read.
