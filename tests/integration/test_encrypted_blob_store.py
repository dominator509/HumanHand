"""Integration tests for the file-backed EncryptedBlobStore."""

from __future__ import annotations

import hashlib
import sys
from pathlib import Path

import pytest

from humanhand.infra.stores.encrypted_blob_store import BlobStoreError, EncryptedBlobStore
from humanhand.infra.stores.key_provider import EncryptionUnavailableError, resolve_key_provider
from humanhand.infra.stores.test_key_provider import TestKeyProvider
from humanhand.infra.stores.windows_dpapi import WindowsDpapiKeyProvider


@pytest.fixture
def store(tmp_path: Path) -> EncryptedBlobStore:
    return EncryptedBlobStore(tmp_path / "blobroot", TestKeyProvider())


class TestEncryptedBlobStore:
    def test_store_and_load_round_trip(self, store: EncryptedBlobStore) -> None:
        raw = b"retained original bytes"
        blob_id = store.store(raw)
        assert len(blob_id) == 64
        assert store.exists(blob_id)
        assert store.load(blob_id) == raw

    def test_re_store_identical_content_is_idempotent(self, store: EncryptedBlobStore) -> None:
        first = store.store(b"same bytes")
        second = store.store(b"same bytes")
        assert first == second

    def test_load_missing_raises(self, store: EncryptedBlobStore) -> None:
        with pytest.raises(BlobStoreError, match="not stored"):
            store.load("0" * 64)

    def test_invalid_blob_id_rejected(self, store: EncryptedBlobStore) -> None:
        with pytest.raises(BlobStoreError, match="Invalid blob id"):
            store.load("../outside")

    def test_tampered_blob_file_fails_closed(
        self, store: EncryptedBlobStore, tmp_path: Path
    ) -> None:
        blob_id = store.store(b"tamper me")
        blobs_dir = tmp_path / "blobroot" / "blobs"
        (blobs_dir / f"{blob_id}.bin").write_bytes(b"tampered!")
        with pytest.raises(EncryptionUnavailableError):
            store.load(blob_id)

    def test_collision_with_different_content_raises(
        self, store: EncryptedBlobStore, tmp_path: Path
    ) -> None:
        target = b"target plaintext"
        different = b"different plaintext"
        blobs_dir = tmp_path / "blobroot" / "blobs"
        blob_id = hashlib.sha256(target).hexdigest()
        # A real sha256 collision is infeasible; simulate a pre-existing
        # file at the target path that decrypts to different content.
        (blobs_dir / f"{blob_id}.bin").write_bytes(TestKeyProvider().encrypt(different))
        with pytest.raises(BlobStoreError, match="collision"):
            store.store(target)

    def test_integrity_check_rejects_wrong_content(
        self, store: EncryptedBlobStore, tmp_path: Path
    ) -> None:
        blob_id = store.store(b"integrity check")
        blobs_dir = tmp_path / "blobroot" / "blobs"
        # Replace the file with a valid encryption of DIFFERENT content.
        (blobs_dir / f"{blob_id}.bin").write_bytes(TestKeyProvider().encrypt(b"other"))
        with pytest.raises(BlobStoreError, match="integrity"):
            store.load(blob_id)

    def test_clean_file_layout_after_normal_ops(
        self, store: EncryptedBlobStore, tmp_path: Path
    ) -> None:
        first = store.store(b"first blob")
        second = store.store(b"second blob")
        blobs_dir = tmp_path / "blobroot" / "blobs"
        files = sorted(path.name for path in blobs_dir.iterdir())
        assert files == sorted([f"{first}.bin", f"{second}.bin"])
        for name in files:
            assert not name.endswith(".tmp")
            contents = (blobs_dir / name).read_bytes()
            # Stored files carry provider-encoded bytes, never plaintext.
            assert b"first blob" not in contents
            assert b"second blob" not in contents


class TestWindowsDpapi:
    def test_dpapi_round_trip(self) -> None:
        if sys.platform != "win32":
            pytest.skip("Windows DPAPI is only available on win32")
        provider = WindowsDpapiKeyProvider()
        assert provider.provider_name == "dpapi"
        plaintext = b"dpapi round trip bytes"
        ciphertext = provider.encrypt(plaintext)
        assert ciphertext != plaintext
        assert provider.decrypt(ciphertext) == plaintext

    def test_dpapi_empty_round_trip(self) -> None:
        if sys.platform != "win32":
            pytest.skip("Windows DPAPI is only available on win32")
        provider = WindowsDpapiKeyProvider()
        assert provider.decrypt(provider.encrypt(b"")) == b""

    def test_dpapi_tampered_blob_fails_closed(self) -> None:
        if sys.platform != "win32":
            pytest.skip("Windows DPAPI is only available on win32")
        provider = WindowsDpapiKeyProvider()
        ciphertext = bytearray(provider.encrypt(b"tamper target"))
        ciphertext[len(ciphertext) // 2] ^= 0x01
        with pytest.raises(EncryptionUnavailableError, match="unprotect"):
            provider.decrypt(bytes(ciphertext))

    def test_auto_resolution_is_dpapi_on_windows(self) -> None:
        if sys.platform != "win32":
            pytest.skip("Windows DPAPI is only available on win32")
        provider = resolve_key_provider("auto")
        assert isinstance(provider, WindowsDpapiKeyProvider)
