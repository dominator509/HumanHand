"""Integration tests for content-only Markdown public export."""

from __future__ import annotations

from pathlib import Path

import pytest

from humanhand.domain.export_contract import ExportFormat, ExportRequest
from humanhand.domain.public_document import PublicDocument, build_public_document
from humanhand.infra.exporters.base import ExporterError
from humanhand.infra.exporters.markdown_exporter import MarkdownExporter


def _request(document: PublicDocument, output: Path) -> ExportRequest:
    return ExportRequest(format=ExportFormat.MARKDOWN, output_path=str(output), document=document)


@pytest.mark.importers
class TestMarkdownExporter:
    def test_internal_claims_never_enter_public_markdown(self, tmp_path: Path) -> None:
        document = build_public_document(
            title="Report",
            sections=("Body.",),
            claims=("Internal claim A.", "Internal claim B."),
        )
        output = tmp_path / "report.md"
        MarkdownExporter().export(_request(document, output))

        raw = output.read_bytes()
        assert raw == b"# Report\n\nBody.\n"
        assert b"## Claims" not in raw
        assert b"Internal claim" not in raw
        assert raw.endswith(b"\n")
        assert not raw.endswith(b"\n\n")
        assert not raw.startswith(b"\xef\xbb\xbf")

    def test_empty_document_violation_surfaced(self, tmp_path: Path) -> None:
        document = build_public_document(title="", sections=(), claims=())
        with pytest.raises(ExporterError):
            MarkdownExporter().export_bytes(document)

    def test_refuses_humanhand_output_path(self, tmp_path: Path) -> None:
        document = build_public_document(title="Report", sections=("Body.",), claims=())
        output = tmp_path / ".humanhand" / "report.md"
        with pytest.raises(ExporterError):
            MarkdownExporter().export(_request(document, output))
        assert not output.exists()
