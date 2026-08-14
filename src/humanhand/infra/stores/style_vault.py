"""File-backed Style Fidelity Vault with optional application encryption.

Layout under the vault directory:

- ``originals/<artifact_id>.bin`` — original bytes, written exactly once;
- ``packages/<package_id>.json`` — serialized StyleEvidencePackage;
- ``decisions.jsonl`` — append-only review decisions.

When a ``KeyProvider`` is supplied, every file body is provider-encrypted and
wrapped with a versioned envelope. Filenames remain deterministic identifiers
needed by the vault contract, while user text and original document bytes are
not retained in plaintext. Encrypted mode refuses legacy plaintext records
instead of silently weakening the active privacy policy.
"""

from __future__ import annotations

import base64
import binascii
import hashlib
import json
import os
import re
import tempfile
from pathlib import Path

from humanhand.infra.stores.key_provider import (
    EncryptionUnavailableError,
    KeyProvider,
)


class StyleVaultError(Exception):
    """Raised when vault invariants are violated."""


_PACKAGE_ID_RE = re.compile(r"^sty-[0-9a-f]{24}(?:@[A-Za-z0-9._-]{1,64})?$")
_ARTIFACT_ID_RE = re.compile(r"^[0-9a-f]{64}$")
_ENVELOPE_PREFIX = b"HHENC1:"
_DECISION_PREFIX = "enc:"


def _sha256(data: bytes) -> str:
    return hashlib.sha256(data).hexdigest()


def _validated_package_id(package_id: str) -> None:
    if _PACKAGE_ID_RE.match(package_id) is None:
        raise StyleVaultError(f"Invalid package id: {package_id!r}")


def _validated_artifact_id(artifact_id: str) -> None:
    if _ARTIFACT_ID_RE.match(artifact_id) is None:
        raise StyleVaultError(f"Invalid artifact id: {artifact_id!r}")


def _create_once(path: Path, data: bytes) -> bool:
    """Atomically create ``path`` and return False when it already exists."""
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
            return False
        return True
    finally:
        temporary.unlink(missing_ok=True)


class StyleVault:
    """Local, write-once, integrity-verified style evidence vault."""

    def __init__(self, vault_dir: str | Path, key_provider: KeyProvider | None = None) -> None:
        self._root = Path(vault_dir)
        self._originals = self._root / "originals"
        self._packages = self._root / "packages"
        self._decisions = self._root / "decisions.jsonl"
        self._provider = key_provider
        self._ensure_layout()

    def _ensure_layout(self) -> None:
        self._originals.mkdir(parents=True, exist_ok=True)
        self._packages.mkdir(parents=True, exist_ok=True)
        with __import__("contextlib").suppress(OSError):
            os.chmod(self._root, 0o700)
            os.chmod(self._originals, 0o700)
            os.chmod(self._packages, 0o700)

    @property
    def root(self) -> Path:
        return self._root

    @property
    def encrypted(self) -> bool:
        return self._provider is not None

    def _encode(self, plaintext: bytes) -> bytes:
        provider = self._provider
        if provider is None:
            return plaintext
        try:
            encrypted = provider.encrypt(plaintext)
        except EncryptionUnavailableError as exc:
            raise StyleVaultError("Style vault encryption failed") from exc
        return _ENVELOPE_PREFIX + base64.b64encode(encrypted)

    def _decode(self, stored: bytes) -> bytes:
        encrypted = stored.startswith(_ENVELOPE_PREFIX)
        provider = self._provider
        if not encrypted:
            if provider is not None:
                raise StyleVaultError(
                    "Encrypted style vault refuses a legacy plaintext record"
                )
            return stored
        if provider is None:
            raise StyleVaultError("Encrypted style record requires its key provider")
        try:
            payload = base64.b64decode(
                stored[len(_ENVELOPE_PREFIX) :], validate=True
            )
            return provider.decrypt(payload)
        except (binascii.Error, EncryptionUnavailableError) as exc:
            raise StyleVaultError("Encrypted style record could not be decrypted") from exc

    def _store_content_once(self, path: Path, plaintext: bytes, *, collision: str) -> None:
        if path.exists():
            if self._decode(path.read_bytes()) != plaintext:
                raise StyleVaultError(collision)
            return
        encoded = self._encode(plaintext)
        if not _create_once(path, encoded):
            if self._decode(path.read_bytes()) != plaintext:
                raise StyleVaultError(collision)
        with __import__("contextlib").suppress(OSError):
            os.chmod(path, 0o600)

    # ── Originals ─────────────────────────────────────────────────

    def store_original(self, raw: bytes) -> str:
        """Store exact original bytes once and return their integrity id."""
        artifact_id = _sha256(raw)
        path = self._originals / f"{artifact_id}.bin"
        self._store_content_once(
            path,
            raw,
            collision=f"Artifact id collision with different bytes: {artifact_id}",
        )
        return artifact_id

    def load_original(self, artifact_id: str) -> bytes:
        """Read an original back, decrypting and verifying its sha256."""
        _validated_artifact_id(artifact_id)
        path = self._originals / f"{artifact_id}.bin"
        if not path.exists():
            raise StyleVaultError(f"Original not stored: {artifact_id}")
        raw = self._decode(path.read_bytes())
        if _sha256(raw) != artifact_id:
            raise StyleVaultError(f"Original integrity check failed: {artifact_id}")
        return raw

    def original_exists(self, artifact_id: str) -> bool:
        _validated_artifact_id(artifact_id)
        return (self._originals / f"{artifact_id}.bin").exists()

    # ── Packages ──────────────────────────────────────────────────

    def store_package(self, package_id: str, package_json: bytes) -> None:
        """Store a serialized evidence package exactly once."""
        _validated_package_id(package_id)
        path = self._packages / f"{package_id}.json"
        self._store_content_once(
            path,
            package_json,
            collision=f"Package id collision with different content: {package_id}",
        )

    def load_package(self, package_id: str) -> bytes:
        _validated_package_id(package_id)
        path = self._packages / f"{package_id}.json"
        if not path.exists():
            raise StyleVaultError(f"Package not stored: {package_id}")
        return self._decode(path.read_bytes())

    def list_packages(self) -> tuple[str, ...]:
        return tuple(
            sorted(path.name.removesuffix(".json") for path in self._packages.glob("*.json"))
        )

    # ── Review decisions ──────────────────────────────────────────

    def append_decision(self, decision: dict[str, object]) -> None:
        """Append one review decision using the vault's encryption mode."""
        plaintext = json.dumps(decision, sort_keys=True, separators=(",", ":")).encode("utf-8")
        if self._provider is None:
            line = plaintext.decode("utf-8")
        else:
            envelope = self._encode(plaintext)
            line = _DECISION_PREFIX + base64.b64encode(envelope).decode("ascii")
        with self._decisions.open("a", encoding="utf-8", newline="\n") as handle:
            handle.write(line + "\n")
        with __import__("contextlib").suppress(OSError):
            os.chmod(self._decisions, 0o600)

    def read_decisions(self) -> tuple[dict[str, object], ...]:
        """Return decisions in append order, verifying every record."""
        if not self._decisions.exists():
            return ()
        decisions: list[dict[str, object]] = []
        for line in self._decisions.read_text(encoding="utf-8").splitlines():
            if not line.strip():
                continue
            if line.startswith(_DECISION_PREFIX):
                if self._provider is None:
                    raise StyleVaultError("Encrypted decision log requires its key provider")
                try:
                    envelope = base64.b64decode(
                        line[len(_DECISION_PREFIX) :], validate=True
                    )
                except binascii.Error as exc:
                    raise StyleVaultError("Corrupt encrypted decision log line") from exc
                decoded = self._decode(envelope).decode("utf-8")
            else:
                if self._provider is not None:
                    raise StyleVaultError(
                        "Encrypted style vault refuses a legacy plaintext decision"
                    )
                decoded = line
            try:
                record = json.loads(decoded)
            except json.JSONDecodeError:
                raise StyleVaultError("Corrupt decision log line") from None
            if not isinstance(record, dict):
                raise StyleVaultError("Corrupt decision log record")
            decisions.append(record)
        return tuple(decisions)
