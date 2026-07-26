from __future__ import annotations

import ast
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
AGENT_SOURCE = ROOT / "ninjarobot_pi5_agent" / "src" / "ninjarobot_pi5_agent"


def imported_modules(path: Path) -> set[str]:
    tree = ast.parse(path.read_text(encoding="utf-8"), filename=str(path))
    imports: set[str] = set()
    for node in ast.walk(tree):
        if isinstance(node, ast.Import):
            imports.update(alias.name for alias in node.names)
        elif isinstance(node, ast.ImportFrom) and node.module is not None:
            imports.add(node.module)
    return imports


def test_agent_never_imports_managed_hardware_libraries() -> None:
    violations: list[str] = []
    for path in sorted(AGENT_SOURCE.rglob("*.py")):
        for module in imported_modules(path):
            if module.startswith("pi5"):
                violations.append(f"{path.relative_to(ROOT)} imports {module}")

    assert violations == []


def test_phase_1_packages_do_not_import_historical_runtime() -> None:
    forbidden = ("ninjaclawbot", "openclaw")
    violations: list[str] = []
    for package in ("ninjarobot_pi5_agent", "ninjarobot_pi5_ide"):
        source = ROOT / package / "src"
        for path in sorted(source.rglob("*.py")):
            for module in imported_modules(path):
                if module.startswith(forbidden):
                    violations.append(f"{path.relative_to(ROOT)} imports {module}")

    assert violations == []
