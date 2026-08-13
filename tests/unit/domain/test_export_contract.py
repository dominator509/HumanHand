"""Unit tests for the export contract."""

from __future__ import annotations

import pytest

from humanhand.domain.export_contract import (
    ExportFormat,
    ExportRequest,
    validate_export_request,
)
from humanhand.domain.public_document import PublicDocument, build_public_document


def _empty_doc() -> PublicDocument:
    return build_public_document(title="", sections=(), claims=())


def _content_doc() -> PublicDocument:
    return build_public_document(title="Report", sections=("Body",), claims=("Fact one.",))


class TestExportFormat:
    def test_format_enum_values(self) -> None:
        assert [fmt.value for fmt in ExportFormat] == ["txt", "md", "docx", "pdf"]

    def test_enum_members_parse_from_values(self) -> None:
        assert ExportFormat("txt") is ExportFormat.TXT
        assert ExportFormat("md") is ExportFormat.MARKDOWN
        assert ExportFormat("docx") is ExportFormat.DOCX
        assert ExportFormat("pdf") is ExportFormat.PDF


class TestValidateExportRequest:
    def test_valid_request_has_no_violations(self) -> None:
        request = ExportRequest(
            format=ExportFormat.TXT, document=_content_doc(), output_path="out/report.txt"
        )
        assert validate_export_request(request) == ()

    def test_empty_document_is_a_violation(self) -> None:
        request = ExportRequest(
            format=ExportFormat.MARKDOWN, document=_empty_doc(), output_path="out/report.md"
        )
        assert validate_export_request(request) == ("empty_document",)

    def test_output_path_ending_in_humanhand_is_unsafe(self) -> None:
        request = ExportRequest(
            format=ExportFormat.TXT, document=_content_doc(), output_path="out/report.humanhand"
        )
        assert validate_export_request(request) == (
            "unsafe_output_path",
            "format_extension_mismatch",
        )

    def test_internal_path_equality_is_unsafe(self) -> None:
        for internal in (".cache/humanhand", ".humanhand/style-vault"):
            request = ExportRequest(
                format=ExportFormat.TXT, document=_content_doc(), output_path=internal
            )
            assert validate_export_request(request) == (
                "unsafe_output_path",
                "format_extension_mismatch",
            )

    @pytest.mark.parametrize(
        "path",
        [
            "project/.humanhand/report.txt",
            r"project\.HUMANHAND\report.txt",
            "x/.cache/humanhand/out.txt",
        ],
    )
    def test_any_path_inside_private_storage_is_unsafe(self, path: str) -> None:
        request = ExportRequest(format=ExportFormat.TXT, document=_content_doc(), output_path=path)
        assert validate_export_request(request) == ("unsafe_output_path",)

    def test_both_violations_are_reported_in_order(self) -> None:
        request = ExportRequest(
            format=ExportFormat.PDF, document=_empty_doc(), output_path="out/report.humanhand"
        )
        assert validate_export_request(request) == (
            "empty_document",
            "unsafe_output_path",
            "format_extension_mismatch",
        )

    def test_format_must_match_output_extension(self) -> None:
        request = ExportRequest(
            format=ExportFormat.PDF, document=_content_doc(), output_path="out/report.txt"
        )
        assert validate_export_request(request) == ("format_extension_mismatch",)
