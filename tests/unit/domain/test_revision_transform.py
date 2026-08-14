"""Unit tests for applying reviewed lexical changes to canonical revisions."""

from __future__ import annotations

import pytest

from humanhand.domain.canonical_document import CanonicalDocument, build_document
from humanhand.domain.document_nodes import NodeBuilder, NodeType, SourceLocation
from humanhand.domain.import_policy import ImportPolicy
from humanhand.domain.lexical_context import build_contexts
from humanhand.domain.lexical_normalizer import propose_changes
from humanhand.domain.lexical_types import load_bundled_rules
from humanhand.domain.protected_spans import ProtectedSpanSet
from humanhand.domain.revision_transform import apply_reviewed_proposal
from humanhand.domain.structure_signature import compute_structure_signature
from humanhand.domain.types import DomainError


def _document(text: str, node_type: NodeType = NodeType.PARAGRAPH) -> CanonicalDocument:
    root = NodeBuilder(node_type=NodeType.DOCUMENT)
    root.add_child(
        NodeBuilder(
            node_type=node_type,
            text=text,
            source_location=SourceLocation(0, len(text)),
        )
    )
    return build_document(
        root=root,
        lane="source",
        parser_name="test",
        parser_version="1",
        policy=ImportPolicy(lane="source"),
        surface_text=text,
    )


def _proposal(document: CanonicalDocument):  # type: ignore[no-untyped-def]
    spans = ProtectedSpanSet(spans=())
    return propose_changes(
        document.surface_text,
        load_bundled_rules(),
        build_contexts(document.surface_text, spans),
        user_preferences={},
        project_glossary=(),
        register_rules=(),
        domain_glossary=(),
        safe_threshold=0.90,
        protected_spans=spans,
    )


def test_applies_change_and_preserves_macro_structure() -> None:
    document = _document("We utilize evidence.")
    proposal = _proposal(document)
    assert len(proposal.changes) == 1
    transformed = apply_reviewed_proposal(document, proposal)
    assert transformed.surface_text == "We use evidence."
    assert transformed.nodes[1].text == "We use evidence."
    assert transformed.nodes[1].source_location.end_offset == len(transformed.surface_text)
    assert compute_structure_signature(transformed) == compute_structure_signature(document)


def test_protected_heading_change_fails_closed() -> None:
    document = _document("Utilize evidence", NodeType.HEADING)
    proposal = _proposal(document)
    assert proposal.changes
    with pytest.raises(DomainError, match="protected canonical node"):
        apply_reviewed_proposal(document, proposal)


def test_proposal_for_different_document_fails_closed() -> None:
    document = _document("We utilize evidence.")
    proposal = _proposal(document)
    other = _document("We utilize records.")
    with pytest.raises(DomainError, match="hash"):
        apply_reviewed_proposal(other, proposal)
