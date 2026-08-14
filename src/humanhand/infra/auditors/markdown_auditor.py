"""Content-only Markdown artifact auditor (EP-019).

Inherits TXT-lane checks and verifies the approved title, absence of active or
external Markdown content, and absence of an internal ``Claims`` appendix.
"""

from __future__ import annotations

import re
from pathlib import Path

from humanhand.domain.artifact_findings import (
    ArtifactAuditReport,
    ArtifactFinding,
    ArtifactFindingSeverity,
)
from humanhand.domain.public_document import PublicDocument

from .base import AuditCode, build_report, read_file_bytes
from .text_auditor import TextAuditor

ACTIVE_CONTENT_PATTERNS = (
    re.compile(r"<(?:script|iframe|object|embed|link|img)\b", re.IGNORECASE),
    re.compile(r"\bon[a-z]+\s*=", re.IGNORECASE),
    re.compile(r"(?:javascript|vbscript|data):", re.IGNORECASE),
    re.compile(r"!?\[[^\]]*\]\(\s*(?:https?:)?//", re.IGNORECASE),
)


class MarkdownAuditor(TextAuditor):
    """Independent auditor for content-only Markdown artifacts."""

    format = "md"

    def audit_file(
        self, path: str | Path, *, expected: PublicDocument | None
    ) -> ArtifactAuditReport:
        raw = read_file_bytes(path)
        text, base_findings = self._text_findings(raw, expected)
        findings: list[ArtifactFinding] = list(base_findings)
        if text is not None:
            findings.extend(self._markdown_findings(text, expected))
        return build_report(self.format, tuple(findings))

    def _markdown_findings(
        self, text: str, expected: PublicDocument | None
    ) -> tuple[ArtifactFinding, ...]:
        findings: list[ArtifactFinding] = []
        title_headings = [line for line in text.splitlines() if line.startswith("# ")]
        if not title_headings:
            findings.append(
                ArtifactFinding(
                    code=AuditCode.HEADING_TITLE,
                    severity=ArtifactFindingSeverity.ERROR,
                    description="No '# ' title heading present in the Markdown artifact",
                    evidence="heading=title",
                )
            )
        if expected is not None and (
            title_headings and expected.title and f"# {expected.title}" not in title_headings
        ):
            findings.append(
                ArtifactFinding(
                    code=AuditCode.TITLE_MISSING,
                    severity=ArtifactFindingSeverity.ERROR,
                    description="Expected title heading is missing from the Markdown artifact",
                    evidence="heading=expected_title",
                )
            )
        if "## Claims" in text:
            findings.append(
                ArtifactFinding(
                    code=AuditCode.CLAIMS_HEADING,
                    severity=ArtifactFindingSeverity.ERROR,
                    description="Internal claims appendix must not appear in public Markdown",
                    evidence="heading=claims",
                )
            )
        for pattern in ACTIVE_CONTENT_PATTERNS:
            if pattern.search(text):
                findings.append(
                    ArtifactFinding(
                        code=AuditCode.HTML_ACTIVE_CONTENT,
                        severity=ArtifactFindingSeverity.ERROR,
                        description="Active or external Markdown content is present",
                        evidence=f"pattern={pattern.pattern}",
                    )
                )
        return tuple(findings)
