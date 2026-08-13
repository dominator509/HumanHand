"""PDF artifact auditor (EP-016).

Independent audit path: the auditor re-reads the artifact bytes from
disk and opens the PDF with pypdf (:class:`pypdf.PdfReader`); it shares
no code with the exporter.

Checks:
- the bytes open as a valid PDF (``PyPdfError`` fails closed),
- page text extraction succeeds,
- the expected title and every expected section text appear in the
  extracted text, with whitespace collapsed on both sides (documented
  rule: pypdf may split one visual line across page or layout
  boundaries, so exact whitespace must not be required),
- no JavaScript.

JavaScript check scope (LOCAL, documented): this auditor deliberately
does NOT import ``humanhand.infra.importers.pdf_inspection``; it only
detects the two standard placements:
  - catalog ``/Names`` dictionary carrying a ``/JavaScript`` entry,
  - catalog ``/OpenAction`` whose action dictionary has ``/S
    /JavaScript``.
Indirect references are resolved one level with ``reader.get_object``;
an unresolvable catalog structure is treated as no-JavaScript because
broken structure is already reported by the open/extract paths. This is
a narrower check than ``pdf_inspection.javascript_present`` (which also
covers ``/AA`` and ``/A`` entries); the difference is intentional and
recorded in the EP-016 Decision Log.
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
    missing_claim_findings,
    missing_section_findings,
    prohibited_term_findings,
    read_file_bytes,
)


class PdfAuditor(BaseAuditor):
    """Independent auditor for PDF artifacts (format ``pdf``)."""

    format = "pdf"

    def audit_file(
        self, path: str | Path, *, expected: PublicDocument | None
    ) -> ArtifactAuditReport:
        raw = read_file_bytes(path)
        try:
            reader = PdfReader(io.BytesIO(raw))
        except PyPdfError as exc:
            return build_report(
                self.format,
                (
                    ArtifactFinding(
                        code=AuditCode.PDF_OPEN_FAILED,
                        severity=ArtifactFindingSeverity.ERROR,
                        description="Artifact is not a readable PDF",
                        evidence=f"error={type(exc).__name__}",
                    ),
                ),
            )
        findings: list[ArtifactFinding] = []
        extracted = ""
        extraction_ok = True
        try:
            extracted = "\n".join((page.extract_text() or "") for page in reader.pages)
        except PyPdfError as exc:
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
                missing_section_findings(extracted, expected, ordered=False, collapse=True)
            )
            findings.extend(missing_claim_findings(extracted, expected, collapse=True))
        if extraction_ok:
            findings.extend(prohibited_term_findings(extracted))
        metadata = reader.metadata
        if metadata:
            findings.extend(prohibited_term_findings(str(dict(metadata))))
        javascript_present, active_content_present = _active_content_present_local(reader)
        if javascript_present:
            findings.append(
                ArtifactFinding(
                    code=AuditCode.PDF_JAVASCRIPT,
                    severity=ArtifactFindingSeverity.ERROR,
                    description="JavaScript placement detected in the PDF catalog",
                    evidence="local_check",
                )
            )
        if active_content_present:
            findings.append(
                ArtifactFinding(
                    code=AuditCode.PDF_ACTIVE_CONTENT,
                    severity=ArtifactFindingSeverity.ERROR,
                    description="Embedded or interactive content detected in the PDF",
                    evidence="local_catalog_walk",
                )
            )
        return build_report(self.format, tuple(findings))


def _resolved(reader: PdfReader, obj: object) -> object:
    """Resolve one level of indirection for catalog navigation."""
    if isinstance(obj, IndirectObject):
        return reader.get_object(obj)
    return obj


def _active_content_present_local(reader: PdfReader) -> tuple[bool, bool]:
    """Walk the PDF object graph for scripts, attachments, and forms."""
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
                if keys.intersection({"/EmbeddedFiles", "/AcroForm", "/RichMedia"}):
                    active = True
                stack.extend(obj.values())
            elif isinstance(obj, (list, tuple)):
                stack.extend(obj)
    except PyPdfError:
        return True, True
    return javascript, active


def _javascript_present_local(reader: PdfReader) -> bool:
    """Compatibility wrapper for the independently implemented local walk."""
    return _active_content_present_local(reader)[0]
