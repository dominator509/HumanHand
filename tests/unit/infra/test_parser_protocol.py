"""Unit tests for the parser worker environment and policy contract."""

from __future__ import annotations

import dataclasses
import sys
import types
from collections.abc import Callable

import pytest

from humanhand.domain.import_policy import ImportPolicy
from humanhand.domain.unicode_policy import UnicodePolicy
from humanhand.infra.sandbox.parser_protocol import (
    install_network_guard,
    policy_from_dict,
    verify_worker_environment,
)


class TestPolicyFromDict:
    def test_round_trip(self) -> None:
        policy = ImportPolicy(
            lane="style",
            max_bytes=100_000,
            timeout_seconds=12.5,
            unicode=UnicodePolicy(allow_bom=True, reject_control_chars=True),
        )
        rebuilt = policy_from_dict(dataclasses.asdict(policy))
        assert rebuilt == policy

    def test_partial_dict_uses_defaults(self) -> None:
        rebuilt = policy_from_dict({"lane": "source"})
        assert rebuilt == ImportPolicy()

    def test_unknown_key_rejected(self) -> None:
        with pytest.raises(ValueError, match="Unknown policy fields"):
            policy_from_dict({"lane": "source", "bogus": 1})

    def test_bad_lane_rejected(self) -> None:
        with pytest.raises(ValueError, match="lane"):
            policy_from_dict({"lane": "not-a-lane"})


class TestVerifyWorkerEnvironment:
    def test_reports_injected_forbidden_modules(self, monkeypatch: pytest.MonkeyPatch) -> None:
        fake_openai = types.ModuleType("openai.evil")
        fake_http = types.ModuleType("humanhand.infra.http.fake")
        monkeypatch.setitem(sys.modules, "openai.evil", fake_openai)
        monkeypatch.setitem(sys.modules, "humanhand.infra.http.fake", fake_http)
        result = verify_worker_environment()
        assert "openai.evil" in result
        assert "humanhand.infra.http.fake" in result
        assert result == sorted(result)
        monkeypatch.delitem(sys.modules, "openai.evil")
        result_after = verify_worker_environment()
        assert "openai.evil" not in result_after
        assert "humanhand.infra.http.fake" in result_after

    def test_non_forbidden_module_not_reported(self, monkeypatch: pytest.MonkeyPatch) -> None:
        fake = types.ModuleType("humanhand.infra.files.fake")
        monkeypatch.setitem(sys.modules, "humanhand.infra.files.fake", fake)
        assert "humanhand.infra.files.fake" not in verify_worker_environment()


class TestNetworkGuard:
    def test_rejects_socket_audit_events(self, monkeypatch: pytest.MonkeyPatch) -> None:
        hooks: list[Callable[[str, tuple[object, ...]], None]] = []

        def capture_hook(hook: Callable[[str, tuple[object, ...]], None]) -> None:
            hooks.append(hook)

        monkeypatch.setattr(sys, "addaudithook", capture_hook)
        install_network_guard()

        assert len(hooks) == 1
        with pytest.raises(PermissionError, match="network access is denied"):
            hooks[0]("socket.connect", ())
        hooks[0]("open", ())
