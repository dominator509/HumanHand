"""File-backed encrypted blob store (ADR-005).

Layout under the store root:

- ``blobs/<blob_id>.bin`` — provider-encoded bytes, one file per blob;
  the blob id is the sha256 hex digest of the plaintext.

Writes are atomic (temp file + ``os.replace``); re-storing identical
content is idempotent; a blob id collision with different content raises
``BlobStoreError``. Reads decrypt the file and verify that
``sha256(plaintext) == blob id`` before returning the bytes.
"""

from __future__ import annotations

import hashlib
import os
import re
import tempfile
from pathlib import Path

from humanhand.infra.stores.key_provider import KeyProvider

_BLOB_ID_RE = re.compile(r"^[0-9a-f]{64}$")


class BlobStoreError(Exception):
    """Raised when blob store invariants are violated (id, integrity)."""


def _sha256(data: bytes) -> str:
    return hashlib.sha256(data).hexdigest()


def _validated_blob_id(blob_id: str) -> None:
    """Reject path-traversal and malformed blob ids (fail closed)."""
    if _BLOB_ID_RE.match(blob_id) is None:
        raise BlobStoreError(f"Invalid blob id: {blob_id!r}")


class EncryptedBlobStore:
    """Local, encrypted, integrity-verified blob store under ``<root>/blobs/``."""

    def __init__(self, root: str | Path, provider: KeyProvider) -> None:
        self._root = Path(root)
        self._blobs = self._root / "blobs"
        self._blobs.mkdir(parents=True, exist_ok=True)
        self._provider = provider

    def store(self, plaintext: bytes) -> str:
        """Store ``plaintext`` encrypted and return its blob id.

        Re-storing identical content is idempotent; storing different
        content under an identical id raises ``BlobStoreError``.
        """
        blob_id = _sha256(plaintext)
        path = self._blobs / f"{blob_id}.bin"
        if path.exists():
            existing_plaintext = self._provider.decrypt(path.read_bytes())
            if existing_plaintext != plaintext:
                raise BlobStoreError(f"Blob id collision with different content: {blob_id}")
            return blob_id
        encoded = self._provider.encrypt(plaintext)
        descriptor, temporary_name = tempfile.mkstemp(
            dir=self._blobs,
            prefix=f".{blob_id}.",
            suffix=".tmp",
        )
        temporary = Path(temporary_name)
        try:
            with os.fdopen(descriptor, "wb") as handle:
                handle.write(encoded)
                handle.flush()
                os.fsync(handle.fileno())
            os.replace(temporary, path)
        finally:
            temporary.unlink(missing_ok=True)
        return blob_id

    def load(self, blob_id: str) -> bytes:
        """Read a blob back, decrypting and verifying its sha256 digest."""
        _validated_blob_id(blob_id)
        path = self._blobs / f"{blob_id}.bin"
        if not path.exists():
            raise BlobStoreError(f"Blob not stored: {blob_id}")
        plaintext = self._provider.decrypt(path.read_bytes())
        if _sha256(plaintext) != blob_id:
            raise BlobStoreError(f"Blob integrity check failed: {blob_id}")
        return plaintext

    def exists(self, blob_id: str) -> bool:
        """True when a blob with this id is stored."""
        _validated_blob_id(blob_id)
        return (self._blobs / f"{blob_id}.bin").exists()
