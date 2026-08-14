"""Unit tests for the centralized EP-019 privacy runtime."""

from __future__ import annotations

from dataclasses import replace
from pathlib import Path

import pytest

from humanhand.infra.config import Config
from humanhand.infra.privacy.runtime import (
    PrivacyRuntimeError,
    build_privacy_runtime,
    open_style_vault,
)


def test_private_audited_does_not_force_encryption() -> None:
    runtime = build_privacy_runtime(Config(privacy_mode="private_audited"))
    assert runtime.policy.mode.value == "private_audited"
    assert runtime.key_provider is None
    assert runtime.encrypted_retention is False


def test_strict_mode_refuses_test_provider_by_default() -> None:
    config = Config(privacy_mode="strict_local", key_provider="test")
    with pytest.raises(PrivacyRuntimeError, match="test_key_provider_forbidden"):
        build_privacy_runtime(config)


def test_test_provider_requires_explicit_nonproduction_opt_in() -> None:
    config = Config(
        privacy_mode="strict_local",
        key_provider="test",
        allow_test_key_provider=True,
    )
    runtime = build_privacy_runtime(config)
    assert runtime.encrypted_retention is True
    assert runtime.key_provider is not None
    assert runtime.key_provider.provider_name == "test"


def test_encrypted_style_vault_retains_no_plaintext(tmp_path: Path) -> None:
    config = replace(
        Config(),
        privacy_mode="strict_local",
        key_provider="test",
        allow_test_key_provider=True,
    )
    runtime = build_privacy_runtime(config)
    vault = open_style_vault(tmp_path / "vault", runtime)
    raw = b"private style sentinel 2197"
    artifact_id = vault.store_original(raw)
    assert vault.load_original(artifact_id) == raw
    stored = (vault.root / "originals" / f"{artifact_id}.bin").read_bytes()
    assert raw not in stored
    assert stored.startswith(b"HHENC1:")
