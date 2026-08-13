"""Bundle-relative loading of the privacy-modes resource (infra layer)."""

from __future__ import annotations

import json
from pathlib import Path

from humanhand.domain.privacy import PrivacyPolicy, privacy_policy_from_modes

_RESOURCE = (
    Path(__file__).resolve().parent.parent.parent / "resources" / "policies" / "privacy-modes.json"
)


def load_privacy_policy_resource() -> dict[str, object]:
    payload = json.loads(_RESOURCE.read_text(encoding="utf-8"))
    if not isinstance(payload, dict):
        raise ValueError("Privacy modes resource must be an object")
    if payload.get("schema") != "privacy-modes" or payload.get("schema_version") != 1:
        raise ValueError("Unsupported privacy modes resource schema")
    if not isinstance(payload.get("modes"), dict):
        raise ValueError("Privacy modes resource must contain a modes object")
    return payload


def privacy_policy_for_mode(mode: str) -> PrivacyPolicy:
    """Load the privacy policy for a mode from the bundled resource."""
    payload = load_privacy_policy_resource()
    return privacy_policy_from_modes(mode, payload["modes"])
