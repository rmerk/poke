"""Local TTS: Piper preferred, espeak-ng fallback."""

from __future__ import annotations

import shutil
import subprocess
import tempfile
from pathlib import Path
from typing import Any


class TtsError(RuntimeError):
    pass


def _which(cmd: str) -> str | None:
    return shutil.which(cmd)


def speak_espeak(text: str, config: dict[str, Any]) -> None:
    tts = config.get("tts", {})
    voice = tts.get("espeak_voice", "en")
    rate = int(tts.get("espeak_rate", 160))
    # Low pitch (espeak default is 50) for the show-Pokedex robotic monotone,
    # mirroring DEX_PITCH in web/js/tts.js.
    pitch = int(tts.get("espeak_pitch", 30))
    bin_name = "espeak-ng" if _which("espeak-ng") else "espeak"
    if not _which(bin_name):
        raise TtsError("espeak-ng / espeak not found on PATH.")
    subprocess.run(
        [bin_name, "-v", str(voice), "-s", str(rate), "-p", str(pitch), text],
        check=True,
    )


def speak_piper(text: str, config: dict[str, Any]) -> None:
    tts = config.get("tts", {})
    model = tts.get("piper_model")
    if not model:
        raise TtsError("tts.piper_model is not set in config.yaml.")
    model_path = Path(model)
    if not model_path.is_absolute():
        from poke.config import resolve_path

        model_path = resolve_path(config, model)
    if not model_path.exists():
        raise TtsError(f"Piper model not found: {model_path}")

    # Prefer piper CLI if available; else try Python API.
    piper_bin = _which("piper")
    with tempfile.NamedTemporaryFile(suffix=".wav", delete=False) as tmp:
        wav_path = Path(tmp.name)

    try:
        if piper_bin:
            proc = subprocess.run(
                [
                    piper_bin,
                    "--model",
                    str(model_path),
                    "--output_file",
                    str(wav_path),
                ],
                input=text.encode("utf-8"),
                check=True,
            )
            _ = proc
        else:
            try:
                from piper import PiperVoice
            except ImportError as exc:
                raise TtsError(
                    "piper-tts not installed and `piper` CLI not on PATH. "
                    "pip install 'poke[tts]' or install espeak-ng."
                ) from exc

            voice = PiperVoice.load(str(model_path))
            with open(wav_path, "wb") as wav_file:
                voice.synthesize(text, wav_file)

        _play_wav(wav_path)
    finally:
        if wav_path.exists():
            wav_path.unlink(missing_ok=True)


def _play_wav(path: Path) -> None:
    # pygame is already a project dependency and works cross-platform.
    import pygame

    if not pygame.mixer.get_init():
        pygame.mixer.init()
    sound = pygame.mixer.Sound(str(path))
    channel = sound.play()
    while channel.get_busy():
        pygame.time.wait(50)


def speak(text: str, config: dict[str, Any]) -> str:
    """Speak text. Returns engine name used."""
    tts = config.get("tts", {})
    if not tts.get("enabled", True):
        return "none"
    engine = str(tts.get("engine", "piper")).lower()

    if engine == "none":
        return "none"

    errors: list[str] = []
    if engine == "piper":
        try:
            speak_piper(text, config)
            return "piper"
        except TtsError as exc:
            errors.append(str(exc))
        try:
            speak_espeak(text, config)
            return "espeak"
        except TtsError as exc:
            errors.append(str(exc))
    elif engine == "espeak":
        speak_espeak(text, config)
        return "espeak"
    else:
        raise TtsError(f"Unknown tts.engine: {engine}")

    raise TtsError("TTS failed: " + " | ".join(errors))
