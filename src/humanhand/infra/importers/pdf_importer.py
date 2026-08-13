"""Clean-room PDF importer producing canonical document structures (EP-013).

Extracts native text per page with pypdf's deterministic text extraction
and maps each page to a SECTION node with one PARAGRAPH per non-empty
line. Image-only pages become IMAGE_PLACEHOLDER nodes with a warning; a
fully image-only PDF fails closed with an error because OCR is out of
scope for the Pre-SLM program.

Honest limitations (pypdf cannot do these, so they are declared in
coverage.unsupported_structures on every inspection):
- reading-order verification: pypdf's extractor returns text in content
  stream order, which is not guaranteed to match visual reading order.
- duplicate-OCR-layer detection: overlapping text layers cannot be
  distinguished from legitimate content with pypdf alone.

The importer never opens files, never touches the network, and never
executes PDF actions; JavaScript presence is detected structurally and
reported as active-content evidence.
"""

from __future__ import annotations

import io

from pypdf import PdfReader
from pypdf.errors import PyPdfError

from humanhand.domain.active_content import scheme_host_only
from humanhand.domain.canonical_document import CoverageSummary
from humanhand.domain.document_nodes import NodeBuilder, NodeType, SourceLocation
from humanhand.domain.file_identity import FileKind
from humanhand.domain.import_findings import (
    FindingCategory,
    FindingCode,
    FindingSeverity,
    ImportFinding,
)
from humanhand.domain.import_policy import ImportPolicy, check_limits
from humanhand.domain.metadata_inventory import MetadataInventory, MetadataItem
from humanhand.infra.importers.base import ContainerImporter, assemble_rich_payloads
from humanhand.infra.importers.pdf_inspection import (
    acroform_present,
    annotations_count,
    attachments_count,
    javascript_present,
    page_has_image,
    remote_references,
)

# Structures this adapter can represent, in a stable order.
_SUPPORTED_STRUCTURES = ("section", "paragraph", "image_placeholder")
# Structures pypdf cannot verify; declared honestly on every inspection.
_UNSUPPORTED_STRUCTURES = ("reading_order_verification", "ocr_layer_detection")

_JAVASCRIPT_FINDING = ImportFinding(
    code=FindingCode.ACTIVE_CONTENT_SCRIPT,
    severity=FindingSeverity.ERROR,
    category=FindingCategory.ACTIVE_CONTENT,
    description="PDF contains JavaScript",
    evidence="pdf_javascript",
)
_ACROFORM_FINDING = ImportFinding(
    code=FindingCode.UNSUPPORTED_FEATURE,
    severity=FindingSeverity.WARNING,
    category=FindingCategory.UNSUPPORTED_FEATURE,
    description="PDF contains an interactive form",
    evidence="acroform",
)


def _invalid_pdf_finding() -> ImportFinding:
    return ImportFinding(
        code=FindingCode.UNSUPPORTED_FEATURE,
        severity=FindingSeverity.ERROR,
        category=FindingCategory.STRUCTURE,
        description="Not a valid PDF",
        evidence="pdf_parse_error",
    )


def _lines_with_spans(
    text: str, start_offset: int, start_line: int
) -> tuple[list[tuple[str, SourceLocation]], int]:
    """Split page text into non-empty lines with exact spans.

    Returns ``(lines, next_line_number)``. Line numbers are 1-based
    positions inside the joined surface text, and offsets index the same
    surface text, so node spans always stay within its bounds.
    """
    lines: list[tuple[str, SourceLocation]] = []
    offset = start_offset
    line_number = start_line
    for raw_line in text.split("\n"):
        if raw_line.strip():
            lines.append(
                (
                    raw_line,
                    SourceLocation(offset, offset + len(raw_line), line_number, line_number),
                )
            )
        offset += len(raw_line) + 1
        line_number += 1
    return lines, line_number


def _page_spans(texts: list[str]) -> list[tuple[int, int, int, int]]:
    """Compute (start_offset, end_offset, line_start, line_end) per page.

    Pages are joined with ``"\\n\\n"`` exactly as ``surface_text`` is
    built, so the returned spans are valid indexes into that text.
    """
    spans: list[tuple[int, int, int, int]] = []
    offset = 0
    line_number = 1
    for text in texts:
        end = offset + len(text)
        line_end = line_number + text.count("\n")
        spans.append((offset, end, line_number, line_end))
        offset = end + 2
        line_number = line_end + 1
    return spans


class PdfImporter(ContainerImporter):
    """Deterministic clean-room parser for PDF containers."""

    parser_name = "pdf"
    parser_version = "1"
    supported_kinds = frozenset({FileKind.PDF})

    def parse_payloads(self, raw: bytes, policy: ImportPolicy) -> dict[str, object]:
        """Parse PDF bytes into the shared payload envelope.

        Any pypdf failure at construction is a structural error: the input
        is not a valid PDF and fails closed without a document.
        """
        findings: list[ImportFinding] = []
        # Pre-parse size bound: never construct a reader for over-limit
        # input (a small, highly compressed PDF can expand far beyond its
        # byte size inside pypdf; the worker timeout and tracemalloc peak
        # check bound the residual expansion risk in the sandboxed path).
        findings.extend(
            check_limits(
                policy,
                size_bytes=len(raw),
                expanded_bytes=len(raw),
                node_count=0,
                depth=0,
            )
        )
        if any(finding.severity is FindingSeverity.ERROR for finding in findings):
            return assemble_rich_payloads(
                raw=raw,
                policy=policy,
                parser_name=self.parser_name,
                parser_version=self.parser_version,
                surface_text="",
                root=None,
                findings=findings,
                coverage=self._coverage(),
                metadata=MetadataInventory(),
                active=(),
            )

        try:
            reader = PdfReader(io.BytesIO(raw))
        except PyPdfError:
            return assemble_rich_payloads(
                raw=raw,
                policy=policy,
                parser_name=self.parser_name,
                parser_version=self.parser_version,
                surface_text="",
                root=None,
                findings=[_invalid_pdf_finding()],
                coverage=self._coverage(),
                metadata=MetadataInventory(),
                active=(),
            )

        if javascript_present(reader):
            findings.append(_JAVASCRIPT_FINDING)
        if acroform_present(reader):
            findings.append(_ACROFORM_FINDING)
        for url in remote_references(reader):
            findings.append(
                ImportFinding(
                    code=FindingCode.EXTERNAL_REMOTE_RESOURCE,
                    severity=FindingSeverity.ERROR,
                    category=FindingCategory.EXTERNAL_RELATIONSHIP,
                    description="PDF contains a remote URI reference",
                    evidence=scheme_host_only(url),
                )
            )

        metadata_items: list[MetadataItem] = []
        attachment_count = attachments_count(reader)
        if attachment_count > 0:
            metadata_items.append(
                MetadataItem(key="attachments", kind="pdf_attachments", value=str(attachment_count))
            )
            findings.append(
                ImportFinding(
                    code=FindingCode.UNSUPPORTED_FEATURE,
                    severity=FindingSeverity.WARNING,
                    category=FindingCategory.UNSUPPORTED_FEATURE,
                    description=f"PDF contains {attachment_count} embedded attachment(s)",
                    evidence=f"attachments={attachment_count}",
                )
            )
        annotation_count = annotations_count(reader)
        if annotation_count > 0:
            metadata_items.append(
                MetadataItem(key="annotations", kind="pdf_annotations", value=str(annotation_count))
            )

        pages = reader.pages
        texts = [page.extract_text() or "" for page in pages]
        surface_text = "\n\n".join(texts)
        spans = _page_spans(texts)

        root_builder = NodeBuilder(
            node_type=NodeType.DOCUMENT,
            source_location=SourceLocation(0, len(surface_text), 1, surface_text.count("\n") + 1),
        )
        for index, (text, span) in enumerate(zip(texts, spans, strict=True)):
            section = NodeBuilder(
                node_type=NodeType.SECTION,
                source_location=SourceLocation(span[0], span[1], span[2], span[3]),
            )
            lines, _ = _lines_with_spans(text, span[0], span[2])
            if lines:
                for line_text, line_span in lines:
                    section.add_child(
                        NodeBuilder(
                            node_type=NodeType.PARAGRAPH,
                            text=line_text,
                            source_location=line_span,
                        )
                    )
            elif page_has_image(pages[index]):
                section.add_child(
                    NodeBuilder(
                        node_type=NodeType.IMAGE_PLACEHOLDER,
                        source_location=SourceLocation(span[0], span[1], span[2], span[3]),
                    )
                )
                findings.append(
                    ImportFinding(
                        code=FindingCode.UNSUPPORTED_FEATURE,
                        severity=FindingSeverity.WARNING,
                        category=FindingCategory.UNSUPPORTED_FEATURE,
                        description="PDF page is image-only",
                        evidence=f"page={index + 1}",
                    )
                )
            root_builder.add_child(section)

        no_text_anywhere = not any(text.strip() for text in texts)
        all_pages_are_images = bool(pages) and all(page_has_image(page) for page in pages)
        root: NodeBuilder | None = root_builder
        if no_text_anywhere and all_pages_are_images:
            findings.append(
                ImportFinding(
                    code=FindingCode.UNSUPPORTED_FEATURE,
                    severity=FindingSeverity.ERROR,
                    category=FindingCategory.UNSUPPORTED_FEATURE,
                    description="Image-only PDF cannot be represented without OCR",
                    evidence="image_only_pdf",
                )
            )
            root = None

        if root is not None:
            findings.append(
                ImportFinding(
                    code=FindingCode.STRUCTURE_READING_ORDER_UNVERIFIED,
                    severity=FindingSeverity.ERROR,
                    category=FindingCategory.STRUCTURE,
                    description="PDF reading order cannot be verified mechanically",
                    evidence="reading_order_unverified",
                )
            )

        return assemble_rich_payloads(
            raw=raw,
            policy=policy,
            parser_name=self.parser_name,
            parser_version=self.parser_version,
            surface_text=surface_text,
            root=root,
            findings=findings,
            coverage=self._coverage(),
            metadata=MetadataInventory(items=tuple(metadata_items)),
            active=(),
        )

    def _coverage(self) -> CoverageSummary:
        return CoverageSummary(
            adapter=self.parser_name,
            supported_structures=_SUPPORTED_STRUCTURES,
            unsupported_structures=_UNSUPPORTED_STRUCTURES,
            status="partial",
        )
