"""Unicode-normalization artifact auditor (EP-016).

Independent audit path: re-reads artifact bytes from disk and decodes
them with strict UTF-8. Checks (format ``any``, usable for any artifact):

- NFC normalization: a non-NFC artifact is a WARNING (normalization is
  visually invisible but breaks byte-level verification guarantees),
- control characters (Unicode category ``Cc``, excluding tab/LF/CR) are
  an ERROR (they are invisible metadata channels),
- surrogate code points are an ERROR (they cannot appear in any valid
  UTF-8 stream; the scan is exposed for text already decoded elsewhere).

Note: surrogate code points are unreachable through a strict UTF-8 file
decode (their bytes are rejected as invalid UTF-8), so the surrogate
branch is exercised through :func:`scan_unicode_text` directly.
"""

from __future__ import annotations

import unicodedata
from pathlib import Path

from humanhand.domain.artifact_findings import (
    ArtifactAuditReport,
    ArtifactFinding,
    ArtifactFindingSeverity,
)
from humanhand.domain.public_document import PublicDocument

from .base import AuditCode, BaseAuditor, build_report, read_file_bytes

# Control characters that are allowed in a public artifact (they are
# ordinary formatting, not metadata channels).
_ALLOWED_CONTROL_CHARS = frozenset(("\t", "\n", "\r"))


class UnicodeAuditor(BaseAuditor):
    """Independent auditor for unicode normalization (format ``any``)."""

    format = "any"

    def audit_file(
        self, path: str | Path, *, expected: PublicDocument | None
    ) -> ArtifactAuditReport:
        raw = read_file_bytes(path)
        try:
            text = raw.decode("utf-8", errors="strict")
        except UnicodeDecodeError as exc:
            return build_report(
                self.format,
                (
                    ArtifactFinding(
                        code=AuditCode.UNICODE_INVALID_UTF8,
                        severity=ArtifactFindingSeverity.ERROR,
                        description="Artifact bytes are not valid UTF-8",
                        evidence=f"reason={exc.reason}",
                    ),
                ),
            )
        return build_report(self.format, self.scan_unicode_text(text))

    @staticmethod
    def scan_unicode_text(text: str) -> tuple[ArtifactFinding, ...]:
        """Scan decoded text for NFC, control-character, and surrogate issues.

        Public so callers that already hold decoded text (e.g. the package
        auditor) can run the same checks without re-reading the file.
        """
        findings: list[ArtifactFinding] = []
        if not unicodedata.is_normalized("NFC", text):
            findings.append(
                ArtifactFinding(
                    code=AuditCode.UNICODE_NOT_NFC,
                    severity=ArtifactFindingSeverity.WARNING,
                    description="Text is not NFC-normalized",
                    evidence="normalization=nfc",
                )
            )
        first_control: int | None = None
        first_surrogate: int | None = None
        for index, char in enumerate(text):
            if char in _ALLOWED_CONTROL_CHARS:
                continue
            category = unicodedata.category(char)
            if category == "Cc" and first_control is None:
                first_control = index
            code_point = ord(char)
            if 0xD800 <= code_point <= 0xDFFF and first_surrogate is None:
                first_surrogate = index
        if first_control is not None:
            findings.append(
                ArtifactFinding(
                    code=AuditCode.UNICODE_CONTROL_CHARS,
                    severity=ArtifactFindingSeverity.ERROR,
                    description="Control characters (category Cc) present in the artifact",
                    evidence=f"first_offset={first_control}",
                )
            )
        if first_surrogate is not None:
            findings.append(
                ArtifactFinding(
                    code=AuditCode.UNICODE_SURROGATES,
                    severity=ArtifactFindingSeverity.ERROR,
                    description="Surrogate code points present; never valid in UTF-8 text",
                    evidence=f"first_offset={first_surrogate}",
                )
            )
        return tuple(findings)
