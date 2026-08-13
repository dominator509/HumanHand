"""Key-provider port and deterministic provider resolution (ADR-005).

The application-layer encryption boundary is a small ``KeyProvider``
protocol. Windows DPAPI is the preferred Windows-first provider; a
deterministic AES-GCM test provider exists for CI/development and is
documented as NOT providing plaintext-equivalent protection.

Master keys are never stored in the project database (ADR-005).
"""

from __future__ import annotations

import sys
from typing import Protocol


class EncryptionUnavailableError(Exception):
    """Raised when the active key provider cannot encrypt or decrypt.

    The message carries an error kind only — never user data.
    """


class KeyProvider(Protocol):
    """Application-layer encryption boundary for sensitive local data."""

    def encrypt(self, plaintext: bytes) -> bytes:
        """Encrypt ``plaintext`` and return provider-encoded bytes."""
        ...

    def decrypt(self, ciphertext: bytes) -> bytes:
        """Decrypt provider-encoded bytes; raise ``EncryptionUnavailableError``
        on any failure (fail closed, never silent)."""
        ...

    @property
    def provider_name(self) -> str:
        """Stable provider name embedded in encrypted-field prefixes."""
        ...


def resolve_key_provider(name: str | None) -> KeyProvider:
    """Resolve the active key provider deterministically (ADR-005).

    - ``None`` or ``"auto"``: DPAPI on Windows, otherwise the test provider.
    - ``"dpapi"``: Windows DPAPI; raises ``EncryptionUnavailableError`` on
      non-Windows platforms.
    - ``"test"``: the deterministic AES-GCM test provider.
    - Unknown names raise ``ValueError``.
    """
    if name is None or name == "auto":
        if sys.platform == "win32":
            from humanhand.infra.stores.windows_dpapi import WindowsDpapiKeyProvider

            return WindowsDpapiKeyProvider()
        from humanhand.infra.stores.test_key_provider import TestKeyProvider

        return TestKeyProvider()
    if name == "dpapi":
        from humanhand.infra.stores.windows_dpapi import WindowsDpapiKeyProvider

        return WindowsDpapiKeyProvider()
    if name == "test":
        from humanhand.infra.stores.test_key_provider import TestKeyProvider

        return TestKeyProvider()
    raise ValueError(f"Unknown key provider: {name!r}")
