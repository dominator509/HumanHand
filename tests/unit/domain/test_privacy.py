"""Unit tests for privacy modes, policies, and retention scanning."""

from __future__ import annotations

import os
import time
from pathlib import Path

import pytest

from humanhand.domain.privacy import (
    PrivacyMode,
    load_privacy_policy,
    policy_from_payload,
    policy_to_payload,
    validate_cache_use,
    validate_network_use,
)
from humanhand.domain.retention import (
    RETENTION_SCOPES,
    RetentionFinding,
    RetentionPolicy,
    retention_policy_for,
    retention_to_payload,
    scan_retention,
)
from humanhand.domain.types import DomainError

ALL_MODES = (
    PrivacyMode.STRICT_LOCAL,
    PrivacyMode.PRIVATE_AUDITED,
    PrivacyMode.REGULATED,
)


class TestLoadPrivacyPolicy:
    def test_every_mode_loads_from_bundled_resource(self) -> None:
        for mode in ALL_MODES:
            policy = load_privacy_policy(mode)
            assert policy.mode is mode

    def test_accepts_raw_mode_name_strings(self) -> None:
        assert load_privacy_policy("strict_local").mode is PrivacyMode.STRICT_LOCAL

    def test_forced_invariants_for_all_modes(self) -> None:
        for mode in ALL_MODES:
            policy = load_privacy_policy(mode)
            assert policy.raw_text_logging is False
            assert policy.obsidian_projection_auto is False

    def test_unknown_mode_raises_value_error(self) -> None:
        with pytest.raises(ValueError, match="Unknown privacy mode"):
            load_privacy_policy("not_a_mode")

    def test_mode_specific_flags_reflect_resource(self) -> None:
        strict = load_privacy_policy(PrivacyMode.STRICT_LOCAL)
        assert strict.network_allowed is False
        assert strict.detector_cache_enabled is False
        assert strict.retention_enforced is True
        assert strict.encrypt_sensitive_fields is True
        audited = load_privacy_policy(PrivacyMode.PRIVATE_AUDITED)
        assert audited.network_allowed is True
        assert audited.detector_cache_enabled is True
        assert audited.retention_enforced is False
        assert audited.encrypt_sensitive_fields is False
        regulated = load_privacy_policy(PrivacyMode.REGULATED)
        assert regulated.network_allowed is True
        assert regulated.detector_cache_enabled is False
        assert regulated.retention_enforced is True
        assert regulated.encrypt_sensitive_fields is True


class TestValidateUse:
    def test_network_use_forbidden_in_strict_local(self) -> None:
        policy = load_privacy_policy(PrivacyMode.STRICT_LOCAL)
        assert validate_network_use(policy, would_use_network=True) == ("network_use_forbidden",)
        assert validate_network_use(policy, would_use_network=False) == ()

    def test_network_use_allowed_where_permitted(self) -> None:
        policy = load_privacy_policy(PrivacyMode.PRIVATE_AUDITED)
        assert validate_network_use(policy, would_use_network=True) == ()

    def test_cache_use_forbidden_when_disabled(self) -> None:
        strict = load_privacy_policy(PrivacyMode.STRICT_LOCAL)
        assert validate_cache_use(strict, cache_would_be_used=True) == ("cache_use_forbidden",)
        audited = load_privacy_policy(PrivacyMode.PRIVATE_AUDITED)
        assert validate_cache_use(audited, cache_would_be_used=True) == ()
        assert validate_cache_use(audited, cache_would_be_used=False) == ()


class TestPolicyPayload:
    def test_round_trip_all_modes(self) -> None:
        for mode in ALL_MODES:
            policy = load_privacy_policy(mode)
            assert policy_from_payload(policy_to_payload(policy)) == policy

    def test_payload_shape(self) -> None:
        payload = policy_to_payload(load_privacy_policy(PrivacyMode.STRICT_LOCAL))
        assert payload["schema"] == "privacy-policy"
        assert payload["schema_version"] == 1
        assert payload["mode"] == "strict_local"
        assert payload["network_allowed"] is False
        assert payload["raw_text_logging"] is False
        assert payload["obsidian_projection_auto"] is False

    def test_strict_from_payload_rejects_unknown_mode(self) -> None:
        payload = policy_to_payload(load_privacy_policy(PrivacyMode.STRICT_LOCAL))
        bad: dict[str, object] = dict(payload)
        bad["mode"] = "bogus"
        with pytest.raises(DomainError, match="unknown mode"):
            policy_from_payload(bad)

    def test_strict_from_payload_rejects_non_boolean_flag(self) -> None:
        payload = policy_to_payload(load_privacy_policy(PrivacyMode.STRICT_LOCAL))
        bad: dict[str, object] = dict(payload)
        bad["network_allowed"] = "yes"
        with pytest.raises(DomainError, match="network_allowed"):
            policy_from_payload(bad)

    def test_strict_from_payload_rejects_invariant_violations(self) -> None:
        payload = policy_to_payload(load_privacy_policy(PrivacyMode.STRICT_LOCAL))
        bad_logging: dict[str, object] = dict(payload)
        bad_logging["raw_text_logging"] = True
        with pytest.raises(DomainError, match="raw_text_logging"):
            policy_from_payload(bad_logging)
        bad_projection: dict[str, object] = dict(payload)
        bad_projection["obsidian_projection_auto"] = True
        with pytest.raises(DomainError, match="obsidian_projection_auto"):
            policy_from_payload(bad_projection)


class TestRetentionMapping:
    def test_enabled_follows_privacy_policy(self) -> None:
        assert retention_policy_for(load_privacy_policy(PrivacyMode.STRICT_LOCAL)).enabled is True
        assert (
            retention_policy_for(load_privacy_policy(PrivacyMode.PRIVATE_AUDITED)).enabled is False
        )
        assert retention_policy_for(load_privacy_policy(PrivacyMode.REGULATED)).enabled is True

    def test_defaults_and_only_scopes(self) -> None:
        policy = retention_policy_for(load_privacy_policy(PrivacyMode.STRICT_LOCAL))
        assert policy.max_age_days == 30
        assert policy.scopes == RETENTION_SCOPES

    def test_retention_to_payload(self) -> None:
        payload = retention_to_payload(
            retention_policy_for(load_privacy_policy(PrivacyMode.STRICT_LOCAL))
        )
        assert payload["schema"] == "retention-policy"
        assert payload["schema_version"] == 1
        assert payload["enabled"] is True
        assert payload["max_age_days"] == 30
        assert payload["scopes"] == ["cache", "reports"]

    def test_retention_to_payload_rejects_other_scopes(self) -> None:
        with pytest.raises(DomainError, match="scopes"):
            retention_to_payload(RetentionPolicy(enabled=True, scopes=("cache",)))


class TestScanRetention:
    def test_only_old_files_are_flagged(self, tmp_path: Path) -> None:
        old_path = tmp_path / "old.txt"
        fresh_path = tmp_path / "fresh.txt"
        old_path.write_text("old bytes", encoding="utf-8")
        fresh_path.write_text("fresh bytes", encoding="utf-8")
        now = time.time()
        os.utime(old_path, (now, now - 40 * 86400))
        os.utime(fresh_path, (now, now - 5 * 86400))
        findings = scan_retention(str(tmp_path), RetentionPolicy(enabled=True, max_age_days=30))
        assert findings == (RetentionFinding(path="old.txt", age_days=40, action="expired"),)

    def test_findings_sorted_by_path(self, tmp_path: Path) -> None:
        now = time.time()
        for name in ("b.txt", "a.txt", "c.txt"):
            path = tmp_path / name
            path.write_text(name, encoding="utf-8")
            os.utime(path, (now, now - 60 * 86400))
        findings = scan_retention(str(tmp_path), RetentionPolicy(enabled=True, max_age_days=30))
        assert [finding.path for finding in findings] == ["a.txt", "b.txt", "c.txt"]
        assert all(finding.action == "expired" for finding in findings)

    def test_scan_is_read_only(self, tmp_path: Path) -> None:
        old_path = tmp_path / "old.txt"
        content = b"read-only bytes\n"
        old_path.write_bytes(content)
        now = time.time()
        os.utime(old_path, (now, now - 40 * 86400))
        before = old_path.read_bytes()
        findings = scan_retention(str(tmp_path), RetentionPolicy(enabled=True, max_age_days=30))
        after = old_path.read_bytes()
        assert findings
        assert before == content
        assert after == content
        assert old_path.exists()

    def test_disabled_policy_scans_nothing(self, tmp_path: Path) -> None:
        path = tmp_path / "old.txt"
        path.write_text("x", encoding="utf-8")
        now = time.time()
        os.utime(path, (now, now - 40 * 86400))
        findings = scan_retention(str(tmp_path), RetentionPolicy(enabled=False, max_age_days=30))
        assert findings == ()

    def test_only_regular_files_are_scanned(self, tmp_path: Path) -> None:
        subdir = tmp_path / "subdir"
        subdir.mkdir()
        now = time.time()
        os.utime(subdir, (now, now - 90 * 86400))
        findings = scan_retention(str(tmp_path), RetentionPolicy(enabled=True, max_age_days=30))
        assert findings == ()

    def test_missing_directory_fails_closed(self, tmp_path: Path) -> None:
        with pytest.raises(DomainError, match="scan"):
            scan_retention(str(tmp_path / "missing"), RetentionPolicy(enabled=True))
