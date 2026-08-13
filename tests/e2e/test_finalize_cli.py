"""E2E tests for the `humanhand finalize lexical` command (EP-017).

The orchestrator registers ``finalize_app`` into ``humanhand.cli.app`` at
merge time; these tests compose a local root app the same way so they run
standalone and exercise the real command functions.

Parallel EP-017 modules (``domain.lexical_types``,
``domain.lexical_normalizer``, the EP-015 project store stack) are merged
in parallel and may be absent while this file is being merged. Tests that
require them skip with an honest reason; everything that runs today (error
paths, JSON purity, fail-closed behavior) runs now.
"""

from __future__ import annotations

import importlib.util
import json
from pathlib import Path
from typing import Any

import pytest
import typer
from typer.testing import CliRunner

from humanhand.cli.finalization_commands import finalize_app
from humanhand.cli.project_commands import project_app

cli_app = typer.Typer()
cli_app.add_typer(project_app, name="project")
cli_app.add_typer(finalize_app, name="finalize")

runner = CliRunner()

HAS_LEXICAL_TYPES = importlib.util.find_spec("humanhand.domain.lexical_types") is not None
HAS_LEXICAL_NORMALIZER = importlib.util.find_spec("humanhand.domain.lexical_normalizer") is not None
HAS_PROJECT_LAYOUT = importlib.util.find_spec("humanhand.infra.stores.project_layout") is not None
HAS_PROJECT_STORE = importlib.util.find_spec("humanhand.infra.stores.project_store") is not None
HAS_DOMAIN_PROJECT = importlib.util.find_spec("humanhand.domain.project") is not None
HAS_PARALLEL_FINALIZE = (
    HAS_LEXICAL_TYPES
    and HAS_LEXICAL_NORMALIZER
    and HAS_PROJECT_LAYOUT
    and HAS_PROJECT_STORE
    and HAS_DOMAIN_PROJECT
)

NEED_PARALLEL = pytest.mark.skipif(
    not HAS_PARALLEL_FINALIZE,
    reason="parallel EP-017 modules (lexical_types, lexical_normalizer, EP-015 store) not merged",
)

ONLY_WITHOUT_PARALLEL = pytest.mark.skipif(
    HAS_PARALLEL_FINALIZE,
    reason="parallel EP-017 modules present; the fail-closed path is no longer reachable",
)


def _init_project(proj: Path) -> None:
    """Initialize a real EP-015 project layout via the project CLI."""
    result = runner.invoke(cli_app, ["project", "init", str(proj), "--name", "Demo", "--json"])
    assert result.exit_code == 0, result.stderr


def _invoke(*args: str) -> Any:
    return runner.invoke(cli_app, ["finalize", *args])


class TestErrorPaths:
    @pytest.mark.importers
    def test_lexical_missing_text_file_is_input_error(self, tmp_path: Path) -> None:
        # EP-017 deviation: --text-file replaces the store document id. A
        # missing text file is an input error (exit 1) and the real
        # exception text (including the path) is surfaced. The project
        # checks run first, so the project must be initialized for the
        # flow to reach the text-file read.
        proj = tmp_path / "proj"
        _init_project(proj)
        result = _invoke(
            "lexical",
            "--project",
            str(proj),
            "--text-file",
            str(proj / "missing.txt"),
            "--json",
        )
        assert result.exit_code == 1, result.stderr
        data = json.loads(result.stdout)
        assert data["status"] == "error"
        assert data["exit_code"] == 1
        assert "missing.txt" in data["message"]

    @pytest.mark.importers
    def test_lexical_missing_project_dir_is_input_error(self, tmp_path: Path) -> None:
        result = _invoke(
            "lexical",
            "--project",
            str(tmp_path / "missing"),
            "--text-file",
            str(tmp_path / "doc.txt"),
            "--json",
        )
        assert result.exit_code == 1, result.stderr
        data = json.loads(result.stdout)
        assert data["status"] == "error"
        assert data["exit_code"] == 1

    @pytest.mark.importers
    def test_lexical_uninitialized_project_is_input_error(self, tmp_path: Path) -> None:
        # Existing directory without .humanhand/project.toml (blueprint 9.3).
        result = _invoke(
            "lexical",
            "--project",
            str(tmp_path),
            "--text-file",
            str(tmp_path / "doc.txt"),
            "--json",
        )
        assert result.exit_code == 1, result.stderr
        data = json.loads(result.stdout)
        assert data["status"] == "error"
        assert "not initialized" in data["message"]

    @pytest.mark.importers
    def test_lexical_flag_beats_env_var(
        self, tmp_path: Path, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        # Resolution order: --project > HUMANHAND_PROJECT_DIR > ".".
        env_dir = tmp_path / "from-env"
        flag_dir = tmp_path / "from-flag"
        monkeypatch.setenv("HUMANHAND_PROJECT_DIR", str(env_dir))
        result = _invoke(
            "lexical",
            "--project",
            str(flag_dir),
            "--text-file",
            str(tmp_path / "doc.txt"),
            "--json",
        )
        assert result.exit_code == 1, result.stderr
        data = json.loads(result.stdout)
        assert str(flag_dir) in data["message"]

    @pytest.mark.importers
    def test_lexical_json_stdout_is_pure_on_error(self, tmp_path: Path) -> None:
        # The entire stdout is exactly one JSON document on error paths.
        result = _invoke(
            "lexical",
            "--project",
            str(tmp_path / "missing"),
            "--text-file",
            str(tmp_path / "doc.txt"),
            "--json",
        )
        assert result.exit_code == 1
        json.loads(result.stdout)


class TestFailClosedWithoutParallelModules:
    @pytest.mark.importers
    @ONLY_WITHOUT_PARALLEL
    def test_lexical_fails_closed_when_lexical_modules_absent(self, tmp_path: Path) -> None:
        # The text-file and project checks pass first; the command then
        # fails closed with an honest missing-module error (exit 2). No
        # stub or fake proposal is ever produced.
        proj = tmp_path / "proj"
        _init_project(proj)
        doc = tmp_path / "doc.txt"
        doc.write_text("The team will utilize the new tool.", encoding="utf-8")
        result = _invoke("lexical", "--project", str(proj), "--text-file", str(doc), "--json")
        assert result.exit_code == 2, result.stderr
        data = json.loads(result.stdout)
        assert data["status"] == "error"
        assert "not available" in data["message"]
        assert "lexical" in data["message"]


class TestLexicalLifecycle:
    @pytest.mark.importers
    @NEED_PARALLEL
    def test_lexical_run_produces_proposal(self, tmp_path: Path) -> None:
        # "utilize" is mapped by the bundled curated ruleset, so the real
        # normalizer must propose at least one deterministic change.
        proj = tmp_path / "proj"
        _init_project(proj)
        doc = tmp_path / "doc.txt"
        doc.write_text("The team will utilize the new tool.", encoding="utf-8")
        result = _invoke("lexical", "--project", str(proj), "--text-file", str(doc), "--json")
        assert result.exit_code == 0, result.stderr
        payload = json.loads(result.stdout)
        # SPEC-014 payload keys: schema_version, run_id, ruleset_hash,
        # ordered changes, review state, findings.
        assert payload["schema_version"] >= 1
        assert isinstance(payload["run_id"], str)
        assert payload["run_id"]
        assert isinstance(payload["ruleset_hash"], str)
        assert payload["ruleset_hash"]
        changes = payload["changes"]
        assert isinstance(changes, list)
        assert len(changes) >= 1
        assert "review" in payload
        assert "findings" in payload
        # The proposal file exists at the documented path
        # (.humanhand/reports/finalize/<run_id>.json) and matches the
        # printed payload exactly after a JSON round trip.
        proposal_file = proj / ".humanhand" / "reports" / "finalize" / f"{payload['run_id']}.json"
        assert proposal_file.is_file()
        assert json.loads(proposal_file.read_text(encoding="utf-8")) == payload

    @pytest.mark.importers
    @NEED_PARALLEL
    def test_lexical_run_is_deterministic(self, tmp_path: Path) -> None:
        # Same input, same project state -> identical run_id and identical
        # payload (SPEC-014 determinism).
        proj = tmp_path / "proj"
        _init_project(proj)
        doc = tmp_path / "doc.txt"
        doc.write_text("The team will utilize the new tool.", encoding="utf-8")
        first = _invoke("lexical", "--project", str(proj), "--text-file", str(doc), "--json")
        second = _invoke("lexical", "--project", str(proj), "--text-file", str(doc), "--json")
        assert first.exit_code == 0, first.stderr
        assert second.exit_code == 0, second.stderr
        first_payload = json.loads(first.stdout)
        second_payload = json.loads(second.stdout)
        assert first_payload["run_id"] == second_payload["run_id"]
        assert first_payload == second_payload
        # Idempotent persistence: the second run rewrote the same file.
        proposal_file = (
            proj / ".humanhand" / "reports" / "finalize" / f"{first_payload['run_id']}.json"
        )
        assert json.loads(proposal_file.read_text(encoding="utf-8")) == first_payload

    @pytest.mark.importers
    @NEED_PARALLEL
    def test_lexical_unknown_tokens_produce_no_changes(self, tmp_path: Path) -> None:
        # A text of only unknown tokens must yield an empty ordered changes
        # list (conservative: no change when nothing maps).
        proj = tmp_path / "proj"
        _init_project(proj)
        doc = tmp_path / "doc.txt"
        doc.write_text("zxqvbn kwylpt mqwpr", encoding="utf-8")
        result = _invoke("lexical", "--project", str(proj), "--text-file", str(doc), "--json")
        assert result.exit_code == 0, result.stderr
        payload = json.loads(result.stdout)
        assert payload["changes"] == []

    @pytest.mark.importers
    @NEED_PARALLEL
    def test_lexical_json_stdout_is_pure_on_success(self, tmp_path: Path) -> None:
        # The entire stdout is exactly the proposal JSON document; no prose
        # is mixed in.
        proj = tmp_path / "proj"
        _init_project(proj)
        doc = tmp_path / "doc.txt"
        doc.write_text("The team will utilize the new tool.", encoding="utf-8")
        result = _invoke("lexical", "--project", str(proj), "--text-file", str(doc), "--json")
        assert result.exit_code == 0, result.stderr
        json.loads(result.stdout)

    @pytest.mark.importers
    @NEED_PARALLEL
    def test_lexical_text_mode_persists_proposal(self, tmp_path: Path) -> None:
        # Without --json the proposal is still persisted and a single
        # summary line is printed (no generated prose on stdout).
        proj = tmp_path / "proj"
        _init_project(proj)
        doc = tmp_path / "doc.txt"
        doc.write_text("The team will utilize the new tool.", encoding="utf-8")
        result = _invoke("lexical", "--project", str(proj), "--text-file", str(doc))
        assert result.exit_code == 0, result.stderr
        assert "Finalize proposal" in result.stdout
        # Text output is not JSON.
        with pytest.raises(json.JSONDecodeError):
            json.loads(result.stdout)
        # The proposal file still exists (one .json file, no journal yet).
        finalize_dir = proj / ".humanhand" / "reports" / "finalize"
        assert len(list(finalize_dir.glob("*.json"))) == 1
