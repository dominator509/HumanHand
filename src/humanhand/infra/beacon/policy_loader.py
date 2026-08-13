"""Bundle-relative loading of the Beacon policy resources (infra layer)."""

from __future__ import annotations

import json
from pathlib import Path

from humanhand.domain.beacon_policy import (
    MANDATORY_BLOCKED_ACTIONS,
    load_allowed_actions_from_resource,
    load_blocked_actions_from_resource,
    load_trust_tiers_from_resource,
)

_POLICIES_DIR = Path(__file__).resolve().parent.parent.parent / "resources" / "policies"


def _load(name: str) -> dict[str, object]:
    path = _POLICIES_DIR / name
    try:
        payload = json.loads(path.read_text(encoding="utf-8"))
    except (OSError, UnicodeError, json.JSONDecodeError) as exc:
        raise ValueError(f"Cannot load Beacon policy resource {name!r}") from exc
    if not isinstance(payload, dict):
        raise ValueError(f"Beacon policy resource {name!r} must be an object")
    return payload


def load_allowed_actions() -> frozenset[str]:
    resource = _load("beacon-allowed-actions.json")
    return frozenset(load_allowed_actions_from_resource(resource))


def load_blocked_actions() -> frozenset[str]:
    resource = _load("beacon-blocked-actions.json")
    blocked = frozenset(load_blocked_actions_from_resource(resource))
    missing = MANDATORY_BLOCKED_ACTIONS - blocked
    if missing:
        raise ValueError(f"Beacon policy omits mandatory blocked actions: {sorted(missing)!r}")
    return blocked


def load_trust_tiers() -> dict[str, str]:
    return load_trust_tiers_from_resource(_load("trusted-source-tiers.json"))
