"""Unit tests for style artifacts and the exact surface representation."""

from __future__ import annotations

import hashlib

from humanhand.domain.canonical_document import build_document
from humanhand.domain.document_nodes import NodeBuilder, NodeType
from humanhand.domain.import_policy import ImportPolicy
from humanhand.domain.style_artifacts import (
    STYLE_EVIDENCE_PACKAGE_SCHEMA_VERSION,
    OriginalStyleArtifact,
    StyleEvidencePackage,
    StyleExemplar,
)
from humanhand.domain.style_authorship import AuthorshipMap
from humanhand.domain.style_surface import (
    CanonicalSurfaceDocument,
    build_surface_document,
    surface_statistics,
)


def _document(text: str = "Hello world. Second sentence.") -> object:
    root = NodeBuilder(node_type=NodeType.DOCUMENT)
    root.add_child(NodeBuilder(node_type=NodeType.PARAGRAPH, text=text))
    return build_document(
        root=root,
        lane="style",
        parser_name="text",
        parser_version="1",
        policy=ImportPolicy(lane="style"),
        surface_text=text,
    )


class TestSurfaceDocument:
    def test_builds_exact_surface(self) -> None:
        document = _document()
        surface = build_surface_document(artifact_id="abc123", document=document)  # type: ignore[arg-type]
        assert surface.surface_text == "Hello world. Second sentence."
        assert surface.artifact_id == "abc123"
        expected_sha = hashlib.sha256(b"Hello world. Second sentence.").hexdigest()
        assert surface.sha256 == expected_sha
        assert surface.code_point_count == len("Hello world. Second sentence.")
        assert surface.statistics.paragraphs == 1
        assert surface.node_count == 2

    def test_statistics_count_structure(self) -> None:
        text = "Title\n\nBody paragraph."
        root = NodeBuilder(node_type=NodeType.DOCUMENT)
        root.add_child(
            NodeBuilder(node_type=NodeType.HEADING, text="Title", attributes={"level": "1"})
        )
        root.add_child(NodeBuilder(node_type=NodeType.PARAGRAPH, text="Body paragraph."))
        document = build_document(
            root=root,
            lane="style",
            parser_name="text",
            parser_version="1",
            policy=ImportPolicy(lane="style"),
            surface_text=text,
        )
        stats = surface_statistics(document)
        assert stats.headings == 1
        assert stats.paragraphs == 1
        assert stats.bytes_utf8 == len(text.encode("utf-8"))

    def test_package_shape(self) -> None:
        package = StyleEvidencePackage(
            schema_version=STYLE_EVIDENCE_PACKAGE_SCHEMA_VERSION,
            package_id="sty-abc",
            profile_label="default",
            original_artifact=OriginalStyleArtifact(
                artifact_id="abc", sha256="abc", size_bytes=3, stored=True
            ),
            exact_surface=CanonicalSurfaceDocument(
                artifact_id="abc",
                surface_text="x",
                sha256="abc",
                statistics=surface_statistics(_document()),  # type: ignore[arg-type]
                node_count=1,
            ),
            authorship=AuthorshipMap(spans=(), excluded=()),
            approved_exemplars=(StyleExemplar(exemplar_id="e1", text="x", span_id="a1"),),
            parser_version="1",
            ruleset_version="1",
        )
        assert package.profile_label == "default"
        assert package.approved_exemplars[0].exemplar_id == "e1"
