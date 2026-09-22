"""Isolated read-only asset check; never imported into the IDE device runtime."""

from __future__ import annotations

import json
import sys


def main() -> int:
    """Reuse standalone mic resolvers without recording or running model inference."""
    try:
        from pi5mic.install.openwakeword import (  # type: ignore[import-untyped]
            resolve_openwakeword_model_path,
        )
        from pi5mic.install.whisper_cpp import (  # type: ignore[import-untyped]
            resolve_model_path,
            resolve_whisper_cpp_command,
        )

        raw = sys.stdin.read(65_537)
        if len(raw) > 65_536:
            return 1
        payload = json.loads(raw)
        resolve_whisper_cpp_command(payload["command"])
        resolve_model_path(payload["model"])
        model = resolve_openwakeword_model_path(payload["wake_model"])
        return 0 if model.name == "hey_Ninja.onnx" else 1
    except Exception:
        # Paths, credentials, and driver exception text must not escape this probe.
        return 1


if __name__ == "__main__":
    raise SystemExit(main())
