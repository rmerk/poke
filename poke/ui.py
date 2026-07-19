"""pygame UI for idle / scanning / entry / search screens."""

from __future__ import annotations

from enum import Enum, auto
from typing import Any, Callable

import pygame

from poke.entry import DexEntry
from poke.gpio_input import GpioButtons, map_key_to_action
from poke.match import MatchResult


class Screen(Enum):
    IDLE = auto()
    BUSY = auto()
    ENTRY = auto()
    SEARCH = auto()
    ERROR = auto()


class PokedexApp:
    def __init__(
        self,
        config: dict[str, Any],
        *,
        on_scan: Callable[[], None],
        on_speak: Callable[[], None],
        on_search_submit: Callable[[str], None],
        on_select_candidate: Callable[[str], None],
    ) -> None:
        self.config = config
        display = config.get("display", {})
        self.width = int(display.get("width", 480))
        self.height = int(display.get("height", 320))
        self.fullscreen = bool(display.get("fullscreen", False))
        self.on_scan = on_scan
        self.on_speak = on_speak
        self.on_search_submit = on_search_submit
        self.on_select_candidate = on_select_candidate

        self.screen_id = Screen.IDLE
        self.status = "Ready. Press Scan (Space)."
        self.entry: DexEntry | None = None
        self.candidates: list[tuple[str, float]] = []
        self.search_text = ""
        self.error_message = ""
        self.attribution = "Data: PokéAPI — cached locally. Fan demo only."

        pygame.init()
        flags = pygame.FULLSCREEN if self.fullscreen else 0
        self.surface = pygame.display.set_mode((self.width, self.height), flags)
        pygame.display.set_caption("Pocket Pokedex")
        self.clock = pygame.time.Clock()
        self.font_lg = pygame.font.SysFont("menlo", 28, bold=True)
        self.font_md = pygame.font.SysFont("menlo", 18)
        self.font_sm = pygame.font.SysFont("menlo", 14)
        self.gpio = GpioButtons(config)
        self.running = True

        # Palette — red Pokedex shell vibe without purple AI defaults
        self.bg = (28, 32, 36)
        self.panel = (48, 18, 18)
        self.accent = (220, 48, 48)
        self.text = (245, 240, 232)
        self.muted = (180, 170, 160)

    def set_idle(self, msg: str | None = None) -> None:
        self.screen_id = Screen.IDLE
        self.status = msg or "Ready. Press Scan (Space)."
        self.entry = None

    def set_busy(self, msg: str) -> None:
        self.screen_id = Screen.BUSY
        self.status = msg

    def set_entry(self, entry: DexEntry) -> None:
        self.screen_id = Screen.ENTRY
        self.entry = entry
        self.status = "Entry loaded. Speak (P) · Rescan (Space) · Back (Esc)"

    def set_search(self, match: MatchResult | None = None, msg: str | None = None) -> None:
        self.screen_id = Screen.SEARCH
        if match:
            self.candidates = list(match.candidates)
            self.search_text = ""
            self.status = msg or f"Low confidence ({match.score:.0f}). Type a name or pick a candidate."
        else:
            self.status = msg or "Search: type a Pokémon name, Enter to look up."

    def set_error(self, message: str) -> None:
        self.screen_id = Screen.ERROR
        self.error_message = message
        self.status = "Error — Esc to go back, Space to retry scan."

    def handle_action(self, action: str) -> None:
        if action == "back":
            if self.screen_id == Screen.SEARCH and self.search_text:
                self.search_text = self.search_text[:-1]
            else:
                self.set_idle()
        elif action == "scan":
            if self.screen_id == Screen.SEARCH and self.search_text.strip():
                self.on_search_submit(self.search_text.strip())
            else:
                self.on_scan()
        elif action == "speak":
            if self.screen_id == Screen.ENTRY:
                self.on_speak()
        elif action == "next":
            if self.screen_id == Screen.SEARCH and self.candidates:
                name, _ = self.candidates[0]
                self.on_select_candidate(name)
        elif action == "search":
            self.set_search(msg="Manual search. Type a name, Enter to look up.")

    def handle_events(self) -> None:
        for event in pygame.event.get():
            if event.type == pygame.QUIT:
                self.running = False
            elif event.type == pygame.KEYDOWN:
                if event.key == pygame.K_ESCAPE:
                    self.handle_action("back")
                    continue
                action = map_key_to_action(pygame.key.name(event.key))
                if self.screen_id == Screen.SEARCH and event.unicode and event.unicode.isprintable():
                    if event.key not in (pygame.K_RETURN, pygame.K_ESCAPE, pygame.K_TAB):
                        ch = event.unicode
                        if ch.isalnum() or ch in " -'.":
                            self.search_text += ch
                            continue
                if event.key == pygame.K_BACKSPACE and self.screen_id == Screen.SEARCH:
                    self.search_text = self.search_text[:-1]
                    continue
                if action:
                    self.handle_action(action)
                # Number keys 1–5 select candidates in search
                if self.screen_id == Screen.SEARCH and pygame.K_1 <= event.key <= pygame.K_5:
                    idx = event.key - pygame.K_1
                    if idx < len(self.candidates):
                        self.on_select_candidate(self.candidates[idx][0])

        gpio_event = self.gpio.poll()
        if gpio_event:
            self.handle_action(gpio_event.name)

    def _blit_wrapped(self, text: str, font: pygame.font.Font, color: tuple[int, int, int], rect: pygame.Rect) -> None:
        words = text.split()
        lines: list[str] = []
        current = ""
        for word in words:
            trial = f"{current} {word}".strip()
            if font.size(trial)[0] <= rect.width:
                current = trial
            else:
                if current:
                    lines.append(current)
                current = word
        if current:
            lines.append(current)
        y = rect.top
        for line in lines:
            if y + font.get_height() > rect.bottom:
                break
            surf = font.render(line, True, color)
            self.surface.blit(surf, (rect.left, y))
            y += font.get_height() + 2

    def draw(self) -> None:
        self.surface.fill(self.bg)
        header = pygame.Rect(0, 0, self.width, 40)
        pygame.draw.rect(self.surface, self.panel, header)
        pygame.draw.rect(self.surface, self.accent, pygame.Rect(0, 40, self.width, 3))
        brand = self.font_lg.render("POKÉDEX", True, self.accent)
        self.surface.blit(brand, (12, 6))

        content = pygame.Rect(16, 56, self.width - 32, self.height - 100)

        if self.screen_id == Screen.IDLE:
            title = self.font_md.render("Scan card.", True, self.text)
            self.surface.blit(title, (content.left, content.top))
            help_lines = [
                "Space / S — Scan",
                "P — Speak (after entry)",
                "/ — Manual search",
                "Esc — Back",
            ]
            y = content.top + 40
            for line in help_lines:
                self.surface.blit(self.font_sm.render(line, True, self.muted), (content.left, y))
                y += 22

        elif self.screen_id == Screen.BUSY:
            self.surface.blit(self.font_md.render(self.status, True, self.text), (content.left, content.top))

        elif self.screen_id == Screen.ERROR:
            self._blit_wrapped(self.error_message, self.font_sm, self.accent, content)

        elif self.screen_id == Screen.SEARCH:
            prompt = self.font_md.render(f"> {self.search_text}_", True, self.text)
            self.surface.blit(prompt, (content.left, content.top))
            y = content.top + 36
            for i, (name, score) in enumerate(self.candidates[:5]):
                line = f"{i + 1}. {name}  ({score:.0f})"
                self.surface.blit(self.font_sm.render(line, True, self.muted), (content.left, y))
                y += 22
            tip = self.font_sm.render("Enter look up · 1-5 pick · Tab = top candidate", True, self.muted)
            self.surface.blit(tip, (content.left, self.height - 70))

        elif self.screen_id == Screen.ENTRY and self.entry:
            e = self.entry
            self.surface.blit(self.font_lg.render(e.title, True, self.text), (content.left, content.top))
            meta = f"{e.types_line}  ·  {e.category}  ·  {e.height_weight}"
            self.surface.blit(self.font_sm.render(meta, True, self.accent), (content.left, content.top + 34))
            narr_rect = pygame.Rect(content.left, content.top + 60, content.width, 110)
            self._blit_wrapped(e.narration, self.font_sm, self.text, narr_rect)
            y = content.top + 180
            for fact in e.facts[:4]:
                self.surface.blit(self.font_sm.render(f"• {fact}", True, self.muted), (content.left, y))
                y += 18

        # Footer
        footer = pygame.Rect(0, self.height - 36, self.width, 36)
        pygame.draw.rect(self.surface, self.panel, footer)
        status_surf = self.font_sm.render(self.status[:70], True, self.muted)
        self.surface.blit(status_surf, (10, self.height - 28))
        attr = self.font_sm.render(self.attribution[:40], True, (120, 110, 100))
        self.surface.blit(attr, (self.width - attr.get_width() - 8, self.height - 28))

        pygame.display.flip()

    def tick(self) -> None:
        self.handle_events()
        self.draw()
        self.clock.tick(30)

    def cleanup(self) -> None:
        self.gpio.cleanup()
        pygame.quit()
