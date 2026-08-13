"""Privacy modes and policies (SPEC-013, blueprint 10).

Three privacy modes are supported: ``strict_local``, ``private_audited``,
and ``regulated``. Policies load deterministically from the bundled
``resources/policies/privacy-modes.json`` resource at import time; no
network and no user configuration is involved.

Repo invariants (forced here regardless of the resource contents):
- ``raw_text_logging`` is ALWAYS False: user text, prompts, and generated
  output are never logged in any mode.
- ``obsidian_projection_auto`` is ALWAYS False: Obsidian projection is a
  user-triggered action, never automatic.
"""

from __future__ import annotations

from dataclasses import dataclass
from enum import StrEnum

from humanhand.domain.types import DomainError

PRIVACY_SCHEMA_VERSION = 1
_SCHEMA_NAME = "privacy-policy"

_FLAG_KEYS = (
    "network_allowed",
    "raw_text_logging",
    "detector_cache_enabled",
    "obsidian_projection_auto",
    "retention_enforced",
    "encrypt_sensitive_fields",
)


class PrivacyMode(StrEnum):
    """The three supported privacy modes."""

    STRICT_LOCAL = "strict_local"
    PRIVATE_AUDITED = "private_audited"
    REGULATED = "regulated"


@dataclass(frozen=True)
class PrivacyPolicy:
    """Immutable privacy policy for one mode."""

    mode: PrivacyMode
    network_allowed: bool
    raw_text_logging: bool  # ALWAYS False for every mode (repo invariant)
    detector_cache_enabled: bool
    obsidian_projection_auto: bool  # ALWAYS False (projection is user-triggered)
    retention_enforced: bool
    encrypt_sensitive_fields: bool


def validate_mode_resource(modes: object) -> dict[str, dict[str, bool]]:
    """Validate and copy an untrusted privacy-mode mapping without I/O."""
    if not isinstance(modes, dict):
        raise DomainError("Bundled privacy-modes resource must contain a 'modes' object")
    parsed: dict[str, dict[str, bool]] = {}
    for name, entry in modes.items():
        if not isinstance(name, str) or not isinstance(entry, dict):
            raise DomainError("Bundled privacy-modes resource contains an invalid mode entry")
        flags: dict[str, bool] = {}
        for key in _FLAG_KEYS:
            value = entry.get(key)
            if not isinstance(value, bool):
                raise DomainError(f"Bundled privacy-modes resource: {name}.{key} must be a boolean")
            flags[key] = value
        parsed[name] = flags
    return parsed


_DEFAULT_MODES = validate_mode_resource(
    {
        "strict_local": {
            "network_allowed": False,
            "raw_text_logging": False,
            "detector_cache_enabled": False,
            "obsidian_projection_auto": False,
            "retention_enforced": True,
            "encrypt_sensitive_fields": True,
        },
        "private_audited": {
            "network_allowed": True,
            "raw_text_logging": False,
            "detector_cache_enabled": True,
            "obsidian_projection_auto": False,
            "retention_enforced": False,
            "encrypt_sensitive_fields": False,
        },
        "regulated": {
            "network_allowed": True,
            "raw_text_logging": False,
            "detector_cache_enabled": False,
            "obsidian_projection_auto": False,
            "retention_enforced": True,
            "encrypt_sensitive_fields": True,
        },
    }
)


def privacy_policy_from_modes(mode: str | PrivacyMode, modes: object) -> PrivacyPolicy:
    """Load the policy for a mode from the bundled resource (deterministic).

    Unknown mode names raise ValueError. ``raw_text_logging`` and
    ``obsidian_projection_auto`` are forced False regardless of the
    resource contents (documented repo invariants).
    """
    mode_name = mode.value if isinstance(mode, PrivacyMode) else mode
    parsed = validate_mode_resource(modes)
    if mode_name not in parsed:
        raise ValueError(f"Unknown privacy mode: {mode_name!r}")
    raw = parsed[mode_name]
    return PrivacyPolicy(
        mode=PrivacyMode(mode_name),
        network_allowed=raw["network_allowed"],
        raw_text_logging=False,  # repo invariant: raw text is never logged
        detector_cache_enabled=raw["detector_cache_enabled"],
        obsidian_projection_auto=False,  # invariant: projection is user-triggered
        retention_enforced=raw["retention_enforced"],
        encrypt_sensitive_fields=raw["encrypt_sensitive_fields"],
    )


def load_privacy_policy(mode: str | PrivacyMode) -> PrivacyPolicy:
    """Build the repository-default policy without performing file I/O."""
    return privacy_policy_from_modes(mode, _DEFAULT_MODES)


def policy_to_payload(policy: PrivacyPolicy) -> dict[str, object]:
    """Render a privacy policy as a stable JSON-ready payload."""
    return {
        "schema": _SCHEMA_NAME,
        "schema_version": PRIVACY_SCHEMA_VERSION,
        "mode": policy.mode.value,
        "network_allowed": policy.network_allowed,
        "raw_text_logging": policy.raw_text_logging,
        "detector_cache_enabled": policy.detector_cache_enabled,
        "obsidian_projection_auto": policy.obsidian_projection_auto,
        "retention_enforced": policy.retention_enforced,
        "encrypt_sensitive_fields": policy.encrypt_sensitive_fields,
    }


def _expect_bool(payload: dict[str, object], key: str) -> bool:
    value = payload.get(key)
    if not isinstance(value, bool):
        raise DomainError(f"Invalid privacy policy payload: {key} must be a boolean")
    return value


def policy_from_payload(payload: dict[str, object]) -> PrivacyPolicy:
    """Deserialize and validate a privacy policy payload (strict, fails closed).

    Raises DomainError on a missing or unknown mode, a wrong field type,
    or a payload that violates a repo invariant (raw text logging enabled
    or automatic Obsidian projection).
    """
    if payload.get("schema") != _SCHEMA_NAME:
        raise DomainError("Invalid privacy policy payload: schema must be 'privacy-policy'")
    if payload.get("schema_version") != PRIVACY_SCHEMA_VERSION:
        raise DomainError("Unsupported privacy policy payload schema version")
    mode_value = payload.get("mode")
    if not isinstance(mode_value, str):
        raise DomainError("Invalid privacy policy payload: mode must be a string")
    try:
        mode = PrivacyMode(mode_value)
    except ValueError as exc:
        raise DomainError(f"Invalid privacy policy payload: unknown mode {mode_value!r}") from exc
    raw_text_logging = _expect_bool(payload, "raw_text_logging")
    obsidian_projection_auto = _expect_bool(payload, "obsidian_projection_auto")
    if raw_text_logging:
        raise DomainError(
            "Invalid privacy policy payload: raw_text_logging violates the repo invariant "
            "(raw text is never logged in any mode)"
        )
    if obsidian_projection_auto:
        raise DomainError(
            "Invalid privacy policy payload: obsidian_projection_auto violates the repo "
            "invariant (projection is user-triggered only)"
        )
    return PrivacyPolicy(
        mode=mode,
        network_allowed=_expect_bool(payload, "network_allowed"),
        raw_text_logging=raw_text_logging,
        detector_cache_enabled=_expect_bool(payload, "detector_cache_enabled"),
        obsidian_projection_auto=obsidian_projection_auto,
        retention_enforced=_expect_bool(payload, "retention_enforced"),
        encrypt_sensitive_fields=_expect_bool(payload, "encrypt_sensitive_fields"),
    )


def validate_network_use(policy: PrivacyPolicy, *, would_use_network: bool) -> tuple[str, ...]:
    """Return violation codes for a proposed network use under ``policy``.

    Returns ``("network_use_forbidden",)`` when the policy forbids network
    access and the caller would use it; otherwise an empty tuple.
    """
    if would_use_network and not policy.network_allowed:
        return ("network_use_forbidden",)
    return ()


def validate_cache_use(policy: PrivacyPolicy, *, cache_would_be_used: bool) -> tuple[str, ...]:
    """Return violation codes for a proposed detector-cache use under ``policy``.

    Returns ``("cache_use_forbidden",)`` when the policy disables the
    detector cache and the caller would use it; otherwise an empty tuple.
    """
    if cache_would_be_used and not policy.detector_cache_enabled:
        return ("cache_use_forbidden",)
    return ()
