"""OCR on fixture image (requires tesseract binary)."""

from __future__ import annotations

import shutil

import pytest

from poke.capture import load_fixture
from poke.config import load_config, project_root
from poke.match import match_from_config
from poke.ocr import extract_name


pytestmark = pytest.mark.skipif(
    shutil.which("tesseract") is None,
    reason="tesseract binary not installed",
)


def test_fixture_ocr_reads_pikachu():
    config = load_config(project_root() / "config.yaml")
    image = load_fixture(config)
    ocr = extract_name(image, config)
    match = match_from_config(ocr.text, config)
    assert match.name == "Pikachu", f"OCR={ocr.text!r} raw={ocr.raw_text!r}"
    assert match.accepted
