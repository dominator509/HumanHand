"""Artifact audit findings (SPEC-013, blueprint 11.4/11.5).

DOCX, PDF, TXT, and Markdown artifacts are audited independently; each
audit produces findings and a pass/fail status. An audit fails when any
ERROR-severity finding exists; INFO and WARNING findings alone never block
a clean-artifact designation.
"""

from __future__ import annotations

from dataclasses import dataclass
from enum import StrEnum

ARTIFACT_AUDIT_SCHEMA_VERSION = 1
_SCHEMA_NAME = "artifact-audit"


class ArtifactFindingSeverity(StrEnum):
    """Severity of one artifact audit finding."""

    INFO = "info"
    WARNING = "warning"
    ERROR = "error"


@dataclass(frozen=True)
class ArtifactFinding:
    """One artifact audit finding."""

    code: str
    severity: ArtifactFindingSeverity
    description: str
    evidence: str = ""


class ArtifactAuditStatus(StrEnum):
    """Outcome of one artifact audit."""

    PASS = "pass"  # nosec B105 - audit status enum, not a credential
    FAIL = "fail"


@dataclass(frozen=True)
class ArtifactAuditReport:
    """Independent audit report for one exported artifact."""

    format: str
    status: ArtifactAuditStatus
    findings: tuple[ArtifactFinding, ...]

    def to_payload(self) -> dict[str, object]:
        """Render the report as a stable JSON-ready payload."""
        return {
            "schema": _SCHEMA_NAME,
            "schema_version": ARTIFACT_AUDIT_SCHEMA_VERSION,
            "format": self.format,
            "status": self.status.value,
            "findings": [
                {
                    "code": finding.code,
                    "severity": finding.severity.value,
                    "description": finding.description,
                    "evidence": finding.evidence,
                }
                for finding in self.findings
            ],
        }


def classify_audit(findings: tuple[ArtifactFinding, ...]) -> ArtifactAuditStatus:
    """Classify findings into a pass/fail status.

    Any ERROR-severity finding fails the audit; INFO and WARNING findings
    alone pass. This matches SPEC-013: prohibited metadata or content
    mismatch (error-class problems) blocks a clean-artifact designation.
    """
    if any(finding.severity is ArtifactFindingSeverity.ERROR for finding in findings):
        return ArtifactAuditStatus.FAIL
    return ArtifactAuditStatus.PASS
