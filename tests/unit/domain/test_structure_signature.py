"""Unit tests for structure signature computation and equality."""

from __future__ import annotations

from humanhand.domain.canonical_document import CanonicalDocument, build_document
from humanhand.domain.document_nodes import NodeBuilder, NodeType
from humanhand.domain.import_policy import ImportPolicy
from humanhand.domain.source_package import LANE_SOURCE
from humanhand.domain.structure_signature import (
    StructureSignature,
    compute_structure_signature,
    signatures_equal,
)

# Hand-verified with the NodeBuilder tree below: pre-order node ids are
# n1=DOCUMENT, n2=SECTION, n3=HEADING, n4..n5=PARAGRAPH, so the counts are
# {"document": 1, "section": 1, "heading": 1, "paragraph": 2} and the total
# node count is 5.


def _document(headings: tuple[str, ...], paragraphs: tuple[str, ...]) -> CanonicalDocument:
    root = NodeBuilder(node_type=NodeType.DOCUMENT)
    section = root.add_child(NodeBuilder(node_type=NodeType.SECTION))
    for heading_text in headings:
        section.add_child(NodeBuilder(node_type=NodeType.HEADING, text=heading_text))
    for paragraph_text in paragraphs:
        section.add_child(NodeBuilder(node_type=NodeType.PARAGRAPH, text=paragraph_text))
    return build_document(
        root=root,
        lane=LANE_SOURCE,
        parser_name="text",
        parser_version="1",
        policy=ImportPolicy(lane=LANE_SOURCE),
        surface_text="\n".join((*headings, *paragraphs)),
    )


class TestComputeStructureSignature:
    def test_fields_shape(self) -> None:
        signature = compute_structure_signature(_document(("Intro",), ("One.", "Two.")))
        assert isinstance(signature.signature, str)
        assert len(signature.signature) == 64
        assert all(char in "0123456789abcdef" for char in signature.signature)
        assert signature.section_order == ("Intro",)
        assert signature.node_type_counts == {
            "document": 1,
            "section": 1,
            "heading": 1,
            "paragraph": 2,
        }
        assert signature.total_nodes == 5

    def test_deterministic_replay(self) -> None:
        document = _document(("Intro",), ("One.", "Two."))
        assert compute_structure_signature(document) == compute_structure_signature(document)

    def test_same_tree_different_input_objects_agree(self) -> None:
        first = compute_structure_signature(_document(("Intro",), ("One.", "Two.")))
        second = compute_structure_signature(_document(("Intro",), ("One.", "Two.")))
        assert signatures_equal(first, second)

    def test_different_heading_order_differs(self) -> None:
        first = compute_structure_signature(_document(("Intro", "Methods"), ("One.",)))
        second = compute_structure_signature(_document(("Methods", "Intro"), ("One.",)))
        assert first.signature != second.signature
        assert not signatures_equal(first, second)

    def test_heading_text_is_part_of_digest(self) -> None:
        first = compute_structure_signature(_document(("Intro",), ("One.",)))
        second = compute_structure_signature(_document(("Methods",), ("One.",)))
        assert first.signature != second.signature

    def test_section_order_is_exact(self) -> None:
        signature = compute_structure_signature(_document(("Intro", "Methods"), ("One.",)))
        assert signature.section_order == ("Intro", "Methods")


class TestStructureSignatureEquality:
    def test_signatures_equal(self) -> None:
        first = StructureSignature(
            signature="a" * 64,
            section_order=("Intro",),
            node_type_counts={"paragraph": 1},
            total_nodes=2,
        )
        second = StructureSignature(
            signature="a" * 64,
            section_order=("Intro",),
            node_type_counts={"paragraph": 1},
            total_nodes=2,
        )
        assert signatures_equal(first, second)

    def test_signatures_differ_on_digest(self) -> None:
        first = StructureSignature(
            signature="a" * 64,
            section_order=(),
            node_type_counts={},
            total_nodes=0,
        )
        second = StructureSignature(
            signature="b" * 64,
            section_order=(),
            node_type_counts={},
            total_nodes=0,
        )
        assert not signatures_equal(first, second)
