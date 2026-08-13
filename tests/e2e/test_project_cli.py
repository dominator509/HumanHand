"""E2E tests for the `humanhand project` commands (EP-015).

The orchestrator registers ``project_app`` into ``humanhand.cli.app`` at
merge time; these tests compose a local root app the same way so they run
standalone and exercise the real command functions.

Parallel EP-015 modules (``infra.stores.project_layout``,
``infra.stores.project_store``, ``domain.project``) are merged in parallel
and may be absent while this file is being merged. Tests that require them
skip with an honest reason; everything that runs today (error paths, JSON
purity, fail-closed behavior, the ingest status gate) runs now.
"""

from __future__ import annotations

import importlib.util
import json
from pathlib import Path
from typing import Any

import pytest
import typer
from typer.testing import CliRunner

from humanhand.cli.project_commands import project_app
from humanhand.domain.canonical_document import (
    CoverageSummary,
    build_document,
    make_inspection,
)
from humanhand.domain.document_nodes import NodeBuilder, NodeType
from humanhand.domain.file_identity import derive_identity
from humanhand.domain.import_policy import ImportPolicy
from humanhand.domain.source_package import LANE_SOURCE, build_source_package

cli_app = typer.Typer()
cli_app.add_typer(project_app, name="project")

runner = CliRunner()

HAS_PROJECT_LAYOUT = importlib.util.find_spec("humanhand.infra.stores.project_layout") is not None
HAS_PROJECT_STORE = importlib.util.find_spec("humanhand.infra.stores.project_store") is not None
HAS_DOMAIN_PROJECT = importlib.util.find_spec("humanhand.domain.project") is not None
HAS_PARALLEL_PROJECT = HAS_PROJECT_LAYOUT and HAS_PROJECT_STORE and HAS_DOMAIN_PROJECT

NEED_PARALLEL = pytest.mark.skipif(
    not HAS_PARALLEL_PROJECT,
    reason="parallel EP-015 modules (project_layout, project_store, domain.project) not merged",
)

ONLY_WITHOUT_PARALLEL = pytest.mark.skipif(
    HAS_PARALLEL_PROJECT,
    reason="parallel EP-015 modules present; the fail-closed path is no longer reachable",
)


def _document(text: str = "In 2024 we shipped 300 units.") -> object:
    root = NodeBuilder(node_type=NodeType.DOCUMENT)
    root.add_child(NodeBuilder(node_type=NodeType.PARAGRAPH, text=text))
    return build_document(
        root=root,
        lane=LANE_SOURCE,
        parser_name="text",
        parser_version="1",
        policy=ImportPolicy(lane=LANE_SOURCE),
        surface_text=text,
    )


def _inspection(text: str = "In 2024 we shipped 300 units.") -> object:
    raw = text.encode("utf-8")
    return make_inspection(
        raw=raw,
        identity=derive_identity("sample.txt", raw),
        lane=LANE_SOURCE,
        parser_name="text",
        parser_version="1",
        policy=ImportPolicy(lane=LANE_SOURCE),
        findings=(),
        coverage=CoverageSummary(
            adapter="text",
            supported_structures=("paragraph",),
            unsupported_structures=(),
            status="complete",
        ),
        document=_document(text),  # type: ignore[arg-type]
    )


def _build_package_file(tmp_path: Path, text: str = "In 2024 we shipped 300 units.") -> Path:
    """Write a real source-package JSON file (the ingest input format)."""
    package = build_source_package(_inspection(text))  # type: ignore[arg-type]
    out = tmp_path / "package.json"
    out.write_text(package.to_json(), encoding="utf-8")
    return out


def _invoke(*args: str) -> Any:
    return runner.invoke(cli_app, ["project", *args])


class TestErrorPaths:
    def test_status_missing_project_dir_is_input_error(self, tmp_path: Path) -> None:
        missing = tmp_path / "missing"
        result = _invoke("status", "--project", str(missing), "--json")
        assert result.exit_code == 1, result.stderr
        data = json.loads(result.stdout)
        assert data["status"] == "error"
        assert data["exit_code"] == 1
        assert str(missing) in data["message"]

    def test_status_uninitialized_dir_is_input_error(self, tmp_path: Path) -> None:
        # Existing directory without .humanhand/project.toml (blueprint 9.3).
        result = _invoke("status", "--project", str(tmp_path), "--json")
        assert result.exit_code == 1, result.stderr
        data = json.loads(result.stdout)
        assert data["status"] == "error"
        assert "not initialized" in data["message"]

    def test_project_flag_beats_env_var(
        self, tmp_path: Path, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        # Resolution order: --project > HUMANHAND_PROJECT_DIR > ".".
        env_dir = tmp_path / "from-env"
        flag_dir = tmp_path / "from-flag"
        monkeypatch.setenv("HUMANHAND_PROJECT_DIR", str(env_dir))
        result = _invoke("status", "--project", str(flag_dir), "--json")
        assert result.exit_code == 1, result.stderr
        data = json.loads(result.stdout)
        assert str(flag_dir) in data["message"]

    def test_env_var_is_used_when_flag_omitted(
        self, tmp_path: Path, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        env_dir = tmp_path / "from-env"
        monkeypatch.setenv("HUMANHAND_PROJECT_DIR", str(env_dir))
        result = _invoke("status", "--json")
        assert result.exit_code == 1, result.stderr
        data = json.loads(result.stdout)
        assert str(env_dir) in data["message"]

    def test_ingest_missing_package_file_is_io_error(self, tmp_path: Path) -> None:
        result = _invoke(
            "ingest", str(tmp_path / "missing.json"), "--project", str(tmp_path), "--json"
        )
        assert result.exit_code == 3, result.stderr
        data = json.loads(result.stdout)
        assert data["status"] == "error"
        assert data["exit_code"] == 3

    def test_ingest_rejects_non_ok_package(self, tmp_path: Path) -> None:
        # A package whose status is not ok/findings fails at the real
        # status gate (ImportStatus re-derived from the payload by
        # source_package_from_json) before any store access.
        package = build_source_package(_inspection())  # type: ignore[arg-type]
        payload = package.to_payload()
        payload["status"] = "quarantined"
        package_file = tmp_path / "quarantined.json"
        package_file.write_text(json.dumps(payload), encoding="utf-8")
        result = _invoke("ingest", str(package_file), "--project", str(tmp_path), "--json")
        assert result.exit_code == 1, result.stderr
        data = json.loads(result.stdout)
        assert data["status"] == "error"
        assert "cannot be ingested" in data["message"]

    def test_json_stdout_is_pure_on_error(self, tmp_path: Path) -> None:
        # The entire stdout is exactly one JSON document on error paths.
        result = _invoke("status", "--project", str(tmp_path / "missing"), "--json")
        assert result.exit_code == 1
        json.loads(result.stdout)


class TestFailClosedWithoutParallelModules:
    @ONLY_WITHOUT_PARALLEL
    def test_init_fails_closed_when_parallel_modules_absent(self, tmp_path: Path) -> None:
        result = _invoke("init", str(tmp_path / "proj"), "--name", "Demo", "--json")
        assert result.exit_code == 2, result.stderr
        data = json.loads(result.stdout)
        assert data["status"] == "error"
        assert "not available" in data["message"]

    @ONLY_WITHOUT_PARALLEL
    def test_status_fails_closed_when_parallel_modules_absent(self, tmp_path: Path) -> None:
        # Simulate the documented layout (blueprint 9.3) so the filesystem
        # check passes and the command reaches the module load.
        (tmp_path / ".humanhand").mkdir()
        (tmp_path / ".humanhand" / "project.toml").write_text(
            'name = "Demo"\nschema_version = 1\n', encoding="utf-8"
        )
        result = _invoke("status", "--project", str(tmp_path), "--json")
        assert result.exit_code == 2, result.stderr
        data = json.loads(result.stdout)
        assert data["status"] == "error"
        assert "not available" in data["message"]

    @ONLY_WITHOUT_PARALLEL
    def test_export_obsidian_fails_closed(self, tmp_path: Path) -> None:
        # Per the command spec, the projection-missing error is exit 1 and
        # the message contains the documented phrase.
        result = _invoke(
            "export-obsidian", str(tmp_path / "vault"), "--project", str(tmp_path), "--json"
        )
        assert result.exit_code == 1, result.stderr
        data = json.loads(result.stdout)
        assert data["status"] == "error"
        assert "obsidian projection unavailable" in data["message"]


class TestParallelProjectLifecycle:
    @NEED_PARALLEL
    def test_init_creates_layout(self, tmp_path: Path) -> None:
        proj = tmp_path / "proj"
        result = _invoke("init", str(proj), "--name", "Demo", "--json")
        assert result.exit_code == 0, result.stderr
        data = json.loads(result.stdout)
        assert data["status"] == "ok"
        assert Path(data["root"]) == Path(str(proj))
        assert isinstance(data["project_id"], str)
        assert data["project_id"]
        # Documented layout (blueprint 9.3): .humanhand/project.toml + dirs.
        assert (proj / ".humanhand" / "project.toml").is_file()
        assert (proj / ".humanhand" / "blobs").is_dir()

    @NEED_PARALLEL
    def test_init_is_idempotent(self, tmp_path: Path) -> None:
        proj = tmp_path / "proj"
        first = _invoke("init", str(proj), "--name", "Demo", "--json")
        second = _invoke("init", str(proj), "--name", "Ignored replacement", "--json")
        assert first.exit_code == 0, first.stderr
        assert second.exit_code == 0, second.stderr
        assert json.loads(first.stdout)["project_id"] == json.loads(second.stdout)["project_id"]

    @NEED_PARALLEL
    def test_status_shows_name_and_revision_count(self, tmp_path: Path) -> None:
        proj = tmp_path / "proj"
        _invoke("init", str(proj), "--name", "Demo", "--json")
        result = _invoke("status", "--project", str(proj), "--json")
        assert result.exit_code == 0, result.stderr
        data = json.loads(result.stdout)
        assert data["status"] == "ok"
        assert data["name"] == "Demo"
        assert data["schema_version"] == "2"
        assert data["revisions"] == 0

    @NEED_PARALLEL
    def test_ingest_and_revisions_lifecycle(self, tmp_path: Path) -> None:
        package_file = _build_package_file(tmp_path)
        proj = tmp_path / "proj"
        _invoke("init", str(proj), "--name", "Demo", "--json")
        ingest = _invoke("ingest", str(package_file), "--project", str(proj), "--json")
        assert ingest.exit_code == 0, ingest.stderr
        ingested = json.loads(ingest.stdout)
        assert ingested["status"] == "ok"
        assert ingested["approval"] == "ingest"
        assert ingested["document_id"].startswith("src-")

        status = _invoke("status", "--project", str(proj), "--json")
        assert status.exit_code == 0, status.stderr
        assert json.loads(status.stdout)["revisions"] == 1

        revisions = _invoke("revisions", "--project", str(proj), "--json")
        assert revisions.exit_code == 0, revisions.stderr
        rows = json.loads(revisions.stdout)
        assert len(rows) == 1
        assert rows[0]["document_id"] == ingested["document_id"]
        assert rows[0]["revision_id"]
        assert rows[0]["token"]

    @NEED_PARALLEL
    def test_two_documents_with_local_ids_ingest_cleanly(self, tmp_path: Path) -> None:
        first_package = _build_package_file(tmp_path, "In 2024 we shipped 300 units.")
        first_text = first_package.read_text(encoding="utf-8")
        second_package = _build_package_file(tmp_path, "In 2025 we shipped 400 units.")
        first_file = tmp_path / "first-package.json"
        first_file.write_text(first_text, encoding="utf-8")
        proj = tmp_path / "proj"
        _invoke("init", str(proj), "--name", "Demo", "--json")

        first = _invoke("ingest", str(first_file), "--project", str(proj), "--json")
        second = _invoke("ingest", str(second_package), "--project", str(proj), "--json")
        assert first.exit_code == 0, first.stderr
        assert second.exit_code == 0, second.stderr
        revisions = _invoke("revisions", "--project", str(proj), "--json")
        assert revisions.exit_code == 0, revisions.stderr
        assert len(json.loads(revisions.stdout)) == 2

    @NEED_PARALLEL
    def test_revisions_missing_project_dir_is_input_error(self, tmp_path: Path) -> None:
        result = _invoke("revisions", "--project", str(tmp_path / "missing"), "--json")
        assert result.exit_code == 1, result.stderr
        json.loads(result.stdout)  # JSON purity on the error path
