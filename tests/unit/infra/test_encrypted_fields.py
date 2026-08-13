"""Unit tests for the EncryptedFieldCodec."""

from __future__ import annotations

import pytest

from humanhand.infra.stores.encrypted_fields import EncryptedFieldCodec
from humanhand.infra.stores.key_provider import EncryptionUnavailableError
from humanhand.infra.stores.test_key_provider import TestKeyProvider


@pytest.fixture
def codec() -> EncryptedFieldCodec:
    return EncryptedFieldCodec(TestKeyProvider())


class TestEncryptedFieldCodec:
    def test_round_trip(self, codec: EncryptedFieldCodec) -> None:
        plaintext = "sensitive style sample text"
        encoded = codec.encode(plaintext)
        assert encoded.startswith("encv1:test:")
        assert codec.decode(encoded) == plaintext

    def test_unicode_round_trip(self, codec: EncryptedFieldCodec) -> None:
        plaintext = "sample with unicode: éü中文"
        assert codec.decode(codec.encode(plaintext)) == plaintext

    def test_decode_if_encoded_leaves_plain_values_untouched(
        self, codec: EncryptedFieldCodec
    ) -> None:
        assert codec.decode_if_encoded("plain legacy text") == "plain legacy text"

    def test_decode_if_encoded_decodes_encoded_value(self, codec: EncryptedFieldCodec) -> None:
        encoded = codec.encode("secret")
        assert codec.decode_if_encoded(encoded) == "secret"

    def test_encode_if_enabled_false_is_identity(self, codec: EncryptedFieldCodec) -> None:
        assert codec.encode_if_enabled("plaintext", enabled=False) == "plaintext"

    def test_encode_if_enabled_true_encodes(self, codec: EncryptedFieldCodec) -> None:
        encoded = codec.encode_if_enabled("plaintext", enabled=True)
        assert encoded != "plaintext"
        assert encoded.startswith("encv1:")

    def test_decode_garbage_fails_closed(self, codec: EncryptedFieldCodec) -> None:
        with pytest.raises(EncryptionUnavailableError, match="prefix"):
            codec.decode("garbage")

    def test_decode_without_provider_part_fails_closed(self, codec: EncryptedFieldCodec) -> None:
        with pytest.raises(EncryptionUnavailableError, match="malformed"):
            codec.decode("encv1:no-separator")

    def test_provider_mismatch_rejected(self, codec: EncryptedFieldCodec) -> None:
        encoded = codec.encode("secret")
        mismatched = encoded.replace("encv1:test:", "encv1:dpapi:", 1)
        with pytest.raises(EncryptionUnavailableError, match="provider"):
            codec.decode(mismatched)

    def test_bad_base64_rejected(self, codec: EncryptedFieldCodec) -> None:
        with pytest.raises(EncryptionUnavailableError, match="base64"):
            codec.decode("encv1:test:!!!not-base64!!!")

    def test_tampered_payload_fails_closed(self, codec: EncryptedFieldCodec) -> None:
        encoded = codec.encode("secret")
        tampered = encoded[:-2] + ("AA" if not encoded.endswith("AA") else "BB")
        with pytest.raises(EncryptionUnavailableError):
            codec.decode(tampered)
