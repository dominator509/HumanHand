"""Independent metadata-free PDF artifact auditor (EP-019).

The auditor re-reads the final bytes with pypdf and fails closed on regular
metadata, XMP/root metadata, trailer identifiers, JavaScript, attachments,
forms, rich media, annotations, or missing approved visible content.
"""

from __future__ import annotations

import io
from pathlib import Path

from pypdf import PdfReader
from pypdf.errors import PyPdfError
from pypdf.generic import IndirectObject, NameObject

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
    collapse_whitespace,
    missing_section_findings,
    prohibited_term_findings,
    read_file_bytes,
)


class PdfAuditor(BaseAuditor):
    """Independent auditor for metadata-free PDF artifacts."""

    format = "pdf"

    def audit_file(
        self, path: str | Path, *, expected: PublicDocument | None
    ) -> ArtifactAuditReport:
        raw = read_file_bytes(path)
        try:
            reader = PdfReader(io.BytesIO(raw), strict=True)
        except PdfError as exc:
            return build_report(
                self.format,
                (
                    ArtifactFinding(
                        code=AuditCode.PDF_OPEN_FAILED,
                        severity=ArtifactFindingSeverity.ERROR,
                        description="Artifact is not a readable strict PDF",
                        evidence=f"error={type(exc).__name__}",
                    ),
                ),
            )
        findings: list[ArtifactFinding] = []
        extracted = ""
        extraction_ok = True
        try:
            extracted = "\n".join((page.extract_text() or "") for page in reader.pages)
        except PdfError as exc:
            extraction_ok = False
            findings.append(
                ArtifactFinding(
                    code=AuditCode.PDF_EXTRACT_FAILED,
                    severity=ArtifactFindingSeverity.ERROR,
                    description="Page text extraction failed",
                    evidence=f"error={type(exc).__name__}",
                )
            )
        if expected is not None and extraction_ok:
            collapsed = collapse_whitespace(extracted)
            if expected.title and collapse_whitespace(expected.title) not in collapsed:
                findings.append(
                    ArtifactFinding(
                        code=AuditCode.TITLE_MISSING,
                        severity=ArtifactFindingSeverity.ERROR,
                        description="Expected title is missing from the extracted PDF text",
                        evidence="check=extract_text",
                    )
                )
            findings.extend(
                missing_section_findings(extracted, expected, ordered=True, collapse=True)
            )
        if extraction_ok:
            findings.extend(prohibited_term_findings(extracted))
        findings.extend(_metadata_findings(reader))
        javascript_present, active_content_present = _active_content_present_local(reader)
        if javascript_present:
            findings.append(
                ArtifactFinding(
                    code=AuditCode.PDF_JAVASCRIPT,
                    severity=ArtifactFindingSeverity.ERROR,
                    description="JavaScript placement detected in the PDF object graph",
                    evidence="object_graph",
                )
            )
        if active_content_present:
            findings.append(
                ArtifactFinding(
                    code=AuditCode.PDF_ACTIVE_CONTENT,
                    severity=ArtifactFindingSeverity.ERROR,
                    description="Embedded, interactive, or annotated content detected",
                    evidence="object_graph",
                )
            )
        return build_report(self.format, tuple(findings))


def _resolved(reader: PdfReader, obj: object) -> object:
    if isinstance(obj, IndirectObject):
        return reader.get_object(obj)
    return obj


def _metadata_findings(reader: PdfReader) -> tuple[ArtifactFinding, ...]:
    findings: list[ArtifactFinding] = []
    try:
        metadata = reader.metadata
    except PdfError:
        metadata = {"unreadable": True}
    if metadata:
        findings.append(
            ArtifactFinding(
                code=AuditCode.METADATA_PROHIBITED,
                severity=ArtifactFindingSeverity.ERROR,
                description="PDF /Info metadata dictionary is present",
                evidence="trailer=/Info",
            )
        )
    try:
        xmp = reader.xmp_metadata
    except PdfError:
        xmp = object()
    root = _resolved(reader, reader.trailer.get("/Root"))
    if xmp is not None or (isinstance(root, dict) and "/Metadata" in root):
        findings.append(
            ArtifactFinding(
                code=AuditCode.METADATA_PROHIBITED,
                severity=ArtifactFindingSeverity.ERROR,
                description="PDF XMP metadata stream is present or unreadable",
                evidence="catalog=/Metadata",
            )
        )
    if reader.trailer.get("/ID") is not None:
        findings.append(
            ArtifactFinding(
                code=AuditCode.METADATA_PROHIBITED,
                severity=ArtifactFindingSeverity.ERROR,
                description="PDF trailer document identifier is present",
                evidence="trailer=/ID",
            )
        )
    return tuple(findings)


def _active_content_present_local(reader: PdfReader) -> tuple[bool, bool]:
    """Walk the PDF object graph for scripts, attachments, forms, and annotations."""
    trailer = reader.trailer
    if trailer is None:
        return False, False
    javascript = False
    active = False
    stack: list[object] = [trailer.get("/Root")]
    seen_indirect: set[tuple[int, int]] = set()
    visited = 0
    try:
        while stack and visited < 10_000:
            obj = stack.pop()
            if isinstance(obj, IndirectObject):
                key = (obj.idnum, obj.generation)
                if key in seen_indirect:
                    continue
                seen_indirect.add(key)
                obj = reader.get_object(obj)
            visited += 1
            if isinstance(obj, dict):
                keys = {str(key) for key in obj}
                if "/JS" in keys or obj.get("/S") == NameObject("/JavaScript"):
                    javascript = True
                if keys.intersection(
                    {
                        "/EmbeddedFiles",
                        "/AcroForm",
                        "/RichMedia",
                        "/Annots",
                        "/AA",
                    }
                ):
                    active = True
                stack.extend(obj.values())
            elif isinstance(obj, (list, tuple)):
                stack.extend(obj)
    except PdfError:
        return True, True
    if stack:
        return True, True
    return javascript, active


def _javascript_present_local(reader: PdfReader) -> bool:
    """Compatibility wrapper for existing tests."""
    return _active_content_present_local(reader)[0]
