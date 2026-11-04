import subprocess
from pathlib import Path


def test_web_mic_lifecycle():
    subprocess.run(
        ["node", "tests/check_web_mic.cjs"],
        cwd=Path(__file__).resolve().parents[1],
        check=True,
        timeout=15,
    )
