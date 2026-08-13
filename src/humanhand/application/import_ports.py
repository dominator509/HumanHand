"""Application ports for the clean-room import workflow."""

from __future__ import annotations

from pathlib import Path
from typing import Protocol

from humanhand.domain.canonical_document import ImportInspection
from humanhand.domain.import_policy import ImportPolicy


class ImportFileReader(Protocol):
    """Protocol for raw import file access (implemented by infra/CLI wiring)."""

    def size_bytes(self, path: str | Path) -> int:
        """Return the file size without reading the file. Raises FileIOError."""
        ...

    def read_head(self, path: str | Path, max_bytes: int) -> bytes:
        """Read at most ``max_bytes`` leading bytes. Raises FileIOError."""
        ...

    def read_bytes(self, path: str | Path) -> bytes:
        """Read the full raw file bytes. Raises FileIOError."""
        ...


class ImportInspector(Protocol):
    """Protocol for the identity-to-worker inspection pipeline."""

    def inspect(
        self,
        *,
        path: str,
        raw: bytes,
        head: bytes,
        size_bytes: int,
        policy: ImportPolicy,
    ) -> ImportInspection:
        """Inspect already-read bytes and return an ImportInspection."""
        ...
