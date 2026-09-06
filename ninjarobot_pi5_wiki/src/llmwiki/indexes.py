from __future__ import annotations

from pathlib import Path

from .frontmatter import FrontmatterError, parse_file


def _description(path: Path) -> tuple[str, str]:
    try:
        document = parse_file(path)
    except FrontmatterError:
        return path.stem.replace("-", " ").title(), "Invalid or incomplete concept page."
    title = str(document.metadata.get("title") or path.stem.replace("-", " ").title())
    description = str(document.metadata.get("description") or "No description provided.")
    return title, description


def render_index(directory: Path, bundle_root: Path) -> str:
    is_root = directory.resolve() == bundle_root.resolve()
    title = "Local LLM Wiki" if is_root else directory.name.replace("-", " ").title()
    prefix = '---\nokf_version: "0.2"\n---\n\n' if is_root else ""
    lines = [f"# {title}", ""]

    files = [
        path
        for path in directory.glob("*.md")
        if path.name not in {"index.md", "log.md"}
    ]
    for path in sorted(files, key=lambda item: item.name):
        page_title, description = _description(path)
        lines.append(f"* [{page_title}]({path.name}) - {description}")

    subdirectories = [
        path
        for path in directory.iterdir()
        if path.is_dir() and not path.name.startswith(".") and path.name != "assets"
    ] if directory.exists() else []
    for path in sorted(subdirectories, key=lambda item: item.name):
        label = path.name.replace("-", " ").title()
        lines.append(f"* [{label}]({path.name}/) - Browse {label.lower()} in this bundle.")
    if len(lines) == 2:
        lines.append("No concept pages yet.")
    return prefix + "\n".join(lines).rstrip() + "\n"


def build_indexes(bundle_root: Path, *, check: bool = False) -> list[Path]:
    directories = [bundle_root]
    directories.extend(
        path for path in bundle_root.rglob("*")
        if path.is_dir() and not path.name.startswith(".") and "assets" not in path.relative_to(bundle_root).parts
    )
    changed: list[Path] = []
    for directory in sorted(directories, key=lambda item: item.relative_to(bundle_root).as_posix()):
        expected = render_index(directory, bundle_root)
        index = directory / "index.md"
        current = index.read_text(encoding="utf-8") if index.exists() else ""
        if current != expected:
            changed.append(index)
            if not check:
                index.write_text(expected, encoding="utf-8")
    return changed
