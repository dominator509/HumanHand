"""Integration tests for the Markdown public-document exporter (EP-016)."""

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
    def test_claims_section_present_only_with_claims(self, tmp_path: Path) -> None:
        with_claims = build_public_document(
            title="Report", sections=("Body.",), claims=("Claim A.", "Claim B.")
        )
        output = tmp_path / "report.md"
        MarkdownExporter().export(_request(with_claims, output))

        raw = output.read_bytes()
        # # title, blank line, section paragraph, then the claims section
        # with one "- proposition" bullet paragraph per claim.
        expected = "# Report\n\nBody.\n\n## Claims\n\n- Claim A.\n\n- Claim B.\n"
        assert raw == expected.encode("utf-8")
        assert raw.endswith(b"\n")
        assert not raw.endswith(b"\n\n")  # exactly one trailing newline
        assert not raw.startswith(b"\xef\xbb\xbf")  # no BOM

        without_claims = build_public_document(title="Report", sections=("Body.",), claims=())
        output2 = tmp_path / "report2.md"
        MarkdownExporter().export(_request(without_claims, output2))

        raw2 = output2.read_bytes()
        expected2 = "# Report\n\nBody.\n"
        assert raw2 == expected2.encode("utf-8")
        assert b"## Claims" not in raw2  # claims section omitted without claims

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
