"""Application-layer encrypted-field codec for sensitive DB text fields.

Layout of an encoded value::

    encv1:<provider_name>:<base64(ciphertext)>

Decoding verifies the ``encv1:`` prefix and the provider name; anything
else raises ``EncryptionUnavailableError`` (fail closed, never silent).
Legacy plaintext rows remain readable via ``decode_if_encoded``.
"""

from __future__ import annotations

import base64
import binascii

from humanhand.infra.stores.key_provider import EncryptionUnavailableError, KeyProvider

_PREFIX = "encv1:"


class EncryptedFieldCodec:
    """Encode/decode sensitive text fields through a ``KeyProvider``."""

    def __init__(self, provider: KeyProvider) -> None:
        self._provider = provider

    def encode(self, plaintext: str) -> str:
        """Encode ``plaintext`` as ``encv1:<provider>:<base64(ciphertext)>``."""
        ciphertext = self._provider.encrypt(plaintext.encode("utf-8"))
        return (
            _PREFIX
            + self._provider.provider_name
            + ":"
            + base64.b64encode(ciphertext).decode("ascii")
        )

    def decode(self, encoded: str) -> str:
        """Decode an ``encv1`` value; fail closed on any malformed input."""
        if not encoded.startswith(_PREFIX):
            raise EncryptionUnavailableError("encv1_prefix_missing")
        rest = encoded[len(_PREFIX) :]
        provider_name, separator, encoded_payload = rest.partition(":")
        if not separator:
            raise EncryptionUnavailableError("encv1_malformed")
        if provider_name != self._provider.provider_name:
            raise EncryptionUnavailableError("encv1_provider_mismatch")
        try:
            ciphertext = base64.b64decode(encoded_payload, validate=True)
        except (ValueError, binascii.Error):
            raise EncryptionUnavailableError("encv1_bad_base64") from None
        try:
            return self._provider.decrypt(ciphertext).decode("utf-8")
        except UnicodeDecodeError:
            raise EncryptionUnavailableError("encv1_not_utf8") from None

    def decode_if_encoded(self, value: str) -> str:
        """Decode when the value carries the ``encv1:`` prefix.

        Plaintext legacy rows are returned unchanged.
        """
        if value.startswith(_PREFIX):
            return self.decode(value)
        return value

    def encode_if_enabled(self, value: str, *, enabled: bool) -> str:
        """Encode when ``enabled`` is true, else return ``value`` unchanged."""
        if enabled:
            return self.encode(value)
        return value
