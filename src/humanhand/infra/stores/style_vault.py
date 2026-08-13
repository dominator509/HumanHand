"""File-backed Style Fidelity Vault.

Layout under the vault directory:

- ``originals/<artifact_id>.bin`` — original bytes, written exactly once,
  filename is the artifact id (a sha256 digest); never modified.
- ``packages/<package_id>.json`` — serialized StyleEvidencePackage,
  written exactly once.
- ``decisions.jsonl`` — append-only review decisions (one JSON object per
  line, newest last).

Writes are atomic (temp file + ``os.replace``). Reads verify the sha256 of
every original before returning it. No scrubber or normalizer ever touches
vault contents (ADR-003).

Application-layer encryption (ADR-005, Windows DPAPI) is intentionally NOT
implemented here: that boundary arrives with the key-provider plan. The
Decision Log records this deferral.
"""

from __future__ import annotations

import hashlib
import json
import os
import re
import tempfile
from pathlib import Path


class StyleVaultError(Exception):
    """Raised when vault invariants are violated (write-once, integrity)."""


# Vault ids: sty-<24 hex> optionally followed by @<profile label>.
_PACKAGE_ID_RE = re.compile(r"^sty-[0-9a-f]{24}(?:@[A-Za-z0-9._-]{1,64})?$")
_ARTIFACT_ID_RE = re.compile(r"^[0-9a-f]{64}$")


def _sha256(data: bytes) -> str:
    return hashlib.sha256(data).hexdigest()


def _validated_package_id(package_id: str) -> None:
    """Reject path-traversal and malformed package ids (fail closed)."""
    if _PACKAGE_ID_RE.match(package_id) is None:
        raise StyleVaultError(f"Invalid package id: {package_id!r}")


def _validated_artifact_id(artifact_id: str) -> None:
    if _ARTIFACT_ID_RE.match(artifact_id) is None:
        raise StyleVaultError(f"Invalid artifact id: {artifact_id!r}")


def _write_once(path: Path, data: bytes, *, collision: str) -> None:
    """Atomically create ``path`` without ever replacing an existing file."""
    descriptor, temporary_name = tempfile.mkstemp(
        dir=path.parent,
        prefix=f".{path.name}.",
        suffix=".tmp",
    )
    temporary = Path(temporary_name)
    try:
        with os.fdopen(descriptor, "wb") as handle:
            handle.write(data)
            handle.flush()
            os.fsync(handle.fileno())
        try:
            os.link(temporary, path)
        except FileExistsError:
            if path.read_bytes() != data:
                raise StyleVaultError(collision) from None
    finally:
        temporary.unlink(missing_ok=True)


class StyleVault:
    """Local, write-once, integrity-verified style evidence vault."""

    def __init__(self, vault_dir: str | Path) -> None:
        self._root = Path(vault_dir)
        self._originals = self._root / "originals"
        self._packages = self._root / "packages"
        self._decisions = self._root / "decisions.jsonl"
        self._ensure_layout()

    def _ensure_layout(self) -> None:
        self._originals.mkdir(parents=True, exist_ok=True)
        self._packages.mkdir(parents=True, exist_ok=True)

    @property
    def root(self) -> Path:
        return self._root

    # ── Originals ─────────────────────────────────────────────────

    def store_original(self, raw: bytes) -> str:
        """Store original bytes once and return the artifact id."""
        artifact_id = _sha256(raw)
        path = self._originals / f"{artifact_id}.bin"
        if path.exists():
            existing = path.read_bytes()
            if existing != raw:
                raise StyleVaultError(f"Artifact id collision with different bytes: {artifact_id}")
            return artifact_id
        _write_once(
            path,
            raw,
            collision=f"Artifact id collision with different bytes: {artifact_id}",
        )
        return artifact_id

    def load_original(self, artifact_id: str) -> bytes:
        """Read an original back, verifying its sha256 matches the id."""
        _validated_artifact_id(artifact_id)
        path = self._originals / f"{artifact_id}.bin"
        if not path.exists():
            raise StyleVaultError(f"Original not stored: {artifact_id}")
        raw = path.read_bytes()
        if _sha256(raw) != artifact_id:
            raise StyleVaultError(f"Original integrity check failed: {artifact_id}")
        return raw

    def original_exists(self, artifact_id: str) -> bool:
        _validated_artifact_id(artifact_id)
        return (self._originals / f"{artifact_id}.bin").exists()

    # ── Packages ──────────────────────────────────────────────────

    def store_package(self, package_id: str, package_json: bytes) -> None:
        """Store a serialized package exactly once under its package id."""
        _validated_package_id(package_id)
        path = self._packages / f"{package_id}.json"
        if path.exists():
            existing = path.read_bytes()
            if existing != package_json:
                raise StyleVaultError(f"Package id collision with different content: {package_id}")
            return
        _write_once(
            path,
            package_json,
            collision=f"Package id collision with different content: {package_id}",
        )

    def load_package(self, package_id: str) -> bytes:
        _validated_package_id(package_id)
        path = self._packages / f"{package_id}.json"
        if not path.exists():
            raise StyleVaultError(f"Package not stored: {package_id}")
        return path.read_bytes()

    def list_packages(self) -> tuple[str, ...]:
        return tuple(
            sorted(path.name.removesuffix(".json") for path in self._packages.glob("*.json"))
        )

    # ── Review decisions ──────────────────────────────────────────

    def append_decision(self, decision: dict[str, object]) -> None:
        """Append one review decision; the log is append-only."""
        line = json.dumps(decision, sort_keys=True, separators=(",", ":")) + "\n"
        with self._decisions.open("a", encoding="utf-8", newline="\n") as handle:
            handle.write(line)

    def read_decisions(self) -> tuple[dict[str, object], ...]:
        """Return decisions in log order (oldest first)."""
        if not self._decisions.exists():
            return ()
        decisions: list[dict[str, object]] = []
        for line in self._decisions.read_text(encoding="utf-8").splitlines():
            if not line.strip():
                continue
            try:
                record = json.loads(line)
            except json.JSONDecodeError:
                raise StyleVaultError("Corrupt decision log line") from None
            if not isinstance(record, dict):
                raise StyleVaultError("Corrupt decision log record")
            decisions.append(record)
        return tuple(decisions)
