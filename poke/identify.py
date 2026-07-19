"""Card identification: OCR text → fuzzy match → optional resolved name."""

from __future__ import annotations

from dataclasses import dataclass
from typing import Any

from poke.match import MatchResult, match_from_config
from poke.ocr import extract_name


@dataclass(frozen=True)
class IdentifyResult:
    ocr_text: str
    match: MatchResult
    resolved_name: str | None
    """Species display name when match.accepted; else None (search fallback)."""


def identify_card(
    config: dict[str, Any],
    image: Any | None = None,
    *,
    force_name: str | None = None,
) -> IdentifyResult:
    if force_name:
        match = match_from_config(force_name, config)
        name = match.name if match.accepted else force_name
        return IdentifyResult(ocr_text=force_name, match=match, resolved_name=name)

    if image is None:
        raise ValueError("image is required unless force_name is set")

    ocr = extract_name(image, config)
    match = match_from_config(ocr.text, config)
    resolved = match.name if match.accepted else None
    return IdentifyResult(ocr_text=ocr.text, match=match, resolved_name=resolved)
