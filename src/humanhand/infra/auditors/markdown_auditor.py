"""Markdown artifact auditor (EP-016).

Inherits every TXT-lane check from :class:`TextAuditor` (UTF-8 no BOM,
one trailing newline, no CR, ordered section containment, prohibited
metadata scan) and adds the Markdown-specific checks:

- a ``# `` title heading is present,
- a ``## Claims`` section is present iff ``expected.claims`` is
  non-empty (skipped when no expected document is supplied),
- no raw HTML active content (``<script`` or ``<iframe``).
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

from .base import AuditCode, build_report, missing_claim_findings, read_file_bytes
from .text_auditor import TextAuditor

# Raw HTML tags that must never appear in a public Markdown artifact.
ACTIVE_CONTENT_PATTERNS = (
    re.compile(r"<(?:script|iframe|object|embed|link|img)\b", re.IGNORECASE),
    re.compile(r"\bon[a-z]+\s*=", re.IGNORECASE),
    re.compile(r"(?:javascript|vbscript|data):", re.IGNORECASE),
    re.compile(r"!?\[[^\]]*\]\(\s*(?:https?:)?//", re.IGNORECASE),
)


class MarkdownAuditor(TextAuditor):
    """Independent auditor for Markdown artifacts (format ``md``)."""

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
        if expected is not None:
            if title_headings and expected.title and f"# {expected.title}" not in title_headings:
                findings.append(
                    ArtifactFinding(
                        code=AuditCode.TITLE_MISSING,
                        severity=ArtifactFindingSeverity.ERROR,
                        description="Expected title heading is missing from the Markdown artifact",
                        evidence="heading=expected_title",
                    )
                )
            has_claims = bool(expected.claims)
            claims_present = "## Claims" in text
            if has_claims and not claims_present:
                findings.append(
                    ArtifactFinding(
                        code=AuditCode.CLAIMS_HEADING,
                        severity=ArtifactFindingSeverity.ERROR,
                        description="'## Claims' section missing but the document declares claims",
                        evidence="claims_expected=true",
                    )
                )
            elif not has_claims and claims_present:
                findings.append(
                    ArtifactFinding(
                        code=AuditCode.CLAIMS_HEADING,
                        severity=ArtifactFindingSeverity.ERROR,
                        description=(
                            "'## Claims' section present but the document declares no claims"
                        ),
                        evidence="claims_expected=false",
                    )
                )
            if claims_present:
                findings.extend(missing_claim_findings(text, expected))
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
