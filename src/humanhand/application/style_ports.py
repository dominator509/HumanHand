"""Application ports for the Style Fidelity Vault workflow."""

from __future__ import annotations

from typing import Protocol


class StyleVaultPort(Protocol):
    """Protocol for the write-once style evidence vault."""

    def store_original(self, raw: bytes) -> str:
        """Store original bytes once; return the artifact id."""
        ...

    def load_original(self, artifact_id: str) -> bytes:
        """Read an original, verifying its sha256 against the id."""
        ...

    def store_package(self, package_id: str, package_json: bytes) -> None:
        """Store a serialized package exactly once."""
        ...

    def load_package(self, package_id: str) -> bytes:
        """Load a serialized package."""
        ...

    def list_packages(self) -> tuple[str, ...]:
        """List stored package ids, sorted."""
        ...

    def append_decision(self, decision: dict[str, object]) -> None:
        """Append one review decision to the append-only log."""
        ...

    def read_decisions(self) -> tuple[dict[str, object], ...]:
        """Read the decision log, oldest first."""
        ...
