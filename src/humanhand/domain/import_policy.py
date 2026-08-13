"""Deterministic import policy and limit checks for clean-room imports."""

from __future__ import annotations

from dataclasses import dataclass, field

from humanhand.domain.import_findings import (
    FindingCategory,
    FindingCode,
    FindingSeverity,
    ImportFinding,
)
from humanhand.domain.types import DomainError
from humanhand.domain.unicode_policy import UnicodePolicy

POLICY_VERSION = "1"

LANES = ("source", "style")
NETWORK_POLICIES = ("deny",)
REVISION_POLICIES = ("review_required", "reject")

DEFAULT_MAX_BYTES = 4_000_000
DEFAULT_MAX_EXPANDED_BYTES = 16_000_000
DEFAULT_MAX_NODES = 50_000
DEFAULT_MAX_DEPTH = 32
DEFAULT_TIMEOUT_SECONDS = 30.0
DEFAULT_MAX_OUTPUT_BYTES = 8_000_000


@dataclass(frozen=True)
class ImportPolicy:
    """Immutable, versioned policy controlling one import.

    The policy version participates in canonical determinism: equal input
    bytes, parser version, policy version, lane, and revision policy produce
    byte-identical canonical JSON.
    """

    version: str = POLICY_VERSION
    lane: str = "source"
    max_bytes: int = DEFAULT_MAX_BYTES
    max_expanded_bytes: int = DEFAULT_MAX_EXPANDED_BYTES
    max_nodes: int = DEFAULT_MAX_NODES
    max_depth: int = DEFAULT_MAX_DEPTH
    timeout_seconds: float = DEFAULT_TIMEOUT_SECONDS
    max_output_bytes: int = DEFAULT_MAX_OUTPUT_BYTES
    required_encoding: str = "utf-8"
    network_policy: str = "deny"
    revision_policy: str = "review_required"
    retain_original: bool = False
    unicode: UnicodePolicy = field(default_factory=UnicodePolicy)


def validate_policy(policy: ImportPolicy) -> None:
    """Validate a policy and raise DomainError on any unsupported value."""
    if policy.lane not in LANES:
        raise DomainError(f"Unknown import lane: {policy.lane}")
    if policy.network_policy not in NETWORK_POLICIES:
        raise DomainError(
            f"Unsupported network policy: {policy.network_policy} "
            f"(only {NETWORK_POLICIES!r} is implemented)"
        )
    if policy.revision_policy not in REVISION_POLICIES:
        raise DomainError(
            f"Unsupported revision policy: {policy.revision_policy} "
            f"(only {REVISION_POLICIES!r} is implemented)"
        )
    if policy.required_encoding not in {"utf-8", "ascii"}:
        raise DomainError(
            f"Unsupported required encoding: {policy.required_encoding} "
            "(only utf-8 and ascii are implemented)"
        )
    for name, value in (
        ("max_bytes", policy.max_bytes),
        ("max_expanded_bytes", policy.max_expanded_bytes),
        ("max_nodes", policy.max_nodes),
        ("max_depth", policy.max_depth),
        ("max_output_bytes", policy.max_output_bytes),
    ):
        if value <= 0:
            raise DomainError(f"{name} must be a positive integer")
    if policy.timeout_seconds <= 0:
        raise DomainError("timeout_seconds must be positive")
    if policy.max_expanded_bytes < policy.max_bytes:
        raise DomainError("max_expanded_bytes must be >= max_bytes")


def check_limits(
    policy: ImportPolicy,
    *,
    size_bytes: int,
    expanded_bytes: int,
    node_count: int,
    depth: int,
) -> tuple[ImportFinding, ...]:
    """Check measured resources against policy limits and return findings."""
    findings: list[ImportFinding] = []
    if size_bytes > policy.max_bytes:
        findings.append(
            ImportFinding(
                code=FindingCode.LIMIT_BYTES,
                severity=FindingSeverity.ERROR,
                category=FindingCategory.RESOURCE_LIMIT,
                description=(f"File size {size_bytes} bytes exceeds limit {policy.max_bytes}"),
                evidence=f"size={size_bytes} limit={policy.max_bytes}",
            )
        )
    if expanded_bytes > policy.max_expanded_bytes:
        findings.append(
            ImportFinding(
                code=FindingCode.LIMIT_EXPANDED_BYTES,
                severity=FindingSeverity.ERROR,
                category=FindingCategory.RESOURCE_LIMIT,
                description=(
                    f"Expanded size {expanded_bytes} bytes exceeds limit "
                    f"{policy.max_expanded_bytes}"
                ),
                evidence=f"expanded={expanded_bytes} limit={policy.max_expanded_bytes}",
            )
        )
    if node_count > policy.max_nodes:
        findings.append(
            ImportFinding(
                code=FindingCode.LIMIT_NODES,
                severity=FindingSeverity.ERROR,
                category=FindingCategory.RESOURCE_LIMIT,
                description=f"Node count {node_count} exceeds limit {policy.max_nodes}",
                evidence=f"nodes={node_count} limit={policy.max_nodes}",
            )
        )
    if depth > policy.max_depth:
        findings.append(
            ImportFinding(
                code=FindingCode.LIMIT_DEPTH,
                severity=FindingSeverity.ERROR,
                category=FindingCategory.RESOURCE_LIMIT,
                description=f"Tree depth {depth} exceeds limit {policy.max_depth}",
                evidence=f"depth={depth} limit={policy.max_depth}",
            )
        )
    return tuple(findings)
