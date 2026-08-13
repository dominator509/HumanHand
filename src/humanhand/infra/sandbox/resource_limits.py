"""Bounded resource limits for parser worker processes."""

from __future__ import annotations

from dataclasses import dataclass

from humanhand.domain.import_policy import ImportPolicy

DEFAULT_MAX_MEMORY_BYTES = 512 * 1024 * 1024


@dataclass(frozen=True)
class ResourceLimits:
    """Hard bounds enforced around one parser worker run."""

    max_time_seconds: float
    max_memory_bytes: int
    max_expanded_bytes: int
    max_nodes: int
    max_archive_depth: int
    max_output_bytes: int


def from_policy(policy: ImportPolicy) -> ResourceLimits:
    """Map an import policy onto the worker resource limits.

    Memory has no policy knob yet, so it uses :data:`DEFAULT_MAX_MEMORY_BYTES`.
    """
    return ResourceLimits(
        max_time_seconds=policy.timeout_seconds,
        max_memory_bytes=DEFAULT_MAX_MEMORY_BYTES,
        max_expanded_bytes=policy.max_expanded_bytes,
        max_nodes=policy.max_nodes,
        max_archive_depth=policy.max_depth,
        max_output_bytes=policy.max_output_bytes,
    )


def validate(limits: ResourceLimits) -> None:
    """Raise ValueError when any limit is nonpositive."""
    for name, value in (
        ("max_time_seconds", limits.max_time_seconds),
        ("max_memory_bytes", limits.max_memory_bytes),
        ("max_expanded_bytes", limits.max_expanded_bytes),
        ("max_nodes", limits.max_nodes),
        ("max_archive_depth", limits.max_archive_depth),
        ("max_output_bytes", limits.max_output_bytes),
    ):
        if value <= 0:
            raise ValueError(f"{name} must be positive, got {value}")
