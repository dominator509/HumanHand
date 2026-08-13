"""E2E tests for the `humanhand privacy` commands (EP-016).

The orchestrator registers ``privacy_app`` into ``humanhand.cli.app`` at
merge time; these tests compose a local root app the same way so they run
standalone and exercise the real command functions.

The parallel EP-016 ``humanhand.domain.privacy`` module is merged in
parallel and may be absent while this file is being merged. Tests that
require it skip with an honest reason; ``privacy validate-project`` is a
pure filesystem inspection and runs without any parallel module, and the
fail-closed paths run today.
"""

from __future__ import annotations

import importlib.util
import json
from pathlib import Path
from typing import Any

import pytest
import typer
from typer.testing import CliRunner

from humanhand.cli.privacy_commands import privacy_app
from humanhand.infra.config import load_config

cli_app = typer.Typer()
cli_app.add_typer(privacy_app, name="privacy")

runner = CliRunner()

HAS_PRIVACY_DOMAIN = importlib.util.find_spec("humanhand.domain.privacy") is not None

NEED_PRIVACY_DOMAIN = pytest.mark.skipif(
    not HAS_PRIVACY_DOMAIN,
    reason="parallel EP-016 module humanhand.domain.privacy not merged",
)

ONLY_WITHOUT_PRIVACY = pytest.mark.skipif(
    HAS_PRIVACY_DOMAIN,
    reason="parallel EP-016 privacy module present; the fail-closed path is no longer reachable",
)


def _invoke(*args: str) -> Any:
    return runner.invoke(cli_app, ["privacy", *args])


def _aligned_cache_env(monkeypatch: pytest.MonkeyPatch) -> None:
    """Align HUMANHAND_CACHE_ENABLED with the real policy for the active mode.

    The doctor compares config cache_enabled against the policy's
    detector_cache_enabled; this reads the real policy (loaded through
    importlib so mypy does not chase an absent module) and sets the env var
    so a clean setup reports no mismatch.
    """
    privacy: Any = importlib.import_module("humanhand.domain.privacy")
    config = load_config()
    policy = privacy.load_privacy_policy(config.privacy_mode)
    monkeypatch.setenv(
        "HUMANHAND_CACHE_ENABLED", "true" if policy.detector_cache_enabled else "false"
    )


def _hermetic_doctor_env(monkeypatch: pytest.MonkeyPatch, tmp_path: Path) -> None:
    """Remove project-dir coupling and point the style vault at tmp_path.

    HUMANHAND_PROJECT_DIR is deleted so the repo root cannot be mistaken
    for a project; the vault dir is set to a fresh tmp path.
    """
    monkeypatch.delenv("HUMANHAND_PRIVACY_MODE", raising=False)
    monkeypatch.delenv("HUMANHAND_PROJECT_DIR", raising=False)
    monkeypatch.setenv("HUMANHAND_STYLE_VAULT_DIR", str(tmp_path / "style-vault"))


def _init_project_files(root: Path) -> None:
    """Write the documented layout (blueprint 9.3) by hand.

    .humanhand/project.toml, .humanhand/project.db, and the five layout
    directories. Mirrors what `project init` produces so validate-project
    reports ok.
    """
    (root / ".humanhand").mkdir(parents=True)
    (root / ".humanhand" / "project.toml").write_text(
        'name = "Demo"\nschema_version = 1\n', encoding="utf-8"
    )
    (root / ".humanhand" / "project.db").touch()
    for name in ("source", "style", "working", "exports"):
        (root / name).mkdir()


class TestPrivacyShow:
    @NEED_PRIVACY_DOMAIN
    def test_show_json_has_policy_fields(self, monkeypatch: pytest.MonkeyPatch) -> None:
        monkeypatch.delenv("HUMANHAND_PRIVACY_MODE", raising=False)
        result = _invoke("show", "--json")
        assert result.exit_code == 0, result.stderr
        data = json.loads(result.stdout)
        assert data["status"] == "ok"
        # The mode is one of the three documented privacy modes and the
        # booleans come from the real PrivacyPolicy object.
        assert data["mode"] in {"strict_local", "private_audited", "regulated"}
        assert isinstance(data["network_allowed"], bool)
        assert isinstance(data["detector_cache_enabled"], bool)

    @NEED_PRIVACY_DOMAIN
    def test_show_strict_local_denies_network(self, monkeypatch: pytest.MonkeyPatch) -> None:
        # SPEC-013: strict-local mode denies network use.
        monkeypatch.setenv("HUMANHAND_PRIVACY_MODE", "strict_local")
        result = _invoke("show", "--json")
        assert result.exit_code == 0, result.stderr
        data = json.loads(result.stdout)
        assert data["status"] == "ok"
        assert data["mode"] == "strict_local"
        assert data["network_allowed"] is False


class TestPrivacyDoctor:
    @NEED_PRIVACY_DOMAIN
    def test_doctor_clean_setup_reports_ok(
        self, tmp_path: Path, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        _hermetic_doctor_env(monkeypatch, tmp_path)
        _aligned_cache_env(monkeypatch)
        result = _invoke("doctor", "--json")
        assert result.exit_code == 0, result.stderr
        data = json.loads(result.stdout)
        assert data["status"] == "ok"
        assert data["findings"] == []

    @NEED_PRIVACY_DOMAIN
    def test_doctor_strict_local_style_vault_finding(
        self, tmp_path: Path, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        # strict_local retains no raw evidence; a style vault holding
        # decisions.jsonl is a finding, not an error.
        monkeypatch.setenv("HUMANHAND_PRIVACY_MODE", "strict_local")
        monkeypatch.delenv("HUMANHAND_PROJECT_DIR", raising=False)
        vault = tmp_path / "style-vault"
        monkeypatch.setenv("HUMANHAND_STYLE_VAULT_DIR", str(vault))
        _aligned_cache_env(monkeypatch)
        vault.mkdir()
        (vault / "decisions.jsonl").write_text('{"decision": "accepted"}\n', encoding="utf-8")
        result = _invoke("doctor", "--json")
        assert result.exit_code == 0, result.stderr
        data = json.loads(result.stdout)
        assert data["status"] == "findings"
        codes = {finding["code"] for finding in data["findings"]}
        assert "privacy.strict_local_style_vault" in codes

    def test_doctor_invalid_mode_is_config_error(
        self, tmp_path: Path, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        # An unknown privacy mode fails closed at config load (exit 2)
        # before any policy module is needed.
        monkeypatch.setenv("HUMANHAND_PRIVACY_MODE", "bogus")
        result = _invoke("doctor", "--json")
        assert result.exit_code == 2, result.stderr
        data = json.loads(result.stdout)
        assert data["status"] == "error"
        assert data["exit_code"] == 2

    @ONLY_WITHOUT_PRIVACY
    def test_doctor_fails_closed_without_privacy_module(
        self, tmp_path: Path, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        # The cache env must NOT be aligned via the real policy here: the
        # module under test is absent, so the command exits at the module
        # load before any cache check runs.
        _hermetic_doctor_env(monkeypatch, tmp_path)
        result = _invoke("doctor", "--json")
        assert result.exit_code == 2, result.stderr
        data = json.loads(result.stdout)
        assert data["status"] == "error"
        assert "not available" in data["message"]

    @ONLY_WITHOUT_PRIVACY
    def test_show_fails_closed_without_privacy_module(
        self, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        monkeypatch.delenv("HUMANHAND_PRIVACY_MODE", raising=False)
        result = _invoke("show", "--json")
        assert result.exit_code == 2, result.stderr
        data = json.loads(result.stdout)
        assert data["status"] == "error"
        assert "not available" in data["message"]


class TestPrivacyValidateProject:
    def test_initialized_project_is_ok(self, tmp_path: Path) -> None:
        proj = tmp_path / "proj"
        _init_project_files(proj)
        result = _invoke("validate-project", str(proj), "--json")
        assert result.exit_code == 0, result.stderr
        data = json.loads(result.stdout)
        assert data["status"] == "ok"
        assert data["root"] == str(proj)
        assert data["findings"] == []

    def test_bare_directory_has_findings(self, tmp_path: Path) -> None:
        # An uninitialized directory reports both missing-layout findings
        # but still exits 0 (findings are advisory).
        proj = tmp_path / "bare"
        proj.mkdir()
        result = _invoke("validate-project", str(proj), "--json")
        assert result.exit_code == 0, result.stderr
        data = json.loads(result.stdout)
        assert data["status"] == "findings"
        codes = {finding["code"] for finding in data["findings"]}
        assert "privacy.project_missing_project_toml" in codes
        assert "privacy.project_missing_database" in codes

    def test_unexpected_top_level_entry_is_finding(self, tmp_path: Path) -> None:
        proj = tmp_path / "proj"
        _init_project_files(proj)
        (proj / "notes.txt").write_text("not a humanhand file\n", encoding="utf-8")
        result = _invoke("validate-project", str(proj), "--json")
        assert result.exit_code == 0, result.stderr
        data = json.loads(result.stdout)
        assert data["status"] == "findings"
        codes = {finding["code"] for finding in data["findings"]}
        assert "privacy.project_unexpected_entry" in codes

    def test_missing_directory_is_input_error(self, tmp_path: Path) -> None:
        result = _invoke("validate-project", str(tmp_path / "missing"), "--json")
        assert result.exit_code == 1, result.stderr
        data = json.loads(result.stdout)
        assert data["status"] == "error"
        assert data["exit_code"] == 1
