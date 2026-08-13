"""Deterministic AES-GCM test key provider (CI/development only).

WARNING — documented loudly, by design: this provider derives a fixed,
public key (SHA256 of the literal bytes ``b"humanhand-test-key"``) and a
deterministic nonce per plaintext. It provides ciphertext-confusion, NOT
plaintext-equivalent protection: anyone who knows the layout can decrypt.
It exists so the encryption boundary is exercised with real cryptography
on CI/development machines where DPAPI is unavailable. Production
retention claims must use the DPAPI provider (ADR-005).

Ciphertext layout: ``nonce(12) || tag(16) || ciphertext``. Nonce reuse is
acceptable ONLY for this test provider (the nonce is derived from the
plaintext, so identical plaintexts reuse a nonce with an identical key).
"""

from __future__ import annotations

import hashlib

from cryptography.exceptions import InvalidTag
from cryptography.hazmat.primitives.ciphers.aead import AESGCM

from humanhand.infra.stores.key_provider import EncryptionUnavailableError

_NONCE_BYTES = 12
_TAG_BYTES = 16
_TEST_KEY = hashlib.sha256(b"humanhand-test-key").digest()


class TestKeyProvider:
    """Deterministic AES-GCM provider for tests and non-Windows dev.

    Implements ``KeyProvider``. See the module docstring for the loudly
    documented security caveats.
    """

    provider_name = "test"

    def encrypt(self, plaintext: bytes) -> bytes:
        """Encrypt with AES-GCM under the fixed test key.

        Returns ``nonce(12) || tag(16) || ciphertext``.
        """
        nonce = hashlib.sha256(plaintext).digest()[:_NONCE_BYTES]
        tag_and_ciphertext = AESGCM(_TEST_KEY).encrypt(nonce, plaintext, None)
        return nonce + tag_and_ciphertext

    def decrypt(self, ciphertext: bytes) -> bytes:
        """Decrypt an AES-GCM payload; fail closed on any invalid input."""
        if len(ciphertext) < _NONCE_BYTES + _TAG_BYTES:
            raise EncryptionUnavailableError("test_invalid_ciphertext")
        nonce = ciphertext[:_NONCE_BYTES]
        payload = ciphertext[_NONCE_BYTES:]
        try:
            return AESGCM(_TEST_KEY).decrypt(nonce, payload, None)
        except InvalidTag:
            raise EncryptionUnavailableError("test_decrypt_failed") from None
