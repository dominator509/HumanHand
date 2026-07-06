"""Application ports — Protocols for infra implementations."""

from __future__ import annotations

from pathlib import Path
from typing import Any, Protocol


class FileReader(Protocol):
    """Protocol for reading text files with strict validation."""

    def read(self, path: str | Path) -> str:
        """Read and return text from path, raising on BOM/encoding/empty errors."""
        ...


class FileWriter(Protocol):
    """Protocol for writing clean output text."""

    def write(
        self,
        output_path: str | Path,
        text: str,
        input_paths: list[str | Path] | None = None,
    ) -> Path:
        """Scrub, normalize, and write text. Returns the output path."""
        ...


class DetectorCache(Protocol):
    """Protocol for detector score cache with no user text storage."""

    def get(
        self, text_hash: str, provider: str, model: str, schema_version: int
    ) -> dict[str, Any] | None:
        """Retrieve a cached detector score record, or None on miss."""
        ...

    def put(self, record: dict[str, Any]) -> None:
        """Store a detector score record. Must not contain user text."""
        ...

    def close(self) -> None:
        """Close the cache connection."""
        ...
