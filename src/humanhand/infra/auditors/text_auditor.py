"""Plain-text (TXT) artifact auditor (EP-016).

Independent audit path: the auditor re-reads the artifact bytes from disk
(``base.read_file_bytes``) and applies byte-level and text-level checks;
it never reuses exporter in-memory output.

Checks (blueprint 11.4 TXT guarantee):
(a) UTF-8 with no BOM,
(b) exactly one trailing newline,
(c) no CR bytes (LF-only line endings),
(d) every expected section text present as a substring, in order,
(e) prohibited internal-metadata term scan.
"""

from __future__ import annotations

from pathlib import Path

from humanhand.domain.artifact_findings import (
    ArtifactAuditReport,
    ArtifactFinding,
    ArtifactFindingSeverity,
)
from humanhand.domain.public_document import PublicDocument

from .base import (
    AuditCode,
    BaseAuditor,
    build_report,
    decode_text_findings,
    missing_section_findings,
    prohibited_term_findings,
    read_file_bytes,
)


class TextAuditor(BaseAuditor):
    """Independent auditor for plain-text artifacts (format ``txt``)."""

    format = "txt"

    def audit_file(
        self, path: str | Path, *, expected: PublicDocument | None
    ) -> ArtifactAuditReport:
        raw = read_file_bytes(path)
        text, findings = self._text_findings(raw, expected)
        return build_report(self.format, findings)

    def _text_findings(
        self, raw: bytes, expected: PublicDocument | None
    ) -> tuple[str | None, tuple[ArtifactFinding, ...]]:
        """Run all TXT-lane checks. Returns ``(text, findings)``; ``text``
        is ``None`` when the bytes are not decodable UTF-8."""
        text, findings = decode_text_findings(raw)
        finding_list: list[ArtifactFinding] = list(findings)
        if b"\r" in raw:
            finding_list.append(
                ArtifactFinding(
                    code=AuditCode.LINE_ENDINGS_CR,
                    severity=ArtifactFindingSeverity.ERROR,
                    description="CR byte found; artifacts must use LF-only line endings",
                    evidence="byte=0x0d",
                )
            )
        if text is not None:
            self._trailing_newline_findings(raw, finding_list)
            finding_list.extend(prohibited_term_findings(text))
            if expected is not None:
                finding_list.extend(missing_section_findings(text, expected, ordered=True))
        return text, tuple(finding_list)

    @staticmethod
    def _trailing_newline_findings(raw: bytes, findings: list[ArtifactFinding]) -> None:
        if not raw.endswith(b"\n"):
            findings.append(
                ArtifactFinding(
                    code=AuditCode.TRAILING_NEWLINE_MISSING,
                    severity=ArtifactFindingSeverity.ERROR,
                    description="Artifact must end with exactly one newline; none found",
                    evidence="tail_missing",
                )
            )
        elif raw.endswith(b"\n\n"):
            findings.append(
                ArtifactFinding(
                    code=AuditCode.TRAILING_NEWLINE_EXTRA,
                    severity=ArtifactFindingSeverity.ERROR,
                    description="Artifact must end with exactly one newline; extra found",
                    evidence="tail_extra",
                )
            )
