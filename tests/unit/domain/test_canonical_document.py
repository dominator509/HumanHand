"""Unit tests for canonical document construction and inspection assembly."""

from __future__ import annotations

import pytest

from humanhand.domain.active_content import ActiveContentFinding, ActiveContentKind
from humanhand.domain.canonical_document import (
    CanonicalDocument,
    CoverageSummary,
    ResourceMeasurements,
    build_document,
    derive_import_id,
    make_inspection,
    measure_document,
)
from humanhand.domain.document_nodes import NodeBuilder, NodeType, SourceLocation
from humanhand.domain.file_identity import derive_identity
from humanhand.domain.import_findings import (
    FindingCategory,
    FindingCode,
    FindingSeverity,
    ImportFinding,
    ImportStatus,
    classify_status,
)
from humanhand.domain.import_policy import ImportPolicy
from humanhand.domain.metadata_inventory import MetadataInventory, MetadataItem
from humanhand.domain.types import DomainError
from humanhand.domain.unicode_policy import NormalizationForm, UnicodeInventory


def _policy(**overrides: object) -> ImportPolicy:
    defaults: dict[str, object] = {"lane": "source"}
    defaults.update(overrides)
    return ImportPolicy(**defaults)  # type: ignore[arg-type]


def _doc_tree() -> NodeBuilder:
    root = NodeBuilder(
        node_type=NodeType.DOCUMENT,
        source_location=SourceLocation(start_offset=0, end_offset=30, line_start=1, line_end=2),
    )
    heading = root.add_child(
        NodeBuilder(
            node_type=NodeType.HEADING,
            text="Title",
            attributes={"level": "1"},
            source_location=SourceLocation(0, 5, 1, 1),
        )
    )
    heading.add_child(NodeBuilder(node_type=NodeType.TEXT_RUN, text="Title"))
    para = root.add_child(
        NodeBuilder(
            node_type=NodeType.PARAGRAPH,
            text="Hello world.",
            source_location=SourceLocation(6, 18, 2, 2),
        )
    )
    para.add_child(
        NodeBuilder(
            node_type=NodeType.TEXT_RUN,
            text="Hello world.",
            source_location=SourceLocation(6, 18, 2, 2),
        )
    )
    return root


class TestBuildDocument:
    def test_assigns_deterministic_ids_and_positions(self) -> None:
        policy = _policy()
        document = build_document(
            root=_doc_tree(),
            lane="source",
            parser_name="test",
            parser_version="1",
            policy=policy,
            surface_text="Title\nHello world.",
        )
        assert [node.node_id for node in document.nodes] == ["n1", "n2", "n3", "n4", "n5"]
        assert document.root.node_id == "n1"
        assert document.root.parent_id is None
        heading = document.node_by_id("n2")
        assert heading.parent_id == "n1"
        assert heading.position == 1
        assert heading.attributes == {"level": "1"}
        para = document.node_by_id("n4")
        assert para.parent_id == "n1"
        assert para.position == 2
        assert document.lane == "source"
        assert document.parser_name == "test"
        assert document.policy_version == policy.version

    def test_canonical_text_is_nfc(self) -> None:
        decomposed = "café"
        policy = _policy()
        root = NodeBuilder(node_type=NodeType.DOCUMENT)
        root.add_child(NodeBuilder(node_type=NodeType.PARAGRAPH, text=decomposed))
        document = build_document(
            root=root,
            lane="source",
            parser_name="test",
            parser_version="1",
            policy=policy,
            surface_text=decomposed,
        )
        assert document.surface_text == decomposed
        assert document.canonical_text == "café"

    def test_rejects_non_document_root(self) -> None:
        with pytest.raises(DomainError, match="DOCUMENT"):
            build_document(
                root=NodeBuilder(node_type=NodeType.PARAGRAPH, text="x"),
                lane="source",
                parser_name="test",
                parser_version="1",
                policy=_policy(),
                surface_text="x",
            )

    def test_rejects_node_count_over_limit(self) -> None:
        root = NodeBuilder(node_type=NodeType.DOCUMENT)
        for index in range(3):
            root.add_child(NodeBuilder(node_type=NodeType.PARAGRAPH, text=f"p{index}"))
        with pytest.raises(DomainError, match="limit"):
            build_document(
                root=root,
                lane="source",
                parser_name="test",
                parser_version="1",
                policy=_policy(max_nodes=2),
                surface_text="x",
            )

    def test_node_by_id_missing_raises(self) -> None:
        document = build_document(
            root=_doc_tree(),
            lane="source",
            parser_name="test",
            parser_version="1",
            policy=_policy(),
            surface_text="Title\nHello world.",
        )
        with pytest.raises(KeyError):
            document.node_by_id("n999")


class TestMeasureDocument:
    def test_measure_none(self) -> None:
        measurements = measure_document(None, size_bytes=10)
        assert measurements == ResourceMeasurements(
            size_bytes=10, expanded_bytes=10, node_count=0, tree_depth=0
        )

    def test_measure_tree(self) -> None:
        document = build_document(
            root=_doc_tree(),
            lane="source",
            parser_name="test",
            parser_version="1",
            policy=_policy(),
            surface_text="Title\nHello world.",
        )
        measurements = measure_document(document, size_bytes=20)
        assert measurements.size_bytes == 20
        assert measurements.node_count == 5
        assert measurements.tree_depth == 3
        assert measurements.expanded_bytes == len(b"Title\nHello world.")


class TestClassifyStatus:
    def test_empty_findings_ok(self) -> None:
        assert classify_status(()) is ImportStatus.OK

    def test_warning_is_findings(self) -> None:
        findings = (
            ImportFinding(
                code=FindingCode.ENCODING_BOM,
                severity=FindingSeverity.WARNING,
                category=FindingCategory.ENCODING,
                description="bom",
            ),
        )
        assert classify_status(findings) is ImportStatus.FINDINGS

    def test_unsupported_format_wins(self) -> None:
        findings = (
            ImportFinding(
                code=FindingCode.UNSUPPORTED_FORMAT,
                severity=FindingSeverity.ERROR,
                category=FindingCategory.UNSUPPORTED_FEATURE,
                description="unsupported",
            ),
            ImportFinding(
                code=FindingCode.ACTIVE_CONTENT_SCRIPT,
                severity=FindingSeverity.ERROR,
                category=FindingCategory.ACTIVE_CONTENT,
                description="script",
            ),
        )
        assert classify_status(findings) is ImportStatus.UNSUPPORTED_FORMAT

    def test_status_priority_does_not_depend_on_finding_order(self) -> None:
        findings = (
            ImportFinding(
                code=FindingCode.MAGIC_MISMATCH,
                severity=FindingSeverity.ERROR,
                category=FindingCategory.MAGIC_MISMATCH,
                description="mismatch",
            ),
            ImportFinding(
                code=FindingCode.UNSUPPORTED_FORMAT,
                severity=FindingSeverity.ERROR,
                category=FindingCategory.UNSUPPORTED_FEATURE,
                description="unsupported",
            ),
        )
        assert classify_status(findings) is ImportStatus.UNSUPPORTED_FORMAT

    def test_active_content_requires_review(self) -> None:
        findings = (
            ImportFinding(
                code=FindingCode.ACTIVE_CONTENT_SCRIPT,
                severity=FindingSeverity.ERROR,
                category=FindingCategory.ACTIVE_CONTENT,
                description="script",
            ),
        )
        assert classify_status(findings) is ImportStatus.HUMAN_REVIEW_REQUIRED

    def test_remote_resource_requires_review(self) -> None:
        findings = (
            ImportFinding(
                code=FindingCode.EXTERNAL_REMOTE_RESOURCE,
                severity=FindingSeverity.ERROR,
                category=FindingCategory.EXTERNAL_RELATIONSHIP,
                description="remote",
            ),
        )
        assert classify_status(findings) is ImportStatus.HUMAN_REVIEW_REQUIRED

    def test_unverified_reading_order_requires_review(self) -> None:
        findings = (
            ImportFinding(
                code=FindingCode.STRUCTURE_READING_ORDER_UNVERIFIED,
                severity=FindingSeverity.ERROR,
                category=FindingCategory.STRUCTURE,
                description="reading order",
            ),
        )
        assert classify_status(findings) is ImportStatus.HUMAN_REVIEW_REQUIRED

    def test_magic_mismatch_quarantines(self) -> None:
        findings = (
            ImportFinding(
                code=FindingCode.MAGIC_MISMATCH,
                severity=FindingSeverity.ERROR,
                category=FindingCategory.MAGIC_MISMATCH,
                description="mismatch",
            ),
        )
        assert classify_status(findings) is ImportStatus.QUARANTINED

    def test_other_error_fails(self) -> None:
        findings = (
            ImportFinding(
                code=FindingCode.LIMIT_BYTES,
                severity=FindingSeverity.ERROR,
                category=FindingCategory.RESOURCE_LIMIT,
                description="too big",
            ),
        )
        assert classify_status(findings) is ImportStatus.FAILED


class TestDeriveImportId:
    def test_deterministic(self) -> None:
        policy = _policy()
        first = derive_import_id(
            raw=b"hello", lane="source", parser_name="text", parser_version="1", policy=policy
        )
        second = derive_import_id(
            raw=b"hello", lane="source", parser_name="text", parser_version="1", policy=policy
        )
        assert first == second
        assert first.startswith("import-")
        assert len(first) == len("import-") + 32

    def test_differs_on_content(self) -> None:
        policy = _policy()
        first = derive_import_id(
            raw=b"hello", lane="source", parser_name="text", parser_version="1", policy=policy
        )
        second = derive_import_id(
            raw=b"world", lane="source", parser_name="text", parser_version="1", policy=policy
        )
        assert first != second

    def test_differs_on_lane(self) -> None:
        first = derive_import_id(
            raw=b"hello", lane="source", parser_name="text", parser_version="1", policy=_policy()
        )
        second = derive_import_id(
            raw=b"hello", lane="style", parser_name="text", parser_version="1", policy=_policy()
        )
        assert first != second


class TestMakeInspection:
    def test_assembles_inspection(self) -> None:
        raw = b"Hello world.\n"
        identity = derive_identity("sample.txt", raw)
        policy = _policy()
        document = build_document(
            root=_doc_tree(),
            lane="source",
            parser_name="text",
            parser_version="1",
            policy=policy,
            surface_text="Title\nHello world.",
        )
        inspection = make_inspection(
            raw=raw,
            identity=identity,
            lane="source",
            parser_name="text",
            parser_version="1",
            policy=policy,
            findings=(),
            coverage=CoverageSummary(
                adapter="text",
                supported_structures=("paragraph",),
                unsupported_structures=(),
                status="complete",
            ),
            unicode_inventory=UnicodeInventory(
                has_bom=False,
                bom_name="",
                normalization_form=NormalizationForm.NFC,
                control_char_offsets=(),
                surrogate_offsets=(),
                non_nfc_offsets=(),
                line_ending="lf",
                codepoint_count=13,
            ),
            active_content=(),
            measurements=ResourceMeasurements(
                size_bytes=len(raw), expanded_bytes=len(raw), node_count=5, tree_depth=3
            ),
            document=document,
        )
        assert inspection.status is ImportStatus.OK
        assert inspection.file_identity is identity
        assert inspection.document is document
        assert inspection.import_id.startswith("import-")

    def test_status_override(self) -> None:
        inspection = make_inspection(
            raw=b"x",
            identity=derive_identity("doc.pdf", b"%PDF-1.4\nfake"),
            lane="source",
            parser_name="text",
            parser_version="1",
            policy=_policy(),
            findings=(),
            coverage=CoverageSummary(
                adapter="none",
                supported_structures=(),
                unsupported_structures=("pdf",),
                status="unsupported_format",
            ),
            status_override=ImportStatus.UNSUPPORTED_FORMAT,
        )
        assert inspection.status is ImportStatus.UNSUPPORTED_FORMAT

    def test_empty_metadata_default(self) -> None:
        inspection = make_inspection(
            raw=b"x",
            identity=derive_identity("sample.txt", b"x"),
            lane="source",
            parser_name="text",
            parser_version="1",
            policy=_policy(),
            findings=(),
            coverage=CoverageSummary(
                adapter="text",
                supported_structures=("paragraph",),
                unsupported_structures=(),
                status="complete",
            ),
        )
        assert inspection.metadata == MetadataInventory()
        assert inspection.active_content == ()

    def test_metadata_items_preserved(self) -> None:
        inspection = make_inspection(
            raw=b"x",
            identity=derive_identity("sample.txt", b"x"),
            lane="source",
            parser_name="text",
            parser_version="1",
            policy=_policy(),
            findings=(),
            coverage=CoverageSummary(
                adapter="text",
                supported_structures=("paragraph",),
                unsupported_structures=(),
                status="complete",
            ),
            metadata=MetadataInventory(
                items=(MetadataItem(key="title", kind="front_matter", value="Doc"),)
            ),
            active_content=(
                ActiveContentFinding(
                    kind=ActiveContentKind.HTML_SCRIPT, offset=0, description="script"
                ),
            ),
        )
        assert inspection.metadata.items[0].key == "title"
        assert inspection.active_content[0].kind is ActiveContentKind.HTML_SCRIPT


class TestCanonicalDocumentProperties:
    def test_root_and_node_by_id(self) -> None:
        document = build_document(
            root=_doc_tree(),
            lane="source",
            parser_name="test",
            parser_version="1",
            policy=_policy(),
            surface_text="Title\nHello world.",
        )
        assert document.root is document.nodes[0]
        assert document.root.node_type is NodeType.DOCUMENT

    def test_root_raises_when_empty(self) -> None:
        empty = CanonicalDocument(
            schema_version=1,
            lane="source",
            parser_name="test",
            parser_version="1",
            policy_version="1",
            revision_policy="review_required",
            surface_text="",
            canonical_text="",
            nodes=(),
            findings=(),
        )
        with pytest.raises(DomainError, match="root"):
            _ = empty.root
