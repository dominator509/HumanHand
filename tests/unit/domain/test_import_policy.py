"""Unit tests for import policy defaults, validation, and limit checks."""

from __future__ import annotations

import pytest

from humanhand.domain.import_findings import FindingCode, FindingSeverity
from humanhand.domain.import_policy import ImportPolicy, check_limits, validate_policy
from humanhand.domain.types import DomainError


class TestImportPolicyDefaults:
    def test_defaults(self) -> None:
        policy = ImportPolicy()
        assert policy.version == "1"
        assert policy.lane == "source"
        assert policy.max_bytes == 4_000_000
        assert policy.max_expanded_bytes == 16_000_000
        assert policy.max_nodes == 50_000
        assert policy.network_policy == "deny"
        assert policy.revision_policy == "review_required"
        assert policy.required_encoding == "utf-8"
        assert policy.retain_original is False

    def test_style_lane_is_a_plain_value(self) -> None:
        policy = ImportPolicy(lane="style")
        validate_policy(policy)
        assert policy.lane == "style"


class TestValidatePolicy:
    def test_valid_policy_passes(self) -> None:
        validate_policy(ImportPolicy())

    def test_rejects_unknown_lane(self) -> None:
        with pytest.raises(DomainError, match="lane"):
            validate_policy(ImportPolicy(lane="project"))

    def test_rejects_network_policy_other_than_deny(self) -> None:
        with pytest.raises(DomainError, match="network"):
            validate_policy(ImportPolicy(network_policy="allow"))

    def test_rejects_unknown_revision_policy(self) -> None:
        with pytest.raises(DomainError, match="revision"):
            validate_policy(ImportPolicy(revision_policy="auto"))

    def test_rejects_unknown_encoding(self) -> None:
        with pytest.raises(DomainError, match="encoding"):
            validate_policy(ImportPolicy(required_encoding="latin-1"))

    def test_accepts_ascii_encoding(self) -> None:
        validate_policy(ImportPolicy(required_encoding="ascii"))

    @pytest.mark.parametrize(
        "policy",
        [
            ImportPolicy(max_bytes=0),
            ImportPolicy(max_expanded_bytes=-1),
            ImportPolicy(max_nodes=0),
            ImportPolicy(max_depth=-5),
            ImportPolicy(max_output_bytes=0),
        ],
    )
    def test_rejects_nonpositive_limits(self, policy: ImportPolicy) -> None:
        with pytest.raises(DomainError, match="positive"):
            validate_policy(policy)

    def test_rejects_nonpositive_timeout(self) -> None:
        with pytest.raises(DomainError, match="timeout"):
            validate_policy(ImportPolicy(timeout_seconds=0.0))

    def test_rejects_expanded_smaller_than_bytes(self) -> None:
        with pytest.raises(DomainError, match="expanded"):
            validate_policy(ImportPolicy(max_bytes=1000, max_expanded_bytes=999))


class TestCheckLimits:
    def _policy(self) -> ImportPolicy:
        return ImportPolicy(
            max_bytes=100,
            max_expanded_bytes=200,
            max_nodes=10,
            max_depth=4,
            timeout_seconds=1.0,
        )

    def test_within_limits_yields_nothing(self) -> None:
        assert (
            check_limits(
                self._policy(),
                size_bytes=100,
                expanded_bytes=200,
                node_count=10,
                depth=4,
            )
            == ()
        )

    def test_size_exceeded(self) -> None:
        findings = check_limits(
            self._policy(), size_bytes=101, expanded_bytes=200, node_count=10, depth=4
        )
        assert [finding.code for finding in findings] == [FindingCode.LIMIT_BYTES]
        assert findings[0].severity is FindingSeverity.ERROR

    def test_expanded_exceeded(self) -> None:
        findings = check_limits(
            self._policy(), size_bytes=100, expanded_bytes=201, node_count=10, depth=4
        )
        assert [finding.code for finding in findings] == [FindingCode.LIMIT_EXPANDED_BYTES]

    def test_nodes_exceeded(self) -> None:
        findings = check_limits(
            self._policy(), size_bytes=100, expanded_bytes=200, node_count=11, depth=4
        )
        assert [finding.code for finding in findings] == [FindingCode.LIMIT_NODES]

    def test_depth_exceeded(self) -> None:
        findings = check_limits(
            self._policy(), size_bytes=100, expanded_bytes=200, node_count=10, depth=5
        )
        assert [finding.code for finding in findings] == [FindingCode.LIMIT_DEPTH]

    def test_multiple_breaches_reported_together(self) -> None:
        findings = check_limits(
            self._policy(), size_bytes=101, expanded_bytes=201, node_count=11, depth=5
        )
        assert {finding.code for finding in findings} == {
            FindingCode.LIMIT_BYTES,
            FindingCode.LIMIT_EXPANDED_BYTES,
            FindingCode.LIMIT_NODES,
            FindingCode.LIMIT_DEPTH,
        }
