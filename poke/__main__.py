"""CLI entrypoint for Pocket Pokedex (Mac bench / tests — primary UI is web/)."""

from __future__ import annotations

import argparse
import sys
from typing import Any

from poke.api_client import PokeApiClient, warm_offline_snapshot
from poke.capture import capture_or_fixture
from poke.config import load_config
from poke.entry import DexEntry, build_entry
from poke.identify import identify_card
from poke.match import load_species_names, match_from_config
from poke.tts import TtsError, speak


def parse_args(argv: list[str] | None = None) -> argparse.Namespace:
    p = argparse.ArgumentParser(
        description="Pocket Pokedex Mac pipeline (primary UI: web/ on iPhone A1533)"
    )
    p.add_argument("--config", default=None, help="Path to config.yaml")
    p.add_argument("--demo", action="store_true", help="Use fixture image (no camera)")
    p.add_argument(
        "--offline",
        action="store_true",
        default=None,
        help="Force offline species DB (default: config offline.enabled)",
    )
    p.add_argument(
        "--online",
        action="store_true",
        help="Allow live PokéAPI (overrides offline default)",
    )
    p.add_argument("--no-tts", action="store_true", help="Disable TTS")
    p.add_argument(
        "--headless",
        action="store_true",
        help="Run one scan to stdout (default when --ui is omitted)",
    )
    p.add_argument(
        "--ui",
        action="store_true",
        help="Optional pygame UI (Mac bench only; phone uses web/)",
    )
    p.add_argument(
        "--warm-offline",
        metavar="NAME",
        help="Fetch NAME from PokéAPI into data/offline and exit (needs network)",
    )
    p.add_argument(
        "--force-name",
        metavar="NAME",
        help="Skip OCR and look up NAME (useful for headless/tests)",
    )
    return p.parse_args(argv)


def lookup_entry(client: PokeApiClient, name: str) -> DexEntry:
    data = client.fetch_pokemon(name)
    return build_entry(data)


def run_headless(config: dict[str, Any], args: argparse.Namespace) -> int:
    client = PokeApiClient(config)
    if args.force_name:
        entry = lookup_entry(client, args.force_name)
        print(entry.title)
        print(entry.narration)
        for fact in entry.facts:
            print(f"- {fact}")
        print(entry.attribution)
        if not args.no_tts and config.get("tts", {}).get("enabled", True):
            try:
                engine = speak(entry.narration, config)
                print(f"[tts:{engine}]")
            except TtsError as exc:
                print(f"[tts skipped: {exc}]", file=sys.stderr)
        return 0

    image = capture_or_fixture(config, demo=bool(args.demo))
    result = identify_card(config, image)
    print(f"OCR: {result.ocr_text!r}")
    print(
        f"Match: {result.match.name} score={result.match.score:.1f} "
        f"accepted={result.match.accepted}"
    )
    if not result.resolved_name:
        print("LOW CONFIDENCE — would open search UI")
        for name, score in result.match.candidates:
            print(f"  candidate: {name} ({score:.1f})")
        return 2

    entry = lookup_entry(client, result.resolved_name)
    print(entry.title)
    print(entry.narration)
    for fact in entry.facts:
        print(f"- {fact}")
    print(entry.attribution)
    return 0


def run_ui(config: dict[str, Any], args: argparse.Namespace) -> int:
    from poke.ui import PokedexApp

    client = PokeApiClient(config)
    load_species_names(config)
    state: dict[str, Any] = {"entry": None, "demo": args.demo}

    def do_lookup(name: str) -> None:
        app.set_busy(f"Looking up {name}…")
        app.draw()
        try:
            entry = lookup_entry(client, name)
            state["entry"] = entry
            app.set_entry(entry)
        except Exception as exc:
            app.set_error(str(exc))

    def on_scan() -> None:
        app.set_busy("Scanning…")
        app.draw()
        try:
            image = capture_or_fixture(config, demo=state["demo"])
            if args.force_name:
                do_lookup(args.force_name)
                return
            result = identify_card(config, image)
            app.status = (
                f"OCR: {result.ocr_text or '(empty)'} → "
                f"{result.match.name} ({result.match.score:.0f})"
            )
            if result.resolved_name:
                do_lookup(result.resolved_name)
            else:
                app.set_search(
                    result.match,
                    msg=f"Low confidence ({result.match.score:.0f}). Confirm or type a name.",
                )
        except Exception as exc:
            app.set_error(str(exc))

    def on_speak() -> None:
        entry = state.get("entry")
        if not entry:
            return
        try:
            engine = speak(entry.narration, config)
            app.status = f"Spoke with {engine}."
        except TtsError as exc:
            app.status = f"TTS unavailable: {exc}"

    def on_search_submit(query: str) -> None:
        match = match_from_config(query, config)
        if match.accepted:
            do_lookup(match.name)
        else:
            app.set_search(match, msg="Confirm a candidate or refine the spelling.")

    def on_select_candidate(name: str) -> None:
        do_lookup(name)

    app = PokedexApp(
        config,
        on_scan=on_scan,
        on_speak=on_speak,
        on_search_submit=on_search_submit,
        on_select_candidate=on_select_candidate,
    )

    if args.demo:
        on_scan()

    try:
        while app.running:
            app.tick()
    finally:
        app.cleanup()
    return 0


def main(argv: list[str] | None = None) -> None:
    args = parse_args(argv)
    config = load_config(args.config)
    if args.online:
        config.setdefault("offline", {})["enabled"] = False
    elif args.offline:
        config.setdefault("offline", {})["enabled"] = True
    if args.no_tts:
        config.setdefault("tts", {})["enabled"] = False

    if args.warm_offline:
        # Warm requires network
        config.setdefault("offline", {})["enabled"] = False
        client = PokeApiClient(config)
        path = warm_offline_snapshot(client, args.warm_offline)
        print(f"Warmed offline snapshot for {args.warm_offline} → {path}")
        return

    use_ui = bool(args.ui)
    if use_ui:
        raise SystemExit(run_ui(config, args))
    # Default Mac path: headless (phone UI is web/)
    raise SystemExit(run_headless(config, args))


if __name__ == "__main__":
    main()
