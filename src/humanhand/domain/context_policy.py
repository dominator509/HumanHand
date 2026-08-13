"""Context capsule policy limits (SPEC-012, blueprint 9.6).

The policy is plain configuration: every payload key is exactly one
dataclass field name and the payload carries no schema discriminator, so
``ContextPolicy(**policy_to_payload(p))`` round-trips by construction.
Limits are positive integers; :func:`validate_policy` fails closed on
nonpositive values.
"""

from __future__ import annotations

from dataclasses import dataclass

from humanhand.domain.types import DomainError

_LIMIT_FIELDS = (
    "block_window",
    "max_protected_spans",
    "max_claims",
    "max_entities",
    "max_exemplars",
    "max_invariants",
    "max_tendencies",
)


@dataclass(frozen=True)
class ContextPolicy:
    """Limits and switches for one context capsule."""

    block_window: int = 2  # adjacent blocks on each side
    max_protected_spans: int = 50
    max_claims: int = 50
    max_entities: int = 50
    max_exemplars: int = 5
    max_invariants: int = 20
    max_tendencies: int = 20
    include_untrusted_labels: bool = True


def validate_policy(policy: ContextPolicy) -> None:
    """Validate the policy, raising DomainError on nonpositive limits."""
    for name in _LIMIT_FIELDS:
        if getattr(policy, name) <= 0:
            raise DomainError(f"{name} must be a positive integer")


def policy_to_payload(policy: ContextPolicy) -> dict[str, object]:
    """Render the policy as a field-name-keyed JSON-ready payload."""
    return {
        "block_window": policy.block_window,
        "max_protected_spans": policy.max_protected_spans,
        "max_claims": policy.max_claims,
        "max_entities": policy.max_entities,
        "max_exemplars": policy.max_exemplars,
        "max_invariants": policy.max_invariants,
        "max_tendencies": policy.max_tendencies,
        "include_untrusted_labels": policy.include_untrusted_labels,
    }
