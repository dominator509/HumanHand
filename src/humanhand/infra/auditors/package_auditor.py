"""Package auditor for unknown-extension artifacts (EP-016).

The registry routes file extensions it does not recognize to this
auditor, which produces ONE report for the artifact (format ``any``) by
concatenating:

- the unicode-lane audit results (the format-agnostic auditor),
- a WARNING that the file extension is unknown (``audit.format.unknown``).

The combined findings are classified with ``classify_audit``: the
unknown-extension WARNING alone passes, any ERROR (e.g. invalid UTF-8
or a control character) fails the audit.
"""

from __future__ import annotations

from pathlib import Path

from humanhand.domain.artifact_findings import (
    ArtifactAuditReport,
    ArtifactFinding,
    ArtifactFindingSeverity,
)
from humanhand.domain.public_document import PublicDocument

from .base import AuditCode, BaseAuditor, build_report
from .unicode_auditor import UnicodeAuditor


class PackageAuditor(BaseAuditor):
    """Combined unicode + unknown-format auditor (format ``any``)."""

    format = "any"

    def audit_file(
        self, path: str | Path, *, expected: PublicDocument | None
    ) -> ArtifactAuditReport:
        unicode_report = UnicodeAuditor().audit_file(path, expected=expected)
        findings: list[ArtifactFinding] = list(unicode_report.findings)
        findings.append(
            ArtifactFinding(
                code=AuditCode.FORMAT_UNKNOWN,
                severity=ArtifactFindingSeverity.WARNING,
                description="File extension is not a recognized artifact format",
                evidence=f"ext={Path(path).suffix}",
            )
        )
        return build_report(self.format, tuple(findings))
