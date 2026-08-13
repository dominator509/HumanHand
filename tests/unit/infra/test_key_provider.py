"""Unit tests for key-provider resolution and the AES-GCM test provider."""

from __future__ import annotations

import pytest

from humanhand.infra.stores.key_provider import (
    EncryptionUnavailableError,
    resolve_key_provider,
)
from humanhand.infra.stores.test_key_provider import TestKeyProvider

_KNOWN_PROVIDER_NAMES = {"dpapi", "test"}


class TestResolveKeyProvider:
    def test_resolve_test_provider(self) -> None:
        provider = resolve_key_provider("test")
        assert isinstance(provider, TestKeyProvider)
        assert provider.provider_name == "test"

    def test_resolve_none_returns_a_provider(self) -> None:
        provider = resolve_key_provider(None)
        assert provider.provider_name in _KNOWN_PROVIDER_NAMES
        assert callable(provider.encrypt)
        assert callable(provider.decrypt)

    def test_resolve_auto_returns_a_provider(self) -> None:
        provider = resolve_key_provider("auto")
        assert provider.provider_name in _KNOWN_PROVIDER_NAMES
        assert callable(provider.encrypt)
        assert callable(provider.decrypt)

    def test_unknown_name_raises_value_error(self) -> None:
        with pytest.raises(ValueError, match="Unknown key provider"):
            resolve_key_provider("nonsense")


class TestTestKeyProvider:
    def test_round_trip(self) -> None:
        provider = TestKeyProvider()
        plaintext = b"round trip bytes"
        ciphertext = provider.encrypt(plaintext)
        assert ciphertext != plaintext
        assert provider.decrypt(ciphertext) == plaintext

    def test_empty_round_trip(self) -> None:
        provider = TestKeyProvider()
        assert provider.decrypt(provider.encrypt(b"")) == b""

    def test_ciphertext_layout(self) -> None:
        provider = TestKeyProvider()
        plaintext = b"layout probe"
        ciphertext = provider.encrypt(plaintext)
        assert len(ciphertext) == 12 + 16 + len(plaintext)

    def test_tampered_ciphertext_fails_closed(self) -> None:
        provider = TestKeyProvider()
        ciphertext = bytearray(provider.encrypt(b"secret data"))
        ciphertext[-1] ^= 0xFF
        with pytest.raises(EncryptionUnavailableError):
            provider.decrypt(bytes(ciphertext))

    def test_truncated_ciphertext_fails_closed(self) -> None:
        provider = TestKeyProvider()
        ciphertext = provider.encrypt(b"secret data")
        with pytest.raises(EncryptionUnavailableError):
            provider.decrypt(ciphertext[:12])

    def test_deterministic_output(self) -> None:
        provider = TestKeyProvider()
        first = provider.encrypt(b"same plaintext")
        second = provider.encrypt(b"same plaintext")
        assert first == second
