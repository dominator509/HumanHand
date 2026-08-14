"""Central production privacy runtime (EP-019).

Every integrated workflow command resolves privacy once and receives the same
policy, logger behavior, cache behavior, and encryption provider. Strict and
regulated modes fail closed when a production-capable key provider is not
available; the deterministic test provider is never selected silently.
"""

from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path

from humanhand.application.ports import Logger
from humanhand.domain.privacy import PrivacyPolicy, load_privacy_policy
from humanhand.infra.config import Config
from humanhand.infra.privacy.null_logger import NullLogger
from humanhand.infra.stores.integrated_project_store import IntegratedProjectStore
from humanhand.infra.stores.key_provider import (
    EncryptionUnavailableError,
    KeyProvider,
    resolve_key_provider,
)
from humanhand.infra.stores.style_vault import StyleVault


class PrivacyRuntimeError(Exception):
    """Raised when the declared privacy policy cannot be enforced."""


@dataclass(frozen=True)
class PrivacyRuntime:
    """Resolved privacy controls for one command invocation."""

    policy: PrivacyPolicy
    key_provider: KeyProvider | None
    logger: Logger

    @property
    def encrypted_retention(self) -> bool:
        return self.key_provider is not None


def build_privacy_runtime(config: Config, *, logger: Logger | None = None) -> PrivacyRuntime:
    """Resolve a privacy policy and production-safe key provider.

    ``strict_local`` and ``regulated`` require encrypted sensitive retention.
    On Windows, ``auto`` resolves to DPAPI. On other platforms ``auto`` would
    resolve to the deterministic test provider, so production modes refuse it
    unless the operator explicitly enables that provider for CI/development.
    """
    policy = load_privacy_policy(config.privacy_mode)
    resolved_logger: Logger = (
        NullLogger() if policy.mode.value == "strict_local" else (logger or NullLogger())
    )
    provider: KeyProvider | None = None
    if policy.encrypt_sensitive_fields:
        try:
            provider = resolve_key_provider(config.key_provider)
        except (EncryptionUnavailableError, ValueError) as exc:
            raise PrivacyRuntimeError("secure_key_provider_unavailable") from exc
        if provider.provider_name == "test" and not config.allow_test_key_provider:
            raise PrivacyRuntimeError(
                "test_key_provider_forbidden: configure DPAPI or explicitly enable the test "
                "provider for non-production CI only"
            )
    return PrivacyRuntime(policy=policy, key_provider=provider, logger=resolved_logger)


def open_project_store(root: str | Path, runtime: PrivacyRuntime) -> IntegratedProjectStore:
    """Open an integrated project store under the resolved privacy policy."""
    return IntegratedProjectStore(
        root,
        encryption_enabled=runtime.encrypted_retention,
        key_provider=runtime.key_provider,
    )


def open_style_vault(root: str | Path, runtime: PrivacyRuntime) -> StyleVault:
    """Open the Style Fidelity Vault under the same privacy runtime."""
    return StyleVault(root, key_provider=runtime.key_provider)
