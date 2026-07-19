"""OCR preprocess + Tesseract name extraction."""

from __future__ import annotations

from dataclasses import dataclass
from typing import Any

import cv2
import numpy as np


@dataclass(frozen=True)
class OcrResult:
    text: str
    raw_text: str


def crop_name_region(image: np.ndarray, config: dict[str, Any]) -> np.ndarray:
    region = config.get("camera", {}).get("name_region", [0.08, 0.04, 0.55, 0.14])
    x_f, y_f, w_f, h_f = (float(v) for v in region)
    h, w = image.shape[:2]
    x0 = max(0, int(w * x_f))
    y0 = max(0, int(h * y_f))
    x1 = min(w, int(w * (x_f + w_f)))
    y1 = min(h, int(h * (y_f + h_f)))
    if x1 <= x0 or y1 <= y0:
        return image
    return image[y0:y1, x0:x1]


def preprocess_for_ocr(image: np.ndarray) -> np.ndarray:
    """Grayscale, upscale, CLAHE, adaptive threshold — helps with glare (estimate)."""
    if len(image.shape) == 3:
        gray = cv2.cvtColor(image, cv2.COLOR_BGR2GRAY)
    else:
        gray = image
    # Upscale small crops for Tesseract
    scale = 3 if max(gray.shape) < 400 else 2
    gray = cv2.resize(gray, None, fx=scale, fy=scale, interpolation=cv2.INTER_CUBIC)
    clahe = cv2.createCLAHE(clipLimit=2.0, tileGridSize=(8, 8))
    enhanced = clahe.apply(gray)
    blurred = cv2.GaussianBlur(enhanced, (3, 3), 0)
    binary = cv2.adaptiveThreshold(
        blurred, 255, cv2.ADAPTIVE_THRESH_GAUSSIAN_C, cv2.THRESH_BINARY, 31, 10
    )
    return binary


def _clean_ocr_text(raw: str) -> str:
    lines = [ln.strip() for ln in raw.splitlines() if ln.strip()]
    text = " ".join(lines) if lines else raw.strip()
    # Keep letters, spaces, hyphens, apostrophes (species-like tokens)
    cleaned = "".join(ch if ch.isalpha() or ch in " -'" else " " for ch in text)
    return " ".join(cleaned.split())


def extract_name(image: np.ndarray, config: dict[str, Any]) -> OcrResult:
    """OCR the name band. Requires tesseract + pytesseract when not using forced text."""
    cropped = crop_name_region(image, config)
    processed = preprocess_for_ocr(cropped)

    try:
        import pytesseract
    except ImportError as exc:
        raise RuntimeError(
            "pytesseract is not installed. Install with: pip install 'poke[ocr]' "
            "and install the tesseract binary."
        ) from exc

    ocr_cfg = config.get("ocr", {})
    cmd = ocr_cfg.get("tesseract_cmd")
    if cmd:
        pytesseract.pytesseract.tesseract_cmd = cmd

    psm = int(ocr_cfg.get("psm", 7))
    # Avoid quotes/apostrophes in -c values — pytesseract passes config through shlex.
    tess_config = f"--psm {psm} -c tessedit_char_whitelist=ABCDEFGHIJKLMNOPQRSTUVWXYZabcdefghijklmnopqrstuvwxyz-"
    raw = pytesseract.image_to_string(processed, config=tess_config)
    text = _clean_ocr_text(raw)
    return OcrResult(text=text, raw_text=raw)
