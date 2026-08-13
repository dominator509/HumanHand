"""E2E tests for `humanhand export document` and `humanhand audit` (EP-016).

The orchestrator registers ``export_app`` and ``audit_app`` into
``humanhand.cli.app`` at merge time; these tests compose a local root app
the same way so they run standalone and exercise the real command
functions.

The parallel EP-016 modules (``domain.public_document``,
``domain.export_contract``, ``infra.exporters``,
``infra.auditors``) are merged in parallel and may be absent while this
file is being merged. Tests that require them skip with an honest
reason; format validation, IO errors, and the fail-closed paths run
today against the real EP-015 store and package pipeline.
"""

from __future__ import annotations

import importlib.util
import json
from pathlib import Path
from typing import Any

import pytest
import typer
from typer.testing import CliRunner

from humanhand.cli.audit_commands import audit_app
from humanhand.cli.export_commands import export_app
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
from humanhand.infra.stores.project_layout import init_layout

cli_app = typer.Typer()
cli_app.add_typer(export_app, name="export")
cli_app.add_typer(audit_app, name="audit")
cli_app.add_typer(project_app, name="project")

runner = CliRunner()

HAS_PUBLIC_DOCUMENT = importlib.util.find_spec("humanhand.domain.public_document") is not None
HAS_EXPORT_CONTRACT = importlib.util.find_spec("humanhand.domain.export_contract") is not None
HAS_EXPORTERS = importlib.util.find_spec("humanhand.infra.exporters") is not None
HAS_AUDITORS = importlib.util.find_spec("humanhand.infra.auditors") is not None
HAS_UNICODE_AUDITOR = (
    importlib.util.find_spec("humanhand.infra.auditors.unicode_auditor") is not None
)

HAS_EXPORT_PARALLEL = HAS_PUBLIC_DOCUMENT and HAS_EXPORT_CONTRACT and HAS_EXPORTERS

NEED_EXPORT_AND_AUDIT = pytest.mark.skipif(
    not (HAS_EXPORT_PARALLEL and HAS_AUDITORS),
    reason=(
        "parallel EP-016 export/audit modules "
        "(public_document, export_contract, exporters, auditors) not merged"
    ),
)

NEED_UNICODE_AUDIT = pytest.mark.skipif(
    not HAS_UNICODE_AUDITOR,
    reason="parallel EP-016 module humanhand.infra.auditors.unicode_auditor not merged",
)

ONLY_WITHOUT_EXPORT = pytest.mark.skipif(
    HAS_EXPORT_PARALLEL,
    reason="parallel EP-016 export modules present; the fail-closed path is no longer reachable",
)

ONLY_WITHOUT_AUDITORS = pytest.mark.skipif(
    HAS_AUDITORS,
    reason="parallel EP-016 auditors module present; the fail-closed path is no longer reachable",
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


def _init_project(root: Path, name: str = "Demo") -> None:
    """Initialize a real project layout through the EP-015 store code."""
    init_layout(root, name=name)


def _invoke_export(*args: str) -> Any:
    return runner.invoke(cli_app, ["export", *args])


def _invoke_audit(*args: str) -> Any:
    return runner.invoke(cli_app, ["audit", *args])


def _ingest(package_file: Path, project: Path) -> None:
    result = runner.invoke(
        cli_app,
        ["project", "ingest", str(package_file), "--project", str(project), "--json"],
    )
    assert result.exit_code == 0, result.stderr


class TestExportDocument:
    @NEED_EXPORT_AND_AUDIT
    def test_export_txt_then_audit_lifecycle(self, tmp_path: Path) -> None:
        package_file = _build_package_file(tmp_path)
        proj = tmp_path / "proj"
        _init_project(proj)
        _ingest(package_file, proj)
        out = tmp_path / "out.txt"

        export = _invoke_export(
            "document",
            "--project",
            str(proj),
            "--format",
            "txt",
            "--out",
            str(out),
            "--package",
            str(package_file),
            "--json",
        )
        assert export.exit_code == 0, export.stderr
        data = json.loads(export.stdout)
        assert data["status"] == "ok"
        # The exporter's own result must agree with the real file on disk.
        assert Path(data["output_path"]).is_file()
        assert data["byte_count"] == out.stat().st_size
        assert len(data["sha256"]) == 64
        content = out.read_text(encoding="utf-8")
        # Blueprint 11.2 TXT guarantees: no BOM, exactly one trailing newline.
        assert not content.startswith("\ufeff")
        assert content.endswith("\n")
        assert "In 2024 we shipped 300 units." in content

        audit = _invoke_audit("artifact", str(out), "--json")
        assert audit.exit_code == 0, audit.stderr
        assert json.loads(audit.stdout)["status"] == "pass"

        # Tamper with the artifact bytes; the independent audit must fail
        # (exit 1) with the JSON report still on stdout. A standalone TXT
        # audit (no --expected) checks byte-level rules (no BOM, exactly
        # one trailing newline, no CR bytes) and prohibited
        # internal-metadata terms; appending plain text would preserve
        # all of those and pass, so the tamper injects a prohibited
        # metadata term (blueprint 11.2/11.3).
        out.write_text(content + "project_id=123\n", encoding="utf-8")
        tampered = _invoke_audit("artifact", str(out), "--json")
        assert tampered.exit_code == 1, tampered.stderr
        failed = json.loads(tampered.stdout)
        assert failed["status"] == "fail"

    @NEED_EXPORT_AND_AUDIT
    def test_export_rejects_package_not_ingested_into_project(self, tmp_path: Path) -> None:
        package_file = _build_package_file(tmp_path)
        proj = tmp_path / "proj"
        _init_project(proj)

        result = _invoke_export(
            "document",
            "--project",
            str(proj),
            "--format",
            "txt",
            "--out",
            str(tmp_path / "out.txt"),
            "--package",
            str(package_file),
            "--json",
        )

        assert result.exit_code == 1
        assert "not ingested" in json.loads(result.stdout)["message"]

    def test_export_bogus_format_exits_1(self, tmp_path: Path) -> None:
        # Format validation runs before any project, package, or module
        # access, so this passes without any parallel module.
        result = _invoke_export(
            "document",
            "--project",
            str(tmp_path / "missing"),
            "--format",
            "bogus",
            "--out",
            str(tmp_path / "out.txt"),
            "--package",
            str(tmp_path / "missing.json"),
            "--json",
        )
        assert result.exit_code == 1, result.stderr
        data = json.loads(result.stdout)
        assert data["status"] == "error"
        assert data["exit_code"] == 1
        assert "Unknown export format" in data["message"]

    def test_export_missing_package_is_io_error(self, tmp_path: Path) -> None:
        proj = tmp_path / "proj"
        _init_project(proj)
        result = _invoke_export(
            "document",
            "--project",
            str(proj),
            "--format",
            "txt",
            "--out",
            str(tmp_path / "out.txt"),
            "--package",
            str(tmp_path / "missing.json"),
            "--json",
        )
        assert result.exit_code == 3, result.stderr
        data = json.loads(result.stdout)
        assert data["status"] == "error"
        assert data["exit_code"] == 3

    @ONLY_WITHOUT_EXPORT
    def test_export_fails_closed_when_parallel_modules_absent(self, tmp_path: Path) -> None:
        package_file = _build_package_file(tmp_path)
        proj = tmp_path / "proj"
        _init_project(proj)
        result = _invoke_export(
            "document",
            "--project",
            str(proj),
            "--format",
            "txt",
            "--out",
            str(tmp_path / "out.txt"),
            "--package",
            str(package_file),
            "--json",
        )
        assert result.exit_code == 2, result.stderr
        data = json.loads(result.stdout)
        assert data["status"] == "error"
        assert "not available" in data["message"]


class TestAuditArtifact:
    @ONLY_WITHOUT_AUDITORS
    def test_artifact_fails_closed_without_auditors_module(self, tmp_path: Path) -> None:
        target = tmp_path / "artifact.txt"
        target.write_text("Approved public artifact text.\n", encoding="utf-8")
        result = _invoke_audit("artifact", str(target), "--json")
        assert result.exit_code == 2, result.stderr
        data = json.loads(result.stdout)
        assert data["status"] == "error"
        assert "not available" in data["message"]

    def test_artifact_missing_file_is_io_error(self, tmp_path: Path) -> None:
        # The target-file check runs before any parallel module load.
        result = _invoke_audit("artifact", str(tmp_path / "missing.txt"), "--json")
        assert result.exit_code == 3, result.stderr
        data = json.loads(result.stdout)
        assert data["status"] == "error"
        assert data["exit_code"] == 3


class TestAuditUnicode:
    @NEED_UNICODE_AUDIT
    def test_unicode_clean_file_passes(self, tmp_path: Path) -> None:
        target = tmp_path / "clean.txt"
        target.write_text("Clean UTF-8 text, no BOM.\n", encoding="utf-8")
        result = _invoke_audit("unicode", str(target), "--json")
        assert result.exit_code == 0, result.stderr
        data = json.loads(result.stdout)
        assert data["status"] == "pass"

    @NEED_UNICODE_AUDIT
    def test_unicode_control_char_file_fails(self, tmp_path: Path) -> None:
        # The unicode auditor flags control characters (category Cc);
        # NUL is Cc, so this file must fail. BOM (U+FEFF, category Cf) is
        # the TEXT auditor's check (audit.utf8.bom), not the unicode
        # auditor's, so it is not asserted here.
        target = tmp_path / "control.txt"
        target.write_bytes(b"hello\x00world\n")
        result = _invoke_audit("unicode", str(target), "--json")
        assert result.exit_code == 1, result.stderr
        data = json.loads(result.stdout)
        assert data["status"] == "fail"

    @NEED_UNICODE_AUDIT
    def test_unicode_non_nfc_warning_passes(self, tmp_path: Path) -> None:
        # Non-NFC text is a WARNING-only finding; per SPEC-013 warnings
        # alone pass the audit. The escape sequence is an explicit
        # decomposed "e" + combining acute (U+0301), so the file is
        # genuinely non-NFC.
        target = tmp_path / "nfc.txt"
        target.write_text("cafe\u0301\n", encoding="utf-8")
        result = _invoke_audit("unicode", str(target), "--json")
        assert result.exit_code == 0, result.stderr
        data = json.loads(result.stdout)
        assert data["status"] == "pass"
