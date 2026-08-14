"""Independent metadata-free DOCX artifact auditor (EP-019).

The auditor re-reads the artifact from disk, validates the ZIP/XML structure,
extracts visible text independently, and fails closed on any properties,
custom XML, revisions, comments, hidden text, external relationships, macros,
embedded objects, headers/footers, or prohibited internal identifiers.
"""

from __future__ import annotations

import html
import io
import zipfile
from pathlib import Path
from typing import Any

from humanhand.domain.artifact_findings import (
    ArtifactAuditReport,
    ArtifactFinding,
    ArtifactFindingSeverity,
)
from humanhand.domain.import_policy import ImportPolicy
from humanhand.domain.public_document import PublicDocument
from humanhand.infra.importers.container_utils import (
    evidence_name,
    parse_xml_bounded,
    read_zip_entry_bounded,
)

from .base import (
    PROHIBITED_METADATA_TERMS,
    AuditCode,
    BaseAuditor,
    build_report,
    missing_section_findings,
    read_file_bytes,
)

MAIN_DOCUMENT_PART = "word/document.xml"
DOCX_METADATA_TERMS = PROHIBITED_METADATA_TERMS
_MACRO_PART_MARKERS = ("vbaproject", "vbadata")
_FORBIDDEN_PART_PREFIXES = (
    "docprops/",
    "customxml/",
    "word/comments",
    "word/people",
    "word/embeddings/",
    "word/header",
    "word/footer",
    "word/glossary/",
)
_FORBIDDEN_XML_MARKERS = (
    b"<w:ins",
    b"<w:del",
    b"<w:movefrom",
    b"<w:moveto",
    b"<w:commentrange",
    b"<w:commentreference",
    b"<w:altchunk",
    b"<w:object",
    b"<w:control",
    b"w:vanish",
    b"w:webhidden",
)


class DocxAuditor(BaseAuditor):
    """Independent auditor for metadata-free DOCX artifacts."""

    format = "docx"

    def audit_file(
        self, path: str | Path, *, expected: PublicDocument | None
    ) -> ArtifactAuditReport:
        raw = read_file_bytes(path)
        try:
            archive = zipfile.ZipFile(io.BytesIO(raw))
        except zipfile.BadZipFile as exc:
            return build_report(
                self.format,
                (
                    ArtifactFinding(
                        code=AuditCode.DOCX_ZIP_INVALID,
                        severity=ArtifactFindingSeverity.ERROR,
                        description="Artifact is not a valid ZIP/DOCX package",
                        evidence=f"reason={type(exc).__name__}",
                    ),
                ),
            )
        findings: list[ArtifactFinding] = []
        try:
            with archive:
                self._collect_findings(archive, expected, findings)
        except (zipfile.BadZipFile, zipfile.LargeZipFile, RuntimeError) as exc:
            findings.append(
                ArtifactFinding(
                    code=AuditCode.DOCX_ZIP_INVALID,
                    severity=ArtifactFindingSeverity.ERROR,
                    description="Package became unreadable during the audit",
                    evidence=f"reason={type(exc).__name__}",
                )
            )
        return build_report(self.format, tuple(findings))

    def _collect_findings(
        self,
        archive: zipfile.ZipFile,
        expected: PublicDocument | None,
        findings: list[ArtifactFinding],
    ) -> None:
        policy = ImportPolicy()
        names = archive.namelist()
        for name in names:
            if name.endswith("/"):
                continue
            lowered = name.lower()
            if any(lowered.startswith(prefix) for prefix in _FORBIDDEN_PART_PREFIXES):
                findings.append(
                    ArtifactFinding(
                        code=AuditCode.DOCX_METADATA_PROHIBITED,
                        severity=ArtifactFindingSeverity.ERROR,
                        description="Prohibited DOCX package part detected",
                        evidence=f"part={evidence_name(name)}",
                    )
                )
            if any(marker in lowered for marker in _MACRO_PART_MARKERS):
                findings.append(
                    ArtifactFinding(
                        code=AuditCode.DOCX_MACROS,
                        severity=ArtifactFindingSeverity.ERROR,
                        description="VBA macro part detected in the package",
                        evidence=f"part={evidence_name(name)}",
                    )
                )

        document_text: str | None = None
        if MAIN_DOCUMENT_PART in names:
            document_text = self._read_main_document(archive, policy, findings)
        else:
            findings.append(
                ArtifactFinding(
                    code=AuditCode.DOCX_DOCUMENT_XML_MALFORMED,
                    severity=ArtifactFindingSeverity.ERROR,
                    description="Main document part is missing from the package",
                    evidence=f"part={MAIN_DOCUMENT_PART}",
                )
            )
        self._scan_parts(archive, policy, names, findings)
        if expected is not None and document_text is not None:
            if expected.title and expected.title not in document_text:
                findings.append(
                    ArtifactFinding(
                        code=AuditCode.TITLE_MISSING,
                        severity=ArtifactFindingSeverity.ERROR,
                        description="Expected title is missing from the DOCX document text",
                        evidence="part=word/document.xml",
                    )
                )
            findings.extend(missing_section_findings(document_text, expected, ordered=True))

    def _read_main_document(
        self,
        archive: zipfile.ZipFile,
        policy: ImportPolicy,
        findings: list[ArtifactFinding],
    ) -> str | None:
        part_bytes, read_findings = read_zip_entry_bounded(archive, MAIN_DOCUMENT_PART, policy)
        if read_findings:
            findings.append(
                ArtifactFinding(
                    code=AuditCode.DOCX_DOCUMENT_XML_MALFORMED,
                    severity=ArtifactFindingSeverity.ERROR,
                    description="Main document part could not be read",
                    evidence=f"part={MAIN_DOCUMENT_PART}, reason={read_findings[0].code}",
                )
            )
            return None
        root, parse_findings = parse_xml_bounded(part_bytes, policy, MAIN_DOCUMENT_PART)
        if root is None or parse_findings:
            findings.append(
                ArtifactFinding(
                    code=AuditCode.DOCX_DOCUMENT_XML_MALFORMED,
                    severity=ArtifactFindingSeverity.ERROR,
                    description="Main document part is not well-formed XML",
                    evidence=(
                        f"part={MAIN_DOCUMENT_PART}, reason="
                        f"{parse_findings[0].code if parse_findings else 'unparsable'}"
                    ),
                )
            )
            return None
        return _document_text(root)

    def _scan_parts(
        self,
        archive: zipfile.ZipFile,
        policy: ImportPolicy,
        names: list[str],
        findings: list[ArtifactFinding],
    ) -> None:
        for name in names:
            if name.endswith("/"):
                continue
            part_bytes, read_findings = read_zip_entry_bounded(archive, name, policy)
            if read_findings:
                findings.append(
                    ArtifactFinding(
                        code=AuditCode.DOCX_PART_UNREADABLE,
                        severity=ArtifactFindingSeverity.ERROR,
                        description="Package part could not be read; audit incomplete",
                        evidence=f"part={evidence_name(name)}, reason={read_findings[0].code}",
                    )
                )
                continue
            lowered = part_bytes.lower()
            if name.lower().endswith(".rels") and (
                b'targetmode="external"' in lowered or b"targetmode='external'" in lowered
            ):
                findings.append(
                    ArtifactFinding(
                        code=AuditCode.DOCX_EXTERNAL_RELATIONSHIP,
                        severity=ArtifactFindingSeverity.ERROR,
                        description="External package relationship detected",
                        evidence=f"part={evidence_name(name)}",
                    )
                )
            for marker in _FORBIDDEN_XML_MARKERS:
                if marker in lowered:
                    findings.append(
                        ArtifactFinding(
                            code=AuditCode.DOCX_HIDDEN_CONTENT,
                            severity=ArtifactFindingSeverity.ERROR,
                            description="Hidden, revision, or embedded content detected",
                            evidence=f"part={evidence_name(name)}, marker={marker.decode()}",
                        )
                    )
            for term in DOCX_METADATA_TERMS:
                if term.encode("utf-8") in lowered:
                    findings.append(
                        ArtifactFinding(
                            code=AuditCode.DOCX_METADATA_PROHIBITED,
                            severity=ArtifactFindingSeverity.ERROR,
                            description=f"Prohibited internal metadata term present: {term}",
                            evidence=f"part={evidence_name(name)}, term={term}",
                        )
                    )


def _local_name(tag: object) -> str:
    return str(tag).rsplit("}", 1)[-1]


def _document_text(root: Any) -> str:
    """Extract paragraph text from the independently parsed document tree."""
    paragraphs: list[str] = []
    for paragraph in root.iter():
        if _local_name(paragraph.tag) != "p":
            continue
        text = "".join(
            html.unescape(str(element.text))
            for element in paragraph.iter()
            if _local_name(element.tag) == "t" and element.text
        )
        paragraphs.append(text)
    return "\n".join(paragraphs)
