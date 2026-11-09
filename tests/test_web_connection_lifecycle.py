"""Execute the browser lifecycle with fake sockets and timers."""

import subprocess
from pathlib import Path


def test_web_connection_lifecycle() -> None:
    subprocess.run(
        ["node", "tests/check_web_connection_lifecycle.cjs"],
        cwd=Path(__file__).resolve().parents[1],
        check=True,
        timeout=15,
    )
