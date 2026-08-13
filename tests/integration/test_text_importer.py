"""Integration tests for the TXT import adapter (EP-012)."""

from __future__ import annotations

from pathlib import Path

import pytest

from humanhand.domain.canonical_document import ImportInspection
from humanhand.domain.document_nodes import NodeType
from humanhand.domain.import_findings import FindingCode, ImportStatus
from humanhand.domain.import_policy import ImportPolicy
from humanhand.infra.importers.text_importer import TextImporter

fixtures_dir: Path = Path(__file__).resolve().parents[1] / "fixtures" / "import"
policy = ImportPolicy(lane="source")


def _inspect(name: str, raw: bytes, import_policy: ImportPolicy = policy) -> ImportInspection:
    """Run a full inspect over fixture bytes using the TXT adapter."""
    return TextImporter().inspect(raw=raw, path=str(fixtures_dir / name), policy=import_policy)


@pytest.mark.importers
class TestTextImporterInspect:
    def test_clean_txt_builds_paragraph_document(self) -> None:
        raw = (fixtures_dir / "clean.txt").read_bytes()
        inspection = _inspect("clean.txt", raw)
        assert inspection.status is ImportStatus.OK
        document = inspection.document
        assert document is not None
        assert document.root.node_type is NodeType.DOCUMENT
        non_root = document.nodes[1:]
        assert non_root
        assert all(node.node_type is NodeType.PARAGRAPH for node in non_root)
        surface = raw.decode("utf-8")
        expected_lines = [line for line in surface.split("\n") if line.strip()]
        assert [node.text for node in non_root] == expected_lines

    def test_clean_txt_deterministic_replay(self) -> None:
        raw = (fixtures_dir / "clean.txt").read_bytes()
        first = _inspect("clean.txt", raw)
        second = _inspect("clean.txt", raw)
        assert first.to_json(include_content=True) == second.to_json(include_content=True)

    def test_bom_spans_align_with_surface_text(self) -> None:
        # Regression: the BOM is container framing, not content. The surface
        # view must be BOM-free so node spans index it exactly.
        raw = (fixtures_dir / "bom.txt").read_bytes()
        inspection = _inspect("bom.txt", raw)
        document = inspection.document
        assert document is not None
        assert not document.surface_text.startswith("﻿")
        for node in document.nodes:
            if not node.text:
                continue  # structural nodes (the DOCUMENT root) carry no text
            location = node.source_location
            assert document.surface_text[location.start_offset : location.end_offset] == node.text

    def test_bom_finding_and_bom_stripped(self) -> None:
        raw = (fixtures_dir / "bom.txt").read_bytes()
        inspection = _inspect("bom.txt", raw)
        assert inspection.status is ImportStatus.FINDINGS
        assert any(finding.code == FindingCode.ENCODING_BOM for finding in inspection.findings)
        document = inspection.document
        assert document is not None
        paragraphs = [node for node in document.nodes if node.node_type is NodeType.PARAGRAPH]
        assert paragraphs
        assert not paragraphs[0].text.startswith("\ufeff")

    def test_unicode_control_chars_finding(self) -> None:
        raw = (fixtures_dir / "unicode-controls.txt").read_bytes()
        inspection = _inspect("unicode-controls.txt", raw)
        assert inspection.status is ImportStatus.FINDINGS
        assert any(
            finding.code == FindingCode.UNICODE_CONTROL_CHARS for finding in inspection.findings
        )

    def test_fake_extension_docx_is_quarantined(self) -> None:
        raw = (fixtures_dir / "fake-extension.docx").read_bytes()
        inspection = _inspect("fake-extension.docx", raw)
        assert inspection.status is ImportStatus.QUARANTINED
        assert any(finding.code == FindingCode.MAGIC_MISMATCH for finding in inspection.findings)
        assert inspection.document is None

    def test_crlf_line_ending_inventoried(self) -> None:
        raw = (fixtures_dir / "crlf.txt").read_bytes()
        inspection = _inspect("crlf.txt", raw)
        assert inspection.status is ImportStatus.OK
        unicode_inventory = inspection.unicode
        assert unicode_inventory is not None
        assert unicode_inventory.line_ending == "crlf"

    def test_mixed_line_endings_finding(self) -> None:
        raw = (fixtures_dir / "mixed-endings.txt").read_bytes()
        inspection = _inspect("mixed-endings.txt", raw)
        assert any(
            finding.code == FindingCode.LINE_ENDINGS_MIXED for finding in inspection.findings
        )

    def test_empty_file_finding(self) -> None:
        raw = (fixtures_dir / "empty.txt").read_bytes()
        inspection = _inspect("empty.txt", raw)
        assert inspection.status is ImportStatus.FINDINGS
        assert any(finding.code == FindingCode.STRUCTURE_EMPTY for finding in inspection.findings)
        assert inspection.document is None

    def test_utf16_unsupported(self) -> None:
        raw = (fixtures_dir / "utf16.txt").read_bytes()
        inspection = _inspect("utf16.txt", raw)
        assert inspection.status is ImportStatus.FAILED
        assert any(
            finding.code == FindingCode.ENCODING_UTF16_UNSUPPORTED
            for finding in inspection.findings
        )
        assert inspection.document is None

    def test_invalid_utf8_failing(self) -> None:
        raw = (fixtures_dir / "invalid-utf8.bin").read_bytes()
        inspection = _inspect("invalid-utf8.bin", raw)
        assert inspection.status is ImportStatus.FAILED
        assert any(
            finding.code == FindingCode.ENCODING_INVALID_UTF8 for finding in inspection.findings
        )
        assert inspection.document is None

    def test_size_limit_blocks_parse(self) -> None:
        small_policy = ImportPolicy(lane="source", max_bytes=10)
        raw = (fixtures_dir / "clean.txt").read_bytes()
        assert len(raw) > 10
        inspection = _inspect("clean.txt", raw, small_policy)
        assert inspection.status is ImportStatus.FAILED
        assert any(finding.code == FindingCode.LIMIT_BYTES for finding in inspection.findings)
        assert inspection.document is None

    def test_input_bytes_never_modified(self) -> None:
        path = fixtures_dir / "clean.txt"
        before = path.read_bytes()
        _inspect("clean.txt", before)
        after = path.read_bytes()
        assert after == before

    def test_import_id_is_deterministic(self) -> None:
        clean_raw = (fixtures_dir / "clean.txt").read_bytes()
        crlf_raw = (fixtures_dir / "crlf.txt").read_bytes()
        first = _inspect("clean.txt", clean_raw)
        second = _inspect("clean.txt", clean_raw)
        crlf = _inspect("crlf.txt", crlf_raw)
        assert first.import_id == second.import_id
        assert first.import_id != crlf.import_id
