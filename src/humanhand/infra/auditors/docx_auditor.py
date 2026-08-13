"""DOCX artifact auditor (EP-016).

Independent audit path: the auditor re-reads the artifact bytes from
disk, opens the package with :mod:`zipfile`, parses the main document
part through the repository's bounded/defused XML tooling
(``container_utils``), and scans every package part. It shares no code
with the exporter (the exporter's in-memory package is never reused).

Checks:
- the bytes are a valid ZIP package,
- ``word/document.xml`` is present and well-formed (bounded parse),
- every expected section text is present in the extracted document text
  (XML entities unescaped first), order-insensitive,
- no ``project_id`` or ``claim_id`` term in ANY package part,
- no VBA macro parts (names containing ``vbaproject``/``vbadata``).

Fail-closed extra: a package part that cannot be read is an ERROR
(``audit.docx.part_unreadable``) because the no-prohibited-terms
guarantee cannot be verified for that part.
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
    missing_claim_findings,
    missing_section_findings,
    read_file_bytes,
)

MAIN_DOCUMENT_PART = "word/document.xml"
# Terms that must not appear anywhere inside a public DOCX package.
DOCX_METADATA_TERMS = PROHIBITED_METADATA_TERMS
# Part-name markers for VBA macro payloads.
MACRO_PART_MARKERS = ("vbaproject", "vbadata")


class DocxAuditor(BaseAuditor):
    """Independent auditor for DOCX artifacts (format ``docx``)."""

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
                continue  # directory entry, not a package part
            lowered = name.lower()
            for marker in MACRO_PART_MARKERS:
                if marker in lowered:
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
        elif expected is not None:
            findings.append(
                ArtifactFinding(
                    code=AuditCode.DOCX_DOCUMENT_XML_MALFORMED,
                    severity=ArtifactFindingSeverity.ERROR,
                    description="Main document part is missing from the package",
                    evidence=f"part={MAIN_DOCUMENT_PART}",
                )
            )
        self._scan_parts_for_metadata(archive, policy, names, findings)
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
            findings.extend(missing_section_findings(document_text, expected, ordered=False))
            findings.extend(missing_claim_findings(document_text, expected))

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

    def _scan_parts_for_metadata(
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
                        description="Package part could not be read; prohibited-term scan skipped",
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
            if b"w:vanish" in lowered:
                findings.append(
                    ArtifactFinding(
                        code=AuditCode.DOCX_HIDDEN_CONTENT,
                        severity=ArtifactFindingSeverity.ERROR,
                        description="Hidden text formatting detected in a package part",
                        evidence=f"part={evidence_name(name)}",
                    )
                )
            for term in DOCX_METADATA_TERMS:
                if term.encode("utf-8") in lowered:
                    findings.append(
                        ArtifactFinding(
                            code=AuditCode.DOCX_METADATA_PROHIBITED,
                            severity=ArtifactFindingSeverity.ERROR,
                            description=(
                                "Prohibited internal metadata term present in a "
                                f"package part: {term}"
                            ),
                            evidence=f"part={evidence_name(name)}, term={term}",
                        )
                    )


def _local_name(tag: object) -> str:
    """Return the local name of an XML tag, stripping any namespace."""
    text = str(tag)
    return text.rsplit("}", 1)[-1]


def _document_text(root: Any) -> str:
    """Extract paragraph text from a parsed main-document element tree.

    ``w:t`` runs are unescaped with :func:`html.unescape` because the
    exporter stores document text as XML-escaped runs; containment must
    compare the actual text. Paragraphs are joined with ``\\n``.
    """
    paragraphs: list[str] = []
    current: list[str] = []
    in_paragraph = False
    for element in root.iter():
        local = _local_name(element.tag)
        if local == "p":
            if in_paragraph and current:
                paragraphs.append("".join(current))
                current = []
            in_paragraph = True
        elif in_paragraph and local == "t" and element.text:
            current.append(html.unescape(str(element.text)))
    if current:
        paragraphs.append("".join(current))
    return "\n".join(paragraphs)
