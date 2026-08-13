"""Unit tests for worker resource limits."""

from __future__ import annotations

import dataclasses

import pytest

from humanhand.domain.import_policy import ImportPolicy
from humanhand.infra.sandbox.resource_limits import (
    DEFAULT_MAX_MEMORY_BYTES,
    ResourceLimits,
    from_policy,
    validate,
)


def _valid_limits() -> ResourceLimits:
    return ResourceLimits(
        max_time_seconds=1.0,
        max_memory_bytes=1024,
        max_expanded_bytes=2048,
        max_nodes=100,
        max_archive_depth=4,
        max_output_bytes=4096,
    )


class TestFromPolicy:
    def test_maps_policy_fields(self) -> None:
        policy = ImportPolicy(
            lane="style",
            max_bytes=1_000,
            max_expanded_bytes=2_000,
            max_nodes=50,
            max_depth=7,
            timeout_seconds=3.5,
            max_output_bytes=4_000,
        )
        limits = from_policy(policy)
        assert limits.max_time_seconds == 3.5
        assert limits.max_memory_bytes == DEFAULT_MAX_MEMORY_BYTES
        assert limits.max_expanded_bytes == 2_000
        assert limits.max_nodes == 50
        assert limits.max_archive_depth == 7
        assert limits.max_output_bytes == 4_000


class TestDefaultMaxMemory:
    def test_default_max_memory_is_positive(self) -> None:
        assert DEFAULT_MAX_MEMORY_BYTES > 0
        assert DEFAULT_MAX_MEMORY_BYTES == 512 * 1024 * 1024


class TestValidate:
    @pytest.mark.parametrize(
        "field",
        [
            "max_time_seconds",
            "max_memory_bytes",
            "max_expanded_bytes",
            "max_nodes",
            "max_archive_depth",
            "max_output_bytes",
        ],
    )
    @pytest.mark.parametrize("bad_value", [0, -1])
    def test_nonpositive_field_rejected(self, field: str, bad_value: int) -> None:
        with pytest.raises(ValueError, match=field):
            validate(dataclasses.replace(_valid_limits(), **{field: bad_value}))

    def test_valid_limits_accepted(self) -> None:
        validate(_valid_limits())  # must not raise
