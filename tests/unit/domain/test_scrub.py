"""Unit tests for metadata scrub and audit."""

from humanhand.domain.scrub import audit_text, scrub_output


class TestScrubOutput:
    def test_clean_text_passes_through(self) -> None:
        text = "This is clean text.\n"
        report = scrub_output(text)
        assert report.cleaned_text == text

    def test_bom_removed(self) -> None:
        text = "﻿Clean text here.\n"
        report = scrub_output(text)
        assert not report.cleaned_text.startswith("﻿")
        assert "Clean text" in report.cleaned_text
        assert report.modifications > 0

    def test_crlf_normalized(self) -> None:
        text = "Line one.\r\nLine two.\r\n"
        report = scrub_output(text)
        assert "\r\n" not in report.cleaned_text
        assert "Line one.\nLine two.\n" in report.cleaned_text

    def test_trailing_whitespace_stripped(self) -> None:
        text = "line with spaces   \nnext line\n"
        report = scrub_output(text)
        for line in report.cleaned_text.split("\n")[:-1]:  # exclude final empty
            assert line == line.rstrip()

    def test_exactly_one_trailing_newline(self) -> None:
        text = "text\n\n\n"
        report = scrub_output(text)
        assert report.cleaned_text.endswith("\n")
        assert not report.cleaned_text.endswith("\n\n")

    def test_no_trailing_newline_added(self) -> None:
        text = "text"
        report = scrub_output(text)
        assert report.cleaned_text == "text\n"

    def test_json_wrapper_removed(self) -> None:
        text = '{"text": "The actual output content here."}'
        report = scrub_output(text)
        assert "The actual output content" in report.cleaned_text
        assert not report.cleaned_text.strip().startswith("{")

    def test_model_tag_removed(self) -> None:
        text = "[Model: gpt-4] The actual content.\n"
        report = scrub_output(text)
        assert "[Model:" not in report.cleaned_text
        assert "The actual content" in report.cleaned_text

    def test_ai_generated_tag_removed(self) -> None:
        text = "[AI Generated] This is the text.\n"
        report = scrub_output(text)
        assert "[AI Generated]" not in report.cleaned_text

    def test_code_fence_removed(self) -> None:
        text = "```\nThe text content here.\n```\n"
        report = scrub_output(text)
        assert "```" not in report.cleaned_text.strip()
        assert "The text content here" in report.cleaned_text

    def test_telemetry_removed(self) -> None:
        text = 'Some text. {"request_id": "abc-123"} more text.\n'
        report = scrub_output(text)
        assert "request_id" not in report.cleaned_text

    def test_multiple_blank_lines_collapsed(self) -> None:
        text = "Para one.\n\n\n\nPara two.\n"
        report = scrub_output(text)
        assert "\n\n\n" not in report.cleaned_text
        assert "Para one.\n\nPara two." in report.cleaned_text

    def test_findings_recorded(self) -> None:
        text = "﻿[Model: test] Content.\r\n"
        report = scrub_output(text)
        assert len(report.findings) > 0
        assert report.modifications > 0

    def test_preserves_legitimate_content(self) -> None:
        text = "This is legitimate prose with [bracketed text] and $50.\n"
        report = scrub_output(text)
        assert "[bracketed text]" in report.cleaned_text
        assert "$50" in report.cleaned_text


class TestAuditText:
    def test_clean_text_no_findings(self) -> None:
        text = "Clean text here.\n"
        report = audit_text(text)
        assert len(report.findings) == 0
        assert report.modifications == 0
        assert report.cleaned_text == text

    def test_bom_detected(self) -> None:
        text = "﻿Text with BOM.\n"
        report = audit_text(text)
        bom_findings = [f for f in report.findings if f.category == "bom"]
        assert len(bom_findings) > 0

    def test_audit_does_not_modify(self) -> None:
        text = "﻿[Model: gpt] Content.\r\n"
        report = audit_text(text)
        assert report.cleaned_text == text
        assert report.modifications == 0

    def test_crlf_detected(self) -> None:
        text = "Line one.\r\nLine two.\r\n"
        report = audit_text(text)
        crlf_findings = [f for f in report.findings if f.category == "crlf"]
        assert len(crlf_findings) > 0

    def test_telemetry_detected(self) -> None:
        text = 'Visible text. {"request_id": "abc-123", "generated_at": "2026-07-06T00:00:00Z"}\n'
        report = audit_text(text)
        telemetry_findings = [f for f in report.findings if f.category == "telemetry"]
        assert len(telemetry_findings) >= 1
