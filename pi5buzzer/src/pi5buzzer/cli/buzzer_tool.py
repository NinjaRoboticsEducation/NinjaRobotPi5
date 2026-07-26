"""Interactive TUI for exercising pi5buzzer on Raspberry Pi 5."""

from __future__ import annotations

import json
import time
from typing import Optional

import click

from pi5buzzer.config.config_manager import BuzzerConfigManager
from pi5buzzer.core.driver import create_default_backend
from pi5buzzer.notes import DEMO_SONG, EMOTION_SOUNDS, get_emotion_names


def buzzer_tool(config_path: Optional[str] = None) -> None:
    """Launch the interactive buzzer tool."""
    cm = BuzzerConfigManager(config_path)
    cm.load()

    try:
        pi = create_default_backend()
    except RuntimeError as exc:
        click.echo(f"ERROR: {exc}")
        return

    try:
        from pi5buzzer.core.music import MusicBuzzer

        pin = cm.get_pin()
        volume = cm.get_volume()
        buzzer = MusicBuzzer(pin=pin, pi=pi, volume=volume)
        buzzer.initialize()
    except Exception as exc:
        click.echo(f"ERROR: Buzzer init failed: {exc}")
        pi.stop()
        return

    def show_menu() -> None:
        click.echo()
        click.echo("+------------------------------------------------------------+")
        click.echo("|                 pi5buzzer Interactive Tool                 |")
        click.echo("+------------------------------------------------------------+")
        click.echo("| 1. Init         - Set up buzzer pin and save config        |")
        click.echo("| 2. Beep         - Play a single tone                       |")
        click.echo("| 3. Play Emotion - Play an emotion sound by name            |")
        click.echo("| 4. Play Music   - Interactive keyboard piano               |")
        click.echo("| 5. Play Song    - Play the demo melody                     |")
        click.echo("| 6. Volume       - Adjust buzzer volume                     |")
        click.echo("| 7. Info         - Show config and health check             |")
        click.echo("| 8. Config       - Show/export/import settings              |")
        click.echo("| 9. Exit                                               |")
        click.echo("+------------------------------------------------------------+")

    def do_init() -> None:
        nonlocal buzzer, pin
        new_pin = click.prompt("\nGPIO pin for buzzer", type=int, default=pin)
        try:
            cm.set_pin(new_pin)
            cm.save()
            click.echo(f"  OK: Config saved (pin={new_pin})")

            buzzer.off()
            buzzer = MusicBuzzer(pin=new_pin, pi=pi, volume=cm.get_volume())
            buzzer.initialize()
            pin = new_pin

            click.echo("  Playing test beep...")
            buzzer.play_sound(440, 0.3)
            time.sleep(0.5)
            click.echo("  OK: Test beep successful")
        except ValueError as exc:
            click.echo(f"  ERROR: Invalid pin: {exc}")
        except Exception as exc:
            click.echo(f"  ERROR: {exc}")

    def do_beep() -> None:
        frequency = click.prompt("\nFrequency (Hz)", type=int, default=440)
        duration = click.prompt("Duration (seconds)", type=float, default=0.5)
        click.echo(f"  Playing {frequency} Hz for {duration}s...")
        buzzer.play_sound(frequency, duration)
        time.sleep(duration + 0.1)
        click.echo("  OK: Done")

    def do_play_emotion() -> None:
        emotions = get_emotion_names()
        click.echo("\nAvailable emotions:")
        for index, name in enumerate(emotions, start=1):
            click.echo(f"  {index:2d}. {name:<15s} ({len(EMOTION_SOUNDS[name])} notes)")

        try:
            choice = click.prompt("\nSelect emotion (number or name)", type=str)
        except (EOFError, KeyboardInterrupt):
            return

        if choice.isdigit():
            emotion_index = int(choice) - 1
            if not 0 <= emotion_index < len(emotions):
                click.echo("  ERROR: Invalid number")
                return
            emotion = emotions[emotion_index]
        elif choice in emotions:
            emotion = choice
        else:
            click.echo(f"  ERROR: Unknown emotion: {choice}")
            return

        click.echo(f"  Playing: {emotion}")
        buzzer.play_emotion(emotion)
        time.sleep(2.0)
        click.echo("  OK: Done")

    def do_play_music() -> None:
        click.echo("\nLaunching keyboard piano. Type 'quit' to return.\n")
        buzzer.play_music()

    def do_play_song() -> None:
        click.echo("\nPlaying demo: Twinkle Twinkle Little Star")
        buzzer.play_demo()
        time.sleep(sum(duration for _, duration in DEMO_SONG) + 0.5)
        click.echo("  OK: Song complete")

    def do_volume() -> None:
        current = buzzer.volume
        percent = current * 100 // 255
        click.echo(f"\nCurrent volume: {current}/255 ({percent}%)")
        new_percent = click.prompt("New volume (0-100%)", type=int, default=percent)
        new_volume = max(0, min(255, new_percent * 255 // 100))

        buzzer.volume = new_volume
        cm.set_volume(new_volume)
        cm.save()

        click.echo(f"  OK: Volume set to {new_volume}/255 ({new_percent}%)")
        buzzer.play_sound(440, 0.2)
        time.sleep(0.3)

    def do_info() -> None:
        cfg = cm.config
        click.echo("\nBuzzer Info:")
        click.echo(f"  Config file: {cm.path}")
        click.echo(f"  Pin:         GPIO {cfg.get('pin', 'N/A')}")
        click.echo(f"  Volume:      {cfg.get('volume', 'N/A')}/255")
        click.echo(f"  Initialized: {buzzer.is_initialized}")
        click.echo(
            f"  GPIO backend:{' Connected' if getattr(pi, 'connected', False) else ' Disconnected'}"
        )

        if click.confirm("\nRun health check?", default=True):
            click.echo("  Testing beep...")
            buzzer.play_sound(440, 0.2)
            time.sleep(0.4)
            click.echo("  OK: Health check passed")

    def do_config() -> None:
        click.echo("\n  1. Show config")
        click.echo("  2. Export config")
        click.echo("  3. Import config")

        try:
            choice = click.prompt("  Choice", type=int, default=1)
        except (EOFError, KeyboardInterrupt):
            return

        if choice == 1:
            click.echo("\n" + json.dumps(cm.config, indent=2))
            return

        if choice == 2:
            path = click.prompt("Export path", type=str)
            try:
                cm.export_config(path)
                click.echo(f"  OK: Exported to {path}")
            except Exception as exc:
                click.echo(f"  ERROR: Export failed: {exc}")
            return

        if choice == 3:
            path = click.prompt("Import path", type=str)
            try:
                cm.import_config(path)
                cm.save()
                buzzer.volume = cm.get_volume()
                click.echo(f"  OK: Imported from {path}")
            except FileNotFoundError:
                click.echo(f"  ERROR: File not found: {path}")
            except Exception as exc:
                click.echo(f"  ERROR: Import failed: {exc}")

    show_menu()

    while True:
        try:
            choice = click.prompt("\nSelect an option", type=int, default=9)
        except (EOFError, KeyboardInterrupt):
            click.echo("\nExiting.")
            break

        if choice == 1:
            do_init()
        elif choice == 2:
            do_beep()
        elif choice == 3:
            do_play_emotion()
        elif choice == 4:
            do_play_music()
        elif choice == 5:
            do_play_song()
        elif choice == 6:
            do_volume()
        elif choice == 7:
            do_info()
        elif choice == 8:
            do_config()
        elif choice == 9:
            click.echo("Goodbye!")
            break
        else:
            click.echo("Invalid choice. Please enter 1-9.")

    buzzer.off()
    pi.stop()
