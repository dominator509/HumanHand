"""Project directory layout for local HumanHand state (EP-015, ADR-001).

ADR-001 permits persisting project state only inside a user-selected project
directory under ``.humanhand/``. This module defines that layout and the
``project.toml`` metadata file. Nothing here ever deletes data; ``init_layout``
is idempotent and never overwrites an existing ``project.toml``.
"""

from __future__ import annotations

import tomllib
from dataclasses import dataclass
from pathlib import Path


@dataclass(frozen=True)
class ProjectLayout:
    """Immutable description of one project directory layout."""

    root: Path
    humanhand_dir: Path  # <root>/.humanhand
    project_toml: Path  # <root>/.humanhand/project.toml
    database: Path  # <root>/.humanhand/project.db
    blobs_dir: Path  # <root>/.humanhand/blobs
    reports_dir: Path  # <root>/.humanhand/reports
    exports_dir: Path  # <root>/.humanhand/exports
    source_dir: Path  # <root>/source
    style_dir: Path  # <root>/style
    working_dir: Path  # <root>/working


def layout_for(root: str | Path) -> ProjectLayout:
    """Compute the layout paths for ``root`` without touching the filesystem."""
    root_path = Path(root).resolve()
    humanhand_dir = root_path / ".humanhand"
    return ProjectLayout(
        root=root_path,
        humanhand_dir=humanhand_dir,
        project_toml=humanhand_dir / "project.toml",
        database=humanhand_dir / "project.db",
        blobs_dir=humanhand_dir / "blobs",
        reports_dir=humanhand_dir / "reports",
        exports_dir=humanhand_dir / "exports",
        source_dir=root_path / "source",
        style_dir=root_path / "style",
        working_dir=root_path / "working",
    )


def _toml_basic_string(value: str) -> str:
    """Escape ``value`` for a TOML basic string literal."""
    escaped = (
        value.replace("\\", "\\\\")
        .replace('"', '\\"')
        .replace("\b", "\\b")
        .replace("\t", "\\t")
        .replace("\n", "\\n")
        .replace("\f", "\\f")
        .replace("\r", "\\r")
    )
    return f'"{escaped}"'


def _write_project_toml(path: Path, name: str) -> None:
    """Write the project.toml metadata file (UTF-8, LF, no BOM)."""
    content = f"[humanhand]\nname = {_toml_basic_string(name)}\nschema_version = 1\n"
    path.write_text(content, encoding="utf-8", newline="\n")


def init_layout(root: str | Path, *, name: str) -> ProjectLayout:
    """Create the full layout (idempotent) and write ``project.toml``.

    Existing directories are reused and nothing is ever deleted. An existing
    ``project.toml`` is never overwritten. Raises :class:`FileExistsError`
    when ``root`` exists and is not a directory.
    """
    layout = layout_for(root)
    if layout.root.exists() and not layout.root.is_dir():
        raise FileExistsError(f"Project root exists and is not a directory: {layout.root}")
    for directory in (
        layout.humanhand_dir,
        layout.blobs_dir,
        layout.reports_dir,
        layout.exports_dir,
        layout.source_dir,
        layout.style_dir,
        layout.working_dir,
    ):
        directory.mkdir(parents=True, exist_ok=True)
    if not layout.project_toml.exists():
        _write_project_toml(layout.project_toml, name)
    return layout


def read_project_toml(root: str | Path) -> dict[str, str]:
    """Read ``name`` and ``schema_version`` from ``project.toml``.

    Returns ``{}`` when the file is missing. A corrupt TOML file raises
    :class:`tomllib.TOMLDecodeError` (fail closed rather than silently losing
    the project identity).
    """
    project_toml = layout_for(root).project_toml
    if not project_toml.exists():
        return {}
    with project_toml.open("rb") as handle:
        data = tomllib.load(handle)
    section = data.get("humanhand")
    if not isinstance(section, dict):
        return {}
    result: dict[str, str] = {}
    for key in ("name", "schema_version"):
        value = section.get(key)
        if value is not None:
            result[key] = str(value)
    return result
