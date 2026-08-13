"""E2E tests for the `humanhand finalize review/accept/reject` commands (EP-017).

The orchestrator registers ``finalize_app`` into ``humanhand.cli.app`` at
merge time; these tests compose a local root app the same way so they run
standalone and exercise the real command functions.

``finalize review`` reads persisted files only, so its error paths run
today. ``accept``/``reject`` load the parallel EP-017 module
``domain.lexical_review`` before validating the run; tests that require it
skip with an honest reason, and the fail-closed path (exit 2) is tested
while the module is absent.
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

HAS_LEXICAL_REVIEW = importlib.util.find_spec("humanhand.domain.lexical_review") is not None
HAS_LEXICAL_TYPES = importlib.util.find_spec("humanhand.domain.lexical_types") is not None
HAS_LEXICAL_NORMALIZER = importlib.util.find_spec("humanhand.domain.lexical_normalizer") is not None
HAS_PROJECT_LAYOUT = importlib.util.find_spec("humanhand.infra.stores.project_layout") is not None
HAS_PROJECT_STORE = importlib.util.find_spec("humanhand.infra.stores.project_store") is not None
HAS_DOMAIN_PROJECT = importlib.util.find_spec("humanhand.domain.project") is not None
HAS_REVIEW_MODULES = (
    HAS_LEXICAL_REVIEW
    and HAS_LEXICAL_TYPES
    and HAS_LEXICAL_NORMALIZER
    and HAS_PROJECT_LAYOUT
    and HAS_PROJECT_STORE
    and HAS_DOMAIN_PROJECT
)

NEED_REVIEW = pytest.mark.skipif(
    not HAS_REVIEW_MODULES,
    reason="parallel EP-017 modules (lexical_review, lexical_types, lexical_normalizer) not merged",
)

ONLY_WITHOUT_REVIEW = pytest.mark.skipif(
    HAS_REVIEW_MODULES,
    reason="parallel EP-017 review modules present; the fail-closed path is no longer reachable",
)


def _init_project(proj: Path) -> None:
    """Initialize a real EP-015 project layout via the project CLI."""
    result = runner.invoke(cli_app, ["project", "init", str(proj), "--name", "Demo", "--json"])
    assert result.exit_code == 0, result.stderr


def _invoke(*args: str) -> Any:
    return runner.invoke(cli_app, ["finalize", *args])


def _create_run(proj: Path, tmp_path: Path) -> tuple[str, str]:
    """Run a real lexical proposal and return (run_id, first change id)."""
    doc = tmp_path / "doc.txt"
    doc.write_text("The team will utilize the new tool.", encoding="utf-8")
    lexical = _invoke("lexical", "--project", str(proj), "--text-file", str(doc), "--json")
    assert lexical.exit_code == 0, lexical.stderr
    payload = json.loads(lexical.stdout)
    run_id: str = payload["run_id"]
    return run_id, _first_change_id(payload)


def _first_change_id(payload: dict[str, object]) -> str:
    """First change id from a proposal payload (``id`` key, else ``change_id``)."""
    changes = payload.get("changes")
    assert isinstance(changes, list) and changes
    first = changes[0]
    assert isinstance(first, dict)
    change_id = first.get("id")
    if not isinstance(change_id, str) or not change_id:
        change_id = first.get("change_id")
    assert isinstance(change_id, str) and change_id
    return change_id


class TestErrorPaths:
    @pytest.mark.importers
    def test_review_unknown_run_id_is_input_error(self, tmp_path: Path) -> None:
        # review reads persisted files only (no lexical domain call), so
        # this runs today: an unknown run id is an input error (exit 1).
        proj = tmp_path / "proj"
        _init_project(proj)
        result = _invoke("review", "--project", str(proj), "--run", "no-such-run", "--json")
        assert result.exit_code == 1, result.stderr
        data = json.loads(result.stdout)
        assert data["status"] == "error"
        assert data["exit_code"] == 1
        assert "Run not found" in data["message"]

    @pytest.mark.importers
    def test_review_json_stdout_is_pure_on_error(self, tmp_path: Path) -> None:
        # The entire stdout is exactly one JSON document on error paths.
        proj = tmp_path / "proj"
        _init_project(proj)
        result = _invoke("review", "--project", str(proj), "--run", "no-such-run", "--json")
        assert result.exit_code == 1
        json.loads(result.stdout)

    @pytest.mark.importers
    def test_review_env_var_resolves_project(
        self, tmp_path: Path, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        # HUMANHAND_PROJECT_DIR is used when --project is omitted; the
        # uninitialized-dir error names the env-resolved root.
        env_dir = tmp_path / "from-env"
        monkeypatch.setenv("HUMANHAND_PROJECT_DIR", str(env_dir))
        result = _invoke("review", "--run", "no-such-run", "--json")
        assert result.exit_code == 1, result.stderr
        data = json.loads(result.stdout)
        assert str(env_dir) in data["message"]


class TestFailClosedWithoutReviewModule:
    @pytest.mark.importers
    @ONLY_WITHOUT_REVIEW
    def test_accept_fails_closed_when_review_module_absent(self, tmp_path: Path) -> None:
        # accept loads humanhand.domain.lexical_review before validating
        # the run, so the fail-closed exit-2 path is reachable even for an
        # unknown run; the ordering is documented in the module docstring.
        proj = tmp_path / "proj"
        _init_project(proj)
        result = _invoke(
            "accept",
            "--project",
            str(proj),
            "--run",
            "r1",
            "--change",
            "ch1",
            "--json",
        )
        assert result.exit_code == 2, result.stderr
        data = json.loads(result.stdout)
        assert data["status"] == "error"
        assert "not available" in data["message"]


class TestReviewLifecycle:
    @pytest.mark.importers
    @NEED_REVIEW
    def test_review_shows_run_after_lexical(self, tmp_path: Path) -> None:
        proj = tmp_path / "proj"
        _init_project(proj)
        doc = tmp_path / "doc.txt"
        doc.write_text("The team will utilize the new tool.", encoding="utf-8")
        lexical = _invoke("lexical", "--project", str(proj), "--text-file", str(doc), "--json")
        assert lexical.exit_code == 0, lexical.stderr
        payload = json.loads(lexical.stdout)
        run_id: str = payload["run_id"]
        result = _invoke("review", "--project", str(proj), "--run", run_id, "--json")
        assert result.exit_code == 0, result.stderr
        data = json.loads(result.stdout)
        assert data["status"] == "ok"
        assert data["run_id"] == run_id
        # The stored proposal is returned unchanged.
        assert data["proposal"] == payload
        # Without a journal file the initial review state is shown.
        assert isinstance(data["journal"], dict)

    @pytest.mark.importers
    @NEED_REVIEW
    def test_accept_updates_journal_and_persists(self, tmp_path: Path) -> None:
        proj = tmp_path / "proj"
        _init_project(proj)
        run_id, change_id = _create_run(proj, tmp_path)
        review_before = _invoke("review", "--project", str(proj), "--run", run_id, "--json")
        assert review_before.exit_code == 0, review_before.stderr
        journal_before = json.loads(review_before.stdout)["journal"]
        accept = _invoke(
            "accept", "--project", str(proj), "--run", run_id, "--change", change_id, "--json"
        )
        assert accept.exit_code == 0, accept.stderr
        data = json.loads(accept.stdout)
        assert data["status"] == "ok"
        assert data["run_id"] == run_id
        assert data["change_id"] == change_id
        assert data["decision"] == "accept"
        # The journal changed: a decision entry was recorded by the real
        # apply_review call.
        assert data["journal"] != journal_before
        # The journal file persists at the documented path
        # (.humanhand/reports/finalize/<run_id>.journal.json) and matches
        # the printed journal exactly after a JSON round trip.
        journal_file = proj / ".humanhand" / "reports" / "finalize" / f"{run_id}.journal.json"
        assert journal_file.is_file()
        assert json.loads(journal_file.read_text(encoding="utf-8")) == data["journal"]
        # A later review invocation (separate command) shows the persisted
        # journal.
        review_after = _invoke("review", "--project", str(proj), "--run", run_id, "--json")
        assert review_after.exit_code == 0, review_after.stderr
        assert json.loads(review_after.stdout)["journal"] == data["journal"]

    @pytest.mark.importers
    @NEED_REVIEW
    def test_reject_records_and_journal_persists_across_invocations(self, tmp_path: Path) -> None:
        proj = tmp_path / "proj"
        _init_project(proj)
        run_id, change_id = _create_run(proj, tmp_path)
        accept = _invoke(
            "accept", "--project", str(proj), "--run", run_id, "--change", change_id, "--json"
        )
        assert accept.exit_code == 0, accept.stderr
        accept_journal = json.loads(accept.stdout)["journal"]
        # Reject the same change in a separate invocation: the journal read
        # from the persisted file is updated, so the rejected journal
        # differs from the accepted one.
        reject = _invoke(
            "reject", "--project", str(proj), "--run", run_id, "--change", change_id, "--json"
        )
        assert reject.exit_code == 0, reject.stderr
        reject_data = json.loads(reject.stdout)
        assert reject_data["decision"] == "reject"
        assert reject_data["journal"] != accept_journal
        # Accepting again updates the journal again: each decision appends
        # to the journal persisted by the previous invocation.
        accept2 = _invoke(
            "accept", "--project", str(proj), "--run", run_id, "--change", change_id, "--json"
        )
        assert accept2.exit_code == 0, accept2.stderr
        accept2_journal = json.loads(accept2.stdout)["journal"]
        assert accept2_journal != reject_data["journal"]
        assert accept2_journal != accept_journal
        # The journal file at the documented path now holds the final
        # journal.
        journal_file = proj / ".humanhand" / "reports" / "finalize" / f"{run_id}.journal.json"
        assert json.loads(journal_file.read_text(encoding="utf-8")) == accept2_journal

    @pytest.mark.importers
    @NEED_REVIEW
    def test_accept_unknown_change_id_is_input_error(self, tmp_path: Path) -> None:
        proj = tmp_path / "proj"
        _init_project(proj)
        run_id, _ = _create_run(proj, tmp_path)
        result = _invoke(
            "accept",
            "--project",
            str(proj),
            "--run",
            run_id,
            "--change",
            "no-such-change",
            "--json",
        )
        assert result.exit_code == 1, result.stderr
        data = json.loads(result.stdout)
        assert data["status"] == "error"
        assert data["exit_code"] == 1
        assert "Unknown change id" in data["message"]

    @pytest.mark.importers
    @NEED_REVIEW
    def test_accept_unknown_run_id_is_input_error(self, tmp_path: Path) -> None:
        proj = tmp_path / "proj"
        _init_project(proj)
        result = _invoke(
            "accept",
            "--project",
            str(proj),
            "--run",
            "no-such-run",
            "--change",
            "ch1",
            "--json",
        )
        assert result.exit_code == 1, result.stderr
        data = json.loads(result.stdout)
        assert data["status"] == "error"
        assert "Run not found" in data["message"]
