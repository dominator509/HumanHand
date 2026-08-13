"""Shared contracts for independent artifact auditors (EP-016).

Every auditor re-reads the artifact bytes from disk on every audit and
never touches exporter in-memory state, satisfying the blueprint's
independent-check rule (section 11: "Exporter and auditor implementations
must not merely call the same helper and declare success").

The audit domain contract lives in ``humanhand.domain.artifact_findings``
and ``humanhand.domain.public_document`` (landed with EP-016):
- ``ArtifactFinding(code, severity, description, evidence="")``,
- ``ArtifactAuditReport(format, status, findings)``,
- ``classify_audit`` fails the audit iff any ERROR-severity finding
  exists; INFO and WARNING findings alone pass (SPEC-013).
"""

from __future__ import annotations

import re
from abc import ABC, abstractmethod
from pathlib import Path

from humanhand.domain.artifact_findings import (
    ArtifactAuditReport,
    ArtifactFinding,
    ArtifactFindingSeverity,
    classify_audit,
)
from humanhand.domain.public_document import PublicDocument
from humanhand.infra.files import FileIOError
from humanhand.infra.files import read_bytes as _read_bytes

# Terms that must never appear in a public artifact (blueprint 11.2/11.3:
# no internal identifiers, no model names, no API envelopes). The scan is
# case-insensitive substring matching on the decoded artifact text.
PROHIBITED_METADATA_TERMS = ("project_id", "claim_id", "block_id", "api_key", "model:")

_WHITESPACE_RUN = re.compile(r"\s+")


class AuditCode:
    """Stable audit finding codes. Never change an existing code string."""

    UTF8_BOM = "audit.utf8.bom"
    UTF8_DECODE = "audit.utf8.decode"
    TRAILING_NEWLINE_MISSING = "audit.trailing_newline.missing"
    TRAILING_NEWLINE_EXTRA = "audit.trailing_newline.extra"
    LINE_ENDINGS_CR = "audit.line_endings.cr"
    METADATA_PROHIBITED = "audit.metadata.prohibited"
    CONTENT_MISSING = "audit.content.missing"
    TITLE_MISSING = "audit.title.missing"
    HEADING_TITLE = "audit.heading.title"
    CLAIMS_HEADING = "audit.claims.heading"
    HTML_ACTIVE_CONTENT = "audit.html.active_content"
    UNICODE_NOT_NFC = "audit.unicode.not_nfc"
    UNICODE_CONTROL_CHARS = "audit.unicode.control_chars"
    UNICODE_SURROGATES = "audit.unicode.surrogates"
    UNICODE_INVALID_UTF8 = "audit.unicode.invalid_utf8"
    DOCX_ZIP_INVALID = "audit.docx.zip_invalid"
    DOCX_DOCUMENT_XML_MALFORMED = "audit.docx.document_xml_malformed"
    DOCX_PART_UNREADABLE = "audit.docx.part_unreadable"
    DOCX_METADATA_PROHIBITED = "audit.docx.metadata.prohibited"
    DOCX_MACROS = "audit.docx.macros"
    DOCX_EXTERNAL_RELATIONSHIP = "audit.docx.external_relationship"
    DOCX_HIDDEN_CONTENT = "audit.docx.hidden_content"
    PDF_OPEN_FAILED = "audit.pdf.open_failed"
    PDF_EXTRACT_FAILED = "audit.pdf.extract_failed"
    PDF_JAVASCRIPT = "audit.pdf.javascript"
    PDF_ACTIVE_CONTENT = "audit.pdf.active_content"
    FORMAT_UNKNOWN = "audit.format.unknown"


class AuditorError(Exception):
    """Raised when an artifact cannot be read or opened for auditing."""


class BaseAuditor(ABC):
    """Common audit surface; each subclass owns one artifact format."""

    format: str = "any"

    @abstractmethod
    def audit_file(
        self, path: str | Path, *, expected: PublicDocument | None
    ) -> ArtifactAuditReport:
        """Audit the artifact bytes at ``path`` independently.

        Args:
            path: Path of the artifact file on disk.
            expected: Optional public document the artifact should match.
        """


def read_file_bytes(path: str | Path) -> bytes:
    """Read artifact bytes with the repository strict-read conventions.

    ``humanhand.infra.files.read_bytes`` performs the existence and
    regular-file checks and raises ``FileIOError`` on failure; that error
    is translated to :class:`AuditorError` per the auditor contract.
    """
    try:
        return _read_bytes(path)
    except FileIOError as exc:
        raise AuditorError(str(exc)) from exc


def build_report(format_name: str, findings: tuple[ArtifactFinding, ...]) -> ArtifactAuditReport:
    """Build an audit report whose status comes from ``classify_audit``."""
    return ArtifactAuditReport(
        format=format_name, status=classify_audit(findings), findings=findings
    )


def decode_text_findings(raw: bytes) -> tuple[str | None, tuple[ArtifactFinding, ...]]:
    """UTF-8 rules check: no BOM, strict decode. Returns ``(text, findings)``.

    On decode failure ``text`` is ``None`` and the findings carry an ERROR
    so the artifact fails closed.
    """
    findings: list[ArtifactFinding] = []
    if raw.startswith(b"\xef\xbb\xbf"):
        findings.append(
            ArtifactFinding(
                code=AuditCode.UTF8_BOM,
                severity=ArtifactFindingSeverity.ERROR,
                description="UTF-8 BOM detected; public artifacts must have no BOM",
                evidence="bom=utf8",
            )
        )
    try:
        text = raw.decode("utf-8", errors="strict")
    except UnicodeDecodeError as exc:
        findings.append(
            ArtifactFinding(
                code=AuditCode.UTF8_DECODE,
                severity=ArtifactFindingSeverity.ERROR,
                description="Artifact bytes are not valid UTF-8",
                evidence=f"reason={exc.reason}",
            )
        )
        return None, tuple(findings)
    return text, tuple(findings)


def prohibited_term_findings(text: str) -> tuple[ArtifactFinding, ...]:
    """Scan decoded artifact text for prohibited internal-metadata terms.

    Independent scan: case-insensitive substring matching over the decoded
    text re-read from disk. One ERROR finding per distinct term found.
    """
    lowered = text.lower()
    findings: list[ArtifactFinding] = []
    for term in PROHIBITED_METADATA_TERMS:
        if term in lowered:
            findings.append(
                ArtifactFinding(
                    code=AuditCode.METADATA_PROHIBITED,
                    severity=ArtifactFindingSeverity.ERROR,
                    description=f"Prohibited internal metadata term present: {term}",
                    evidence=f"term={term}",
                )
            )
    return tuple(findings)


def collapse_whitespace(text: str) -> str:
    """Reduce every whitespace run to a single space.

    Used for PDF containment: pypdf page-boundary whitespace differences
    must not break substring matching (documented rule in pdf_auditor).
    """
    return _WHITESPACE_RUN.sub(" ", text)


def missing_section_findings(
    text: str,
    expected: PublicDocument,
    *,
    ordered: bool,
    collapse: bool = False,
) -> tuple[ArtifactFinding, ...]:
    """Report expected section texts absent from the artifact text.

    ``ordered=True`` requires the sections to appear as substrings in
    order: a section that only appears earlier than its predecessor is
    reported missing from its expected position. ``collapse=True``
    compares whitespace-collapsed forms (the PDF rule; see
    :func:`collapse_whitespace`).
    """
    haystack = collapse_whitespace(text) if collapse else text
    needles = list(expected.sections)
    findings: list[ArtifactFinding] = []
    search_from = 0
    for index, needle in enumerate(needles):
        if collapse:
            needle = collapse_whitespace(needle)
        position = haystack.find(needle, search_from) if ordered else haystack.find(needle)
        if position == -1:
            findings.append(
                ArtifactFinding(
                    code=AuditCode.CONTENT_MISSING,
                    severity=ArtifactFindingSeverity.ERROR,
                    description="Expected section text is missing from the artifact",
                    evidence=f"section_index={index}",
                )
            )
        elif ordered:
            search_from = position + len(needle)
    return tuple(findings)


def missing_claim_findings(
    text: str, expected: PublicDocument, *, collapse: bool = False
) -> tuple[ArtifactFinding, ...]:
    """Report approved public claims absent from formats that render them."""
    haystack = collapse_whitespace(text) if collapse else text
    findings: list[ArtifactFinding] = []
    for index, claim in enumerate(expected.claims):
        needle = collapse_whitespace(claim) if collapse else claim
        if needle not in haystack:
            findings.append(
                ArtifactFinding(
                    code=AuditCode.CONTENT_MISSING,
                    severity=ArtifactFindingSeverity.ERROR,
                    description="Expected claim text is missing from the artifact",
                    evidence=f"claim_index={index}",
                )
            )
    return tuple(findings)
