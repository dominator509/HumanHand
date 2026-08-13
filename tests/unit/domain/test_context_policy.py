"""Unit tests for context capsule policy validation and payloads."""

from __future__ import annotations

from typing import Any, cast

import pytest

from humanhand.domain.context_policy import (
    ContextPolicy,
    policy_to_payload,
    validate_policy,
)
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


class TestValidatePolicy:
    def test_default_policy_is_valid(self) -> None:
        validate_policy(ContextPolicy())

    @pytest.mark.parametrize("field", _LIMIT_FIELDS)
    @pytest.mark.parametrize("value", [0, -1])
    def test_rejects_nonpositive_limits(self, field: str, value: int) -> None:
        policy = ContextPolicy(**cast("dict[str, Any]", {field: value}))
        with pytest.raises(DomainError, match=field):
            validate_policy(policy)

    def test_accepts_custom_positive_limits(self) -> None:
        policy = ContextPolicy(block_window=1, max_claims=2, max_entities=3)
        validate_policy(policy)


class TestPolicyPayload:
    def test_round_trip(self) -> None:
        policy = ContextPolicy(block_window=1, max_claims=2, include_untrusted_labels=False)
        assert ContextPolicy(**cast("dict[str, Any]", policy_to_payload(policy))) == policy

    def test_payload_is_field_name_keyed(self) -> None:
        # Hand-verified: every payload key is exactly one dataclass field
        # name and the payload carries no schema discriminator.
        payload = policy_to_payload(ContextPolicy())
        assert set(payload) == {
            "block_window",
            "max_protected_spans",
            "max_claims",
            "max_entities",
            "max_exemplars",
            "max_invariants",
            "max_tendencies",
            "include_untrusted_labels",
        }
        assert payload["block_window"] == 2
        assert payload["max_claims"] == 50
        assert payload["include_untrusted_labels"] is True

    def test_defaults_round_trip(self) -> None:
        assert ContextPolicy(**cast("dict[str, Any]", policy_to_payload(ContextPolicy()))) == (
            ContextPolicy()
        )
