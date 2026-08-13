"""Unit tests for the deterministic lexical review journal (EP-017).

The review journal imports the lexical proposal module, which imports
the parallel lexical modules (lexical_rules, lexical_types,
lexical_context) owned by other workstreams.
"""

from __future__ import annotations

import pytest

from humanhand.domain.lexical_normalizer import (
    LEXICAL_PROPOSAL_SCHEMA_VERSION,
    ChangeStatus,
    LexicalChange,
    LexicalProposal,
    compute_run_id,
    proposal_from_payload,
    proposal_to_payload,
)
from humanhand.domain.lexical_review import (
    LexicalReviewJournal,
    ReviewDecision,
    apply_review,
    build_review_journal,
    revalidate_facts_and_citations,
    revalidate_structure,
    review_from_payload,
    review_to_payload,
)
from humanhand.domain.structure_signature import StructureSignature
from humanhand.domain.types import DomainError


def _change(
    change_id: str, *, target: str = "use", offset: int = 3, length: int = 7
) -> LexicalChange:
    return LexicalChange(
        change_id=change_id,
        offset=offset,
        length=length,
        source_surface="utilize",
        target=target,
        reason="rule-1:verb",
        precedence="curated_rule",
        confidence=0.9,
        status=ChangeStatus.SAFE,
        rule_id="rule-1",
        sense="verb",
        ruleset_hash="rs-1",
    )


def _proposal(*changes: LexicalChange, findings: tuple[str, ...] = ()) -> LexicalProposal:
    raw = LexicalProposal(
        proposal_id="",
        run_id="",
        ruleset_hash="rs-1",
        document_hash="ab12" * 16,
        schema_version=LEXICAL_PROPOSAL_SCHEMA_VERSION,
        changes=tuple(changes),
        findings=findings,
    )
    payload = proposal_to_payload(raw)
    run_id = compute_run_id(
        {key: value for key, value in payload.items() if key not in ("run_id", "proposal_id")}
    )
    payload["run_id"] = run_id
    payload["proposal_id"] = run_id
    return proposal_from_payload(payload)


def _decision(change_id: str, decision: str = "accept") -> ReviewDecision:
    return ReviewDecision(change_id=change_id, decision=decision)


def _journal(
    *decisions: ReviewDecision, proposal_run_id: str = "run-" + "a" * 24
) -> LexicalReviewJournal:
    return build_review_journal(proposal_run_id=proposal_run_id, decisions=tuple(decisions))


class TestBuildReviewJournal:
    def test_round_trip(self) -> None:
        journal = _journal(_decision("ch1"), _decision("ch2", "reject"))
        assert review_from_payload(review_to_payload(journal)) == journal

    def test_journal_id_is_deterministic(self) -> None:
        assert _journal(_decision("ch1")).journal_id == _journal(_decision("ch1")).journal_id

    def test_duplicate_decision_rejected(self) -> None:
        with pytest.raises(DomainError, match="[Dd]uplicate"):
            _journal(_decision("ch1"), _decision("ch1"))

    def test_invalid_decision_value_rejected(self) -> None:
        with pytest.raises(DomainError, match="decision"):
            _journal(_decision("ch1", "maybe"))

    def test_malformed_proposal_run_id_rejected(self) -> None:
        with pytest.raises(DomainError, match="run_id"):
            build_review_journal(proposal_run_id="nope", decisions=())


class TestReviewPayloadStrictness:
    def test_wrong_schema_rejected(self) -> None:
        payload = review_to_payload(_journal(_decision("ch1")))
        bad: dict[str, object] = dict(payload)
        bad["schema"] = "other"
        with pytest.raises(DomainError, match="schema"):
            review_from_payload(bad)

    def test_wrong_schema_version_rejected(self) -> None:
        payload = review_to_payload(_journal(_decision("ch1")))
        bad: dict[str, object] = dict(payload)
        bad["schema_version"] = 99
        with pytest.raises(DomainError, match="schema version"):
            review_from_payload(bad)

    def test_tampered_journal_id_rejected(self) -> None:
        payload = review_to_payload(_journal(_decision("ch1")))
        bad: dict[str, object] = dict(payload)
        bad["journal_id"] = "journal-" + "b" * 24
        with pytest.raises(DomainError, match="journal_id"):
            review_from_payload(bad)

    def test_decisions_must_be_a_list(self) -> None:
        payload = review_to_payload(_journal(_decision("ch1")))
        bad: dict[str, object] = dict(payload)
        bad["decisions"] = "nope"
        with pytest.raises(DomainError, match="decisions"):
            review_from_payload(bad)


class TestApplyReview:
    def test_accept_subset_applies_only_accepted(self) -> None:
        proposal = _proposal(_change("ch1"), _change("ch2"))
        reviewed = apply_review(proposal, _journal(_decision("ch1")))
        assert [c.change_id for c in reviewed.changes] == ["ch1"]
        assert reviewed.document_hash == proposal.document_hash
        assert reviewed.run_id != proposal.run_id

    def test_reject_all_leaves_no_changes(self) -> None:
        proposal = _proposal(_change("ch1"))
        reviewed = apply_review(proposal, _journal(_decision("ch1", "reject")))
        assert reviewed.changes == ()

    def test_missing_approval_drops_change(self) -> None:
        proposal = _proposal(_change("ch1"), _change("ch2"))
        reviewed = apply_review(proposal, _journal(_decision("ch1")))
        assert [c.change_id for c in reviewed.changes] == ["ch1"]

    def test_unknown_change_id_rejected(self) -> None:
        proposal = _proposal(_change("ch1"))
        with pytest.raises(DomainError, match="unknown"):
            apply_review(proposal, _journal(_decision("ch9")))

    def test_duplicate_decisions_rejected(self) -> None:
        proposal = _proposal(_change("ch1"))
        with pytest.raises(DomainError, match="[Dd]uplicate"):
            apply_review(proposal, _journal(_decision("ch1"), _decision("ch1", "reject")))

    def test_original_proposal_is_untouched(self) -> None:
        proposal = _proposal(_change("ch1"), _change("ch2"))
        reviewed = apply_review(proposal, _journal(_decision("ch1")))
        assert [c.change_id for c in proposal.changes] == ["ch1", "ch2"]
        assert reviewed is not proposal


class TestProposalRoundTrip:
    def test_round_trip(self) -> None:
        proposal = _proposal(_change("ch1"), _change("ch2", target="used"))
        restored = proposal_from_payload(proposal_to_payload(proposal))
        assert restored == proposal

    def test_payload_is_deterministic(self) -> None:
        first = proposal_to_payload(_proposal(_change("ch1")))
        second = proposal_to_payload(_proposal(_change("ch1")))
        assert first == second

    def test_tampered_status_rejected(self) -> None:
        payload = proposal_to_payload(_proposal(_change("ch1")))
        bad: dict[str, object] = dict(payload)
        changes = bad["changes"]
        assert isinstance(changes, list)
        assert isinstance(changes[0], dict)
        first: dict[str, object] = dict(changes[0])
        first["status"] = "bogus"
        changes[0] = first
        with pytest.raises(DomainError, match="status"):
            proposal_from_payload(bad)

    def test_tampered_confidence_rejected(self) -> None:
        payload = proposal_to_payload(_proposal(_change("ch1")))
        bad: dict[str, object] = dict(payload)
        changes = bad["changes"]
        assert isinstance(changes, list)
        assert isinstance(changes[0], dict)
        first: dict[str, object] = dict(changes[0])
        first["confidence"] = 1.5
        changes[0] = first
        with pytest.raises(DomainError, match="confidence"):
            proposal_from_payload(bad)

    def test_tampered_run_id_rejected(self) -> None:
        payload = proposal_to_payload(_proposal(_change("ch1")))
        bad: dict[str, object] = dict(payload)
        bad["run_id"] = "run-" + "b" * 24
        with pytest.raises(DomainError, match="run_id"):
            proposal_from_payload(bad)

    def test_wrong_schema_rejected(self) -> None:
        payload = proposal_to_payload(_proposal(_change("ch1")))
        bad: dict[str, object] = dict(payload)
        bad["schema"] = "other"
        with pytest.raises(DomainError, match="schema"):
            proposal_from_payload(bad)

    def test_non_sequential_change_ids_rejected(self) -> None:
        payload = proposal_to_payload(_proposal(_change("ch1")))
        bad: dict[str, object] = dict(payload)
        changes = bad["changes"]
        assert isinstance(changes, list)
        assert isinstance(changes[0], dict)
        first: dict[str, object] = dict(changes[0])
        first["change_id"] = "ch9"
        changes[0] = first
        with pytest.raises(DomainError, match="change_id"):
            proposal_from_payload(bad)

    def test_negative_offset_rejected(self) -> None:
        payload = proposal_to_payload(_proposal(_change("ch1")))
        bad: dict[str, object] = dict(payload)
        changes = bad["changes"]
        assert isinstance(changes, list)
        assert isinstance(changes[0], dict)
        first: dict[str, object] = dict(changes[0])
        first["offset"] = -1
        changes[0] = first
        with pytest.raises(DomainError, match="offset"):
            proposal_from_payload(bad)

    def test_mismatched_change_ruleset_hash_rejected(self) -> None:
        payload = proposal_to_payload(_proposal(_change("ch1")))
        bad: dict[str, object] = dict(payload)
        changes = bad["changes"]
        assert isinstance(changes, list)
        assert isinstance(changes[0], dict)
        first: dict[str, object] = dict(changes[0])
        first["ruleset_hash"] = "other"
        changes[0] = first
        with pytest.raises(DomainError, match="ruleset_hash"):
            proposal_from_payload(bad)


def _signature(
    signature: str = "a" * 64, section_order: tuple[str, ...] = ("Intro",)
) -> StructureSignature:
    return StructureSignature(
        signature=signature,
        section_order=section_order,
        node_type_counts={"document": 1, "section": 1, "paragraph": 1},
        total_nodes=3,
    )


class TestRevalidateStructure:
    def test_identical_signatures_pass(self) -> None:
        ok, findings = revalidate_structure(_signature(), _signature())
        assert ok is True
        assert findings == ()

    def test_section_order_drift_reported(self) -> None:
        current = _signature(section_order=("Intro", "Body"))
        ok, findings = revalidate_structure(current, _signature())
        assert ok is False
        assert findings == ("structure_section_order_drift:first_diff_index=1",)

    def test_section_order_diff_at_first_index(self) -> None:
        current = _signature(section_order=("Other",))
        ok, findings = revalidate_structure(current, _signature())
        assert ok is False
        assert findings == ("structure_section_order_drift:first_diff_index=0",)

    def test_digest_drift_with_same_section_order(self) -> None:
        current = _signature(signature="b" * 64)
        ok, findings = revalidate_structure(current, _signature())
        assert ok is False
        assert findings == ("structure_signature_drift:same_section_order",)


class TestRevalidateFactsAndCitations:
    def test_lexical_only_change_preserves_invariants(self) -> None:
        ok, findings = revalidate_facts_and_citations(
            "We utilize the method in [1].",
            "We use the method in [1].",
        )
        assert ok is True
        assert findings == ()

    def test_number_drift_fails_without_echoing_text(self) -> None:
        ok, findings = revalidate_facts_and_citations("The result was 42.", "The result was 43.")
        assert ok is False
        assert findings == ("fact_anchor_drift:omissions=1,additions=1,contradictions=0",)
        assert "42" not in findings[0]
        assert "43" not in findings[0]

    def test_citation_drift_is_explicit(self) -> None:
        ok, findings = revalidate_facts_and_citations(
            "The result is documented [1].", "The result is documented [2]."
        )
        assert ok is False
        assert any(item.startswith("citation_drift:") for item in findings)
