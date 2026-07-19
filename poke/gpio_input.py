"""Optional GPIO button polling for Raspberry Pi."""

from __future__ import annotations

import time
from dataclasses import dataclass
from typing import Any


@dataclass(frozen=True)
class ButtonEvent:
    name: str  # back | scan | speak | next


class GpioButtons:
    """Poll BCM pins. No-op / unavailable off-Pi."""

    def __init__(self, config: dict[str, Any]) -> None:
        gpio = config.get("gpio", {})
        self.enabled = bool(gpio.get("enabled", False))
        self._gpio = None
        self._pins: dict[str, int] = {}
        self._last_fire: dict[str, float] = {}
        self._debounce_s = 0.35

        if not self.enabled:
            return

        try:
            import RPi.GPIO as GPIO  # type: ignore
        except ImportError:
            self.enabled = False
            return

        self._gpio = GPIO
        GPIO.setmode(GPIO.BCM)
        GPIO.setwarnings(False)
        mapping = {
            "back": int(gpio.get("pin_back", 17)),
            "scan": int(gpio.get("pin_scan", 27)),
            "speak": int(gpio.get("pin_speak", 22)),
            "next": int(gpio.get("pin_next", 23)),
        }
        self._pins = mapping
        for pin in mapping.values():
            GPIO.setup(pin, GPIO.IN, pull_up_down=GPIO.PUD_UP)

    def poll(self) -> ButtonEvent | None:
        if not self.enabled or self._gpio is None:
            return None
        GPIO = self._gpio
        now = time.monotonic()
        for name, pin in self._pins.items():
            # Active low with pull-up
            if GPIO.input(pin) == GPIO.LOW:
                last = self._last_fire.get(name, 0.0)
                if now - last >= self._debounce_s:
                    self._last_fire[name] = now
                    return ButtonEvent(name=name)
        return None

    def cleanup(self) -> None:
        if self._gpio is not None:
            try:
                self._gpio.cleanup()
            except Exception:
                pass


def map_key_to_action(key_name: str) -> str | None:
    """Map pygame key names to actions."""
    table = {
        "escape": "back",
        "b": "back",
        "space": "scan",
        "s": "scan",
        "return": "scan",
        "p": "speak",
        "v": "speak",
        "n": "next",
        "tab": "next",
        "slash": "search",
        "f": "search",
    }
    return table.get(key_name.lower())
