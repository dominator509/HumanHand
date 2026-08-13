"""Integration tests for the TXT public-document exporter (EP-016)."""

from __future__ import annotations

import hashlib
from pathlib import Path

import pytest

from humanhand.domain.export_contract import ExportFormat, ExportRequest
from humanhand.domain.public_document import PublicDocument, build_public_document
from humanhand.infra.exporters.base import ExporterError
from humanhand.infra.exporters.text_exporter import TextExporter


def _request(
    document: PublicDocument, output: Path, fmt: ExportFormat = ExportFormat.TXT
) -> ExportRequest:
    return ExportRequest(format=fmt, output_path=str(output), document=document)


@pytest.mark.importers
class TestTextExporter:
    def test_round_trip_exact_bytes(self, tmp_path: Path) -> None:
        document = build_public_document(
            title="Field Notes",
            sections=("The first section.", "The second section."),
            claims=("Claim one.",),
        )
        output = tmp_path / "notes.txt"
        result = TextExporter().export(_request(document, output))

        raw = output.read_bytes()
        # Title line, blank line, sections joined with blank lines, exactly
        # one trailing newline. Claims are intentionally NOT in TXT.
        expected = "Field Notes\n\nThe first section.\n\nThe second section.\n"
        assert raw == expected.encode("utf-8")
        assert raw.endswith(b"\n")
        assert not raw.endswith(b"\n\n")  # exactly one trailing newline
        assert not raw.startswith(b"\xef\xbb\xbf")  # no BOM
        # Result digest and byte count are of the bytes actually written.
        assert result.sha256 == hashlib.sha256(raw).hexdigest()
        assert result.byte_count == len(raw)
        assert result.byte_count == len(expected)
        assert result.output_path == str(output.resolve())
        assert result.format is ExportFormat.TXT

    def test_empty_document_violation_surfaced(self, tmp_path: Path) -> None:
        document = build_public_document(title="", sections=(), claims=())
        with pytest.raises(ExporterError):
            TextExporter().export_bytes(document)

    def test_claims_only_document_refused_for_txt(self, tmp_path: Path) -> None:
        # TXT is content-only; a claims-only document has nothing to say.
        document = build_public_document(title="", sections=(), claims=("Claim one.",))
        with pytest.raises(ExporterError):
            TextExporter().export_bytes(document)

    def test_refuses_humanhand_output_path(self, tmp_path: Path) -> None:
        document = build_public_document(title="T", sections=("s",), claims=())
        output = tmp_path / ".humanhand" / "project" / "notes.txt"
        with pytest.raises(ExporterError):
            TextExporter().export(_request(document, output))
        assert not output.exists()

    def test_wrong_format_request_rejected(self, tmp_path: Path) -> None:
        document = build_public_document(title="T", sections=("s",), claims=())
        output = tmp_path / "notes.md"
        with pytest.raises(ExporterError):
            TextExporter().export(_request(document, output, fmt=ExportFormat.MARKDOWN))
