"""Unit tests for deterministic context capsule assembly and integrity."""

from __future__ import annotations

import json
from dataclasses import replace

import pytest

from humanhand.domain.canonical_document import build_document
from humanhand.domain.citations import Citation
from humanhand.domain.claims_v2 import ClaimStatus, ClaimV2, Modality
from humanhand.domain.context_capsule import (
    ContextCapsule,
    build_context_capsule,
    capsule_from_json,
    capsule_to_json,
    capsule_to_payload,
    validate_capsule,
)
from humanhand.domain.context_policy import ContextPolicy
from humanhand.domain.document_nodes import NodeBuilder, NodeType, SourceLocation
from humanhand.domain.entities import Entity, EntityType
from humanhand.domain.import_policy import ImportPolicy
from humanhand.domain.project import new_project_state
from humanhand.domain.protected_spans import ProtectedSpan, SpanKind, SpanStatus
from humanhand.domain.revisions import create_initial_revision
from humanhand.domain.source_package import LANE_SOURCE
from humanhand.domain.structure_signature import StructureSignature
from humanhand.domain.types import DomainError

# Hand-verified fixture: the NodeBuilder tree below is wrapped pre-order,
# so node ids are n1=DOCUMENT, n2=SECTION, n3=HEADING("Introduction"),
# n4=PARAGRAPH("First paragraph text."), n5=PARAGRAPH("Second paragraph
# text."), n6=PARAGRAPH("Third paragraph text."). The capsule block is n5,
# so with the default window of 2 the adjacent text-bearing nodes are
# n3, n4 (preceding, document order) and n6 (following): exactly
# ("Introduction", "First paragraph text.", "Third paragraph text.").


def _tree() -> NodeBuilder:
    root = NodeBuilder(node_type=NodeType.DOCUMENT)
    section = root.add_child(NodeBuilder(node_type=NodeType.SECTION))
    section.add_child(NodeBuilder(node_type=NodeType.HEADING, text="Introduction"))
    section.add_child(NodeBuilder(node_type=NodeType.PARAGRAPH, text="First paragraph text."))
    section.add_child(NodeBuilder(node_type=NodeType.PARAGRAPH, text="Second paragraph text."))
    section.add_child(NodeBuilder(node_type=NodeType.PARAGRAPH, text="Third paragraph text."))
    return root


_DOCUMENT = build_document(
    root=_tree(),
    lane=LANE_SOURCE,
    parser_name="text",
    parser_version="1",
    policy=ImportPolicy(lane=LANE_SOURCE),
    surface_text=(
        "Introduction\nFirst paragraph text.\nSecond paragraph text.\nThird paragraph text."
    ),
)


_SIGNATURE = StructureSignature(
    signature="a" * 64,
    section_order=("Introduction",),
    node_type_counts={"document": 1, "section": 1, "heading": 1, "paragraph": 3},
    total_nodes=6,
)
_TEXT_SHA256 = "ab12" * 16  # 64 lowercase hex chars, hand-verified

_REVISION = create_initial_revision(
    document_id="doc-1",
    structure_signature=_SIGNATURE,
    accepted_text_sha256=_TEXT_SHA256,
)
_PROJECT = new_project_state(name="Demo", root=r"C:\demo")

_CLAIMS = (
    ClaimV2(
        claim_id="cl1",
        canonical_proposition="The sky is blue.",
        modality=Modality.ASSERTED,
        negation=False,
        attribution="",
        source_evidence_refs=("s1",),
        confidence=None,
        status=ClaimStatus.PROPOSED,
        contradictions=(),
        allowed_paraphrase_scope="exact",
    ),
    ClaimV2(
        claim_id="cl2",
        canonical_proposition="Rivers run downhill.",
        modality=Modality.ASSERTED,
        negation=False,
        attribution="",
        source_evidence_refs=("s2",),
        confidence=0.5,
        status=ClaimStatus.ACCEPTED,
        contradictions=(),
        allowed_paraphrase_scope="exact",
    ),
)
_SPANS = (
    ProtectedSpan(
        span_id="s1",
        kind=SpanKind.NUMBER,
        source_location=SourceLocation(start_offset=0, end_offset=9),
        text="300 units",
        status=SpanStatus.EXTRACTED,
    ),
    ProtectedSpan(
        span_id="s2",
        kind=SpanKind.DATE,
        source_location=SourceLocation(start_offset=10, end_offset=20),
        text="2024-05-01",
        status=SpanStatus.EXCLUDED,
    ),
)
_CITATIONS = (
    Citation(
        citation_id="c1",
        kind="author_year",
        text="(Smith, 2019)",
        source_location=SourceLocation(start_offset=0, end_offset=13),
    ),
)
_ENTITIES = (
    Entity(
        entity_id="e1",
        name="Acme Corporation",
        entity_type=EntityType.ORGANIZATION,
        aliases=(),
        evidence_refs=(),
    ),
    Entity(
        entity_id="e2",
        name="Paris",
        entity_type=EntityType.LOCATION,
        aliases=(),
        evidence_refs=(),
    ),
)


def _build(*, policy: ContextPolicy | None = None) -> ContextCapsule:
    return build_context_capsule(
        document=_DOCUMENT,
        revision=_REVISION,
        block_id="n5",
        project_state=_PROJECT,
        claims=_CLAIMS,
        protected_spans=_SPANS,
        citations=_CITATIONS,
        entities=_ENTITIES,
        profile=None,
        policy=policy if policy is not None else ContextPolicy(),
    )


class TestBuildContextCapsule:
    def test_deterministic_capsule_id(self) -> None:
        first = _build()
        second = _build()
        assert first == second
        assert first.capsule_id.startswith("cap-")
        assert len(first.capsule_id) == 4 + 24
        assert all(char in "0123456789abcdef" for char in first.capsule_id[4:])

    def test_block_text_and_document_fields(self) -> None:
        capsule = _build()
        assert capsule.project_id == _PROJECT.project_id
        assert capsule.document_id == "doc-1"
        assert capsule.revision_id == "rev-1"
        assert capsule.block_id == "n5"
        assert capsule.current_block_text == "Second paragraph text."
        assert capsule.section_goal == "Introduction"
        assert capsule.document_purpose == "First paragraph text."

    def test_adjacent_blocks_window_respected(self) -> None:
        assert _build().adjacent_block_texts == (
            "Introduction",
            "First paragraph text.",
            "Third paragraph text.",
        )
        narrow = _build(policy=ContextPolicy(block_window=1))
        assert narrow.adjacent_block_texts == ("First paragraph text.", "Third paragraph text.")

    def test_open_loops_are_proposed_claim_propositions(self) -> None:
        capsule = _build()
        assert capsule.open_loops == ("The sky is blue.",)

    def test_untrusted_labels_from_excluded_spans(self) -> None:
        assert _build().untrusted_source_labels == ("excluded_span:s2",)
        assert _build(
            policy=ContextPolicy(include_untrusted_labels=False)
        ).untrusted_source_labels == (())

    def test_ai_assisted_nodes_are_labeled(self) -> None:
        root = NodeBuilder(node_type=NodeType.DOCUMENT)
        section = root.add_child(NodeBuilder(node_type=NodeType.SECTION))
        section.add_child(NodeBuilder(node_type=NodeType.HEADING, text="Intro"))
        section.add_child(
            NodeBuilder(
                node_type=NodeType.PARAGRAPH,
                text="First paragraph text.",
                authorship_class="ai_assisted",
            )
        )
        document = build_document(
            root=root,
            lane=LANE_SOURCE,
            parser_name="text",
            parser_version="1",
            policy=ImportPolicy(lane=LANE_SOURCE),
            surface_text="Intro\nFirst paragraph text.",
        )
        capsule = build_context_capsule(
            document=document,
            revision=_REVISION,
            block_id="n4",
            project_state=_PROJECT,
            claims=(),
            protected_spans=(),
            citations=(),
            entities=(),
            profile=None,
            policy=ContextPolicy(),
        )
        assert capsule.untrusted_source_labels == ("ai_assisted:n4",)

    def test_caps_applied_to_claims_spans_and_entities(self) -> None:
        capsule = _build(policy=ContextPolicy(max_claims=1, max_protected_spans=1, max_entities=1))
        assert capsule.required_claims == (_CLAIMS[0],)
        assert capsule.protected_spans == (_SPANS[0],)
        assert capsule.entity_state == (_ENTITIES[0],)

    def test_citations_are_not_capped(self) -> None:
        assert _build().citations == _CITATIONS

    def test_profile_none_yields_empty_style_sections(self) -> None:
        capsule = _build()
        assert capsule.style_hard_invariants == ()
        assert capsule.style_soft_tendencies == ()
        assert capsule.approved_exemplars == ()
        assert capsule.prohibited_changes == ()

    def test_empty_document_raises(self) -> None:
        empty_document = replace(_DOCUMENT, nodes=())
        with pytest.raises(DomainError, match="empty document"):
            build_context_capsule(
                document=empty_document,
                revision=_REVISION,
                block_id="n5",
                project_state=_PROJECT,
                claims=(),
                protected_spans=(),
                citations=(),
                entities=(),
                profile=None,
                policy=ContextPolicy(),
            )

    def test_unknown_block_id_raises(self) -> None:
        with pytest.raises(DomainError, match="Unknown block node id"):
            build_context_capsule(
                document=_DOCUMENT,
                revision=_REVISION,
                block_id="n99",
                project_state=_PROJECT,
                claims=(),
                protected_spans=(),
                citations=(),
                entities=(),
                profile=None,
                policy=ContextPolicy(),
            )


class TestCapsuleJson:
    def test_to_json_twice_byte_identical(self) -> None:
        capsule = _build()
        assert capsule_to_json(capsule) == capsule_to_json(capsule)

    def test_from_json_round_trip(self) -> None:
        capsule = _build()
        assert capsule_from_json(capsule_to_json(capsule)) == capsule

    def test_from_json_rejects_tampered_capsule_id(self) -> None:
        payload = capsule_to_payload(_build())
        bad_payload: dict[str, object] = dict(payload)
        bad_payload["capsule_id"] = "cap-" + "0" * 24
        tampered = (
            json.dumps(bad_payload, ensure_ascii=False, separators=(",", ":"), sort_keys=True)
            + "\n"
        )
        with pytest.raises(DomainError, match="digest"):
            capsule_from_json(tampered)

    def test_from_json_rejects_bad_capsule_id_format(self) -> None:
        payload = capsule_to_payload(_build())
        bad_payload: dict[str, object] = dict(payload)
        bad_payload["capsule_id"] = "cap-xyz"
        tampered = (
            json.dumps(bad_payload, ensure_ascii=False, separators=(",", ":"), sort_keys=True)
            + "\n"
        )
        with pytest.raises(DomainError, match="capsule_id"):
            capsule_from_json(tampered)

    def test_from_json_rejects_invalid_json(self) -> None:
        with pytest.raises(DomainError, match="JSON"):
            capsule_from_json("not json at all")

    def test_from_json_round_trips_nested_records(self) -> None:
        capsule = _build()
        loaded = capsule_from_json(capsule_to_json(capsule))
        assert loaded.required_claims == _CLAIMS
        assert loaded.protected_spans == _SPANS
        assert loaded.citations == _CITATIONS
        assert loaded.entity_state == _ENTITIES


class TestValidateCapsule:
    def test_valid_capsule_has_no_violations(self) -> None:
        assert validate_capsule(_build(), ContextPolicy()) == ()

    def test_reports_claim_cap_violation(self) -> None:
        violations = validate_capsule(_build(), ContextPolicy(max_claims=1))
        assert any("required_claims" in violation for violation in violations)

    def test_reports_span_cap_violation(self) -> None:
        violations = validate_capsule(_build(), ContextPolicy(max_protected_spans=1))
        assert any("protected_spans" in violation for violation in violations)
