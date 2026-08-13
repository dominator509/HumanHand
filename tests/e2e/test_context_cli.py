"""E2E tests for the `humanhand context` commands (EP-015).

The orchestrator registers ``context_app`` into ``humanhand.cli.app`` at
merge time; these tests compose a local root app the same way so they run
standalone and exercise the real command functions.

Parallel EP-015 modules (``domain.context_capsule``,
``domain.context_policy``, the project store, and the claim/entity and
revision domain modules) are merged in parallel and may be absent while
this file is being merged. Tests that require them skip with an honest
reason; everything that runs today (error paths, JSON purity, fail-closed
behavior, block resolution against the real canonical document) runs now.
"""

from __future__ import annotations

import importlib.util
import json
from pathlib import Path
from typing import Any

import pytest
import typer
from typer.testing import CliRunner

from humanhand.cli.context_commands import context_app
from humanhand.cli.project_commands import project_app
from humanhand.domain.canonical_document import (
    CoverageSummary,
    build_document,
    make_inspection,
)
from humanhand.domain.document_nodes import NodeBuilder, NodeType
from humanhand.domain.file_identity import derive_identity
from humanhand.domain.import_policy import ImportPolicy
from humanhand.domain.source_package import (
    LANE_SOURCE,
    build_source_package,
    source_package_from_json,
)

cli_app = typer.Typer()
cli_app.add_typer(project_app, name="project")
cli_app.add_typer(context_app, name="context")

runner = CliRunner()

HAS_CONTEXT_CAPSULE = importlib.util.find_spec("humanhand.domain.context_capsule") is not None
HAS_CONTEXT_POLICY = importlib.util.find_spec("humanhand.domain.context_policy") is not None
HAS_PROJECT_STORE = importlib.util.find_spec("humanhand.infra.stores.project_store") is not None
HAS_DOMAIN_PROJECT = importlib.util.find_spec("humanhand.domain.project") is not None
HAS_REVISIONS = importlib.util.find_spec("humanhand.domain.revisions") is not None
HAS_PARALLEL_CONTEXT = (
    HAS_CONTEXT_CAPSULE
    and HAS_CONTEXT_POLICY
    and HAS_PROJECT_STORE
    and HAS_DOMAIN_PROJECT
    and HAS_REVISIONS
)

NEED_PARALLEL = pytest.mark.skipif(
    not HAS_PARALLEL_CONTEXT,
    reason="parallel EP-015 modules (context_capsule, context_policy, store, domain) not merged",
)

ONLY_WITHOUT_PARALLEL = pytest.mark.skipif(
    HAS_PARALLEL_CONTEXT,
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
    """Write a real source-package JSON file (the preview input format)."""
    package = build_source_package(_inspection(text))  # type: ignore[arg-type]
    out = tmp_path / "package.json"
    out.write_text(package.to_json(), encoding="utf-8")
    return out


def _invoke_context(*args: str) -> Any:
    return runner.invoke(cli_app, ["context", *args])


def _invoke_project(*args: str) -> Any:
    return runner.invoke(cli_app, ["project", *args])


class TestValidateErrorPaths:
    def test_validate_missing_file_is_io_error(self, tmp_path: Path) -> None:
        result = _invoke_context("validate", str(tmp_path / "missing.json"), "--json")
        assert result.exit_code == 3, result.stderr
        data = json.loads(result.stdout)
        assert data["status"] == "error"
        assert data["exit_code"] == 3

    def test_validate_non_json_file_is_input_error(self, tmp_path: Path) -> None:
        bad = tmp_path / "bad.json"
        bad.write_text("this is not json", encoding="utf-8")
        result = _invoke_context("validate", str(bad), "--json")
        assert result.exit_code == 1, result.stderr
        data = json.loads(result.stdout)
        assert data["status"] == "error"
        assert "Invalid capsule JSON" in data["message"]

    def test_validate_json_stdout_is_pure_on_error(self, tmp_path: Path) -> None:
        bad = tmp_path / "bad.json"
        bad.write_text("this is not json", encoding="utf-8")
        result = _invoke_context("validate", str(bad), "--json")
        assert result.exit_code == 1
        json.loads(result.stdout)  # entire stdout is exactly one JSON document

    @ONLY_WITHOUT_PARALLEL
    def test_validate_fails_closed_when_capsule_module_absent(self, tmp_path: Path) -> None:
        # "{}" is valid JSON, so the shape check passes and the command
        # reaches the capsule module load.
        capsule_file = tmp_path / "capsule.json"
        capsule_file.write_text("{}", encoding="utf-8")
        result = _invoke_context("validate", str(capsule_file), "--json")
        assert result.exit_code == 2, result.stderr
        data = json.loads(result.stdout)
        assert data["status"] == "error"
        assert "not available" in data["message"]


class TestPreviewErrorPaths:
    def test_preview_missing_project_dir_is_input_error(self, tmp_path: Path) -> None:
        result = _invoke_context(
            "preview",
            "--project",
            str(tmp_path / "missing"),
            "--block",
            "b1",
            "--document",
            str(tmp_path / "package.json"),
            "--json",
        )
        assert result.exit_code == 1, result.stderr
        data = json.loads(result.stdout)
        assert data["status"] == "error"
        assert data["exit_code"] == 1

    def test_preview_missing_document_file_is_io_error(self, tmp_path: Path) -> None:
        result = _invoke_context(
            "preview",
            "--project",
            str(tmp_path),
            "--block",
            "b1",
            "--document",
            str(tmp_path / "missing.json"),
            "--json",
        )
        assert result.exit_code == 3, result.stderr
        data = json.loads(result.stdout)
        assert data["status"] == "error"
        assert data["exit_code"] == 3

    def test_preview_block_not_found_is_input_error(self, tmp_path: Path) -> None:
        # Block resolution runs against the real canonical document parsed
        # from the source-package file (no parallel modules needed).
        package_file = _build_package_file(tmp_path)
        result = _invoke_context(
            "preview",
            "--project",
            str(tmp_path),
            "--block",
            "no-such-block",
            "--document",
            str(package_file),
            "--json",
        )
        assert result.exit_code == 1, result.stderr
        data = json.loads(result.stdout)
        assert data["status"] == "error"
        assert "Block not found" in data["message"]


class TestParallelCapsuleLifecycle:
    @NEED_PARALLEL
    def test_preview_rejects_package_not_ingested_in_project(self, tmp_path: Path) -> None:
        ingested_file = _build_package_file(tmp_path, "In 2024 we shipped 300 units.")
        ingested_text = ingested_file.read_text(encoding="utf-8")
        other_file = _build_package_file(tmp_path, "In 2025 we shipped 400 units.")
        saved_ingested = tmp_path / "ingested.json"
        saved_ingested.write_text(ingested_text, encoding="utf-8")
        other = source_package_from_json(other_file.read_text(encoding="utf-8"))
        block_id = other.document.nodes[1].node_id
        proj = tmp_path / "proj"
        _invoke_project("init", str(proj), "--name", "Demo", "--json")
        _invoke_project("ingest", str(saved_ingested), "--project", str(proj), "--json")

        preview = _invoke_context(
            "preview",
            "--project",
            str(proj),
            "--block",
            block_id,
            "--document",
            str(other_file),
            "--json",
        )
        assert preview.exit_code == 1, preview.stderr
        assert "not ingested" in json.loads(preview.stdout)["message"]

    @NEED_PARALLEL
    def test_preview_produces_valid_capsule(self, tmp_path: Path) -> None:
        package_file = _build_package_file(tmp_path)
        package = source_package_from_json(package_file.read_text(encoding="utf-8"))
        # The first non-document node is the paragraph block; node ids are
        # assigned deterministically by build_document.
        block_id = package.document.nodes[1].node_id
        proj = tmp_path / "proj"
        init = _invoke_project("init", str(proj), "--name", "Demo", "--json")
        assert init.exit_code == 0, init.stderr
        ingest = _invoke_project("ingest", str(package_file), "--project", str(proj), "--json")
        assert ingest.exit_code == 0, ingest.stderr
        preview = _invoke_context(
            "preview",
            "--project",
            str(proj),
            "--block",
            block_id,
            "--document",
            str(package_file),
            "--json",
        )
        assert preview.exit_code == 0, preview.stderr
        capsule_text = preview.stdout
        data = json.loads(capsule_text)
        # Capsule JSON must expose a valid capsule_id (per SPEC-012).
        assert isinstance(data.get("capsule_id"), str)
        assert data["capsule_id"]

        from humanhand.domain.context_capsule import capsule_from_json

        restored = capsule_from_json(capsule_text)  # integrity-verified round trip
        assert restored is not None

    @NEED_PARALLEL
    def test_validate_round_trip_passes(self, tmp_path: Path) -> None:
        package_file = _build_package_file(tmp_path)
        package = source_package_from_json(package_file.read_text(encoding="utf-8"))
        block_id = package.document.nodes[1].node_id
        proj = tmp_path / "proj"
        _invoke_project("init", str(proj), "--name", "Demo", "--json")
        _invoke_project("ingest", str(package_file), "--project", str(proj), "--json")
        preview = _invoke_context(
            "preview",
            "--project",
            str(proj),
            "--block",
            block_id,
            "--document",
            str(package_file),
            "--json",
        )
        assert preview.exit_code == 0, preview.stderr
        capsule_file = tmp_path / "capsule.json"
        capsule_file.write_text(preview.stdout, encoding="utf-8")
        result = _invoke_context("validate", str(capsule_file), "--json")
        assert result.exit_code == 0, result.stderr
        data = json.loads(result.stdout)
        assert data["status"] == "ok"
        assert data["violations"] == []

    @NEED_PARALLEL
    def test_validate_tampered_capsule_fails(self, tmp_path: Path) -> None:
        package_file = _build_package_file(tmp_path)
        package = source_package_from_json(package_file.read_text(encoding="utf-8"))
        block_id = package.document.nodes[1].node_id
        proj = tmp_path / "proj"
        _invoke_project("init", str(proj), "--name", "Demo", "--json")
        _invoke_project("ingest", str(package_file), "--project", str(proj), "--json")
        preview = _invoke_context(
            "preview",
            "--project",
            str(proj),
            "--block",
            block_id,
            "--document",
            str(package_file),
            "--json",
        )
        assert preview.exit_code == 0, preview.stderr
        payload = json.loads(preview.stdout)
        # Tamper with content and fix nothing: the capsule's capsule_id
        # integrity anchor is not updated, so capsule_from_json is
        # expected to reject the mismatch (fails closed). We assert the
        # command exits nonzero with an error/invalid JSON — whichever
        # path the real modules take.
        payload["current_block_text"] = str(payload["current_block_text"]) + " tampered"
        tampered = tmp_path / "tampered.json"
        tampered.write_text(json.dumps(payload, sort_keys=True), encoding="utf-8")
        result = _invoke_context("validate", str(tampered), "--json")
        assert result.exit_code != 0, result.stdout
        data = json.loads(result.stdout)
        assert data["status"] in {"error", "invalid"}
