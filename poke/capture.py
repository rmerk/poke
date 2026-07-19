"""Camera capture and fixture loading."""

from __future__ import annotations

from pathlib import Path
from typing import Any

import cv2
import numpy as np

from poke.config import resolve_path


def load_fixture(config: dict[str, Any], path: Path | str | None = None) -> np.ndarray:
    rel = path or config.get("demo", {}).get("fixture_image", "fixtures/pikachu_card.png")
    image_path = resolve_path(config, rel)
    image = cv2.imread(str(image_path))
    if image is None:
        raise FileNotFoundError(f"Could not read fixture image: {image_path}")
    return image


def capture_frame(config: dict[str, Any]) -> np.ndarray:
    """Grab a single frame from the configured camera."""
    cam = config.get("camera", {})
    device = cam.get("device")
    index = int(cam.get("index", 0))
    source: int | str = device if device else index

    cap = cv2.VideoCapture(source)
    if not cap.isOpened():
        raise RuntimeError(
            f"Could not open camera {source!r}. "
            "Use --demo for fixture mode, or set camera.index / camera.device in config.yaml."
        )
    try:
        ok, frame = cap.read()
        if not ok or frame is None:
            raise RuntimeError("Camera opened but failed to read a frame.")
        return frame
    finally:
        cap.release()


def capture_or_fixture(config: dict[str, Any], *, demo: bool) -> np.ndarray:
    if demo:
        return load_fixture(config)
    return capture_frame(config)
