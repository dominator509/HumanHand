"""Unit tests for optimistic document revision semantics."""

from __future__ import annotations

import pytest

from humanhand.domain.revisions import (
    DocumentRevision,
    RevisionConflictError,
    RevisionStatus,
    accept_revision,
    create_initial_revision,
    propose_next_revision,
    reject_revision,
    revision_from_payload,
    revision_to_payload,
)
from humanhand.domain.structure_signature import StructureSignature
from humanhand.domain.types import DomainError

_SIGNATURE = StructureSignature(
    signature="a" * 64,
    section_order=("Intro",),
    node_type_counts={"document": 1, "section": 1, "heading": 1, "paragraph": 2},
    total_nodes=5,
)
_TEXT_SHA256 = "ab12" * 16  # 64 lowercase hex chars, hand-verified


def _initial() -> DocumentRevision:
    return create_initial_revision(
        document_id="doc-1",
        structure_signature=_SIGNATURE,
        accepted_text_sha256=_TEXT_SHA256,
    )


class TestCreateInitialRevision:
    def test_token_one_accepted_no_parent(self) -> None:
        revision = _initial()
        assert revision.revision_id == "rev-1"
        assert revision.document_id == "doc-1"
        assert revision.parent_revision_id is None
        assert revision.status is RevisionStatus.ACCEPTED
        assert revision.base_token == 0
        assert revision.token == 1
        assert revision.structure_signature == _SIGNATURE
        assert revision.accepted_text_sha256 == _TEXT_SHA256
        assert revision.created_note == ""


class TestProposeNextRevision:
    def test_increments_token_and_parent(self) -> None:
        proposed = propose_next_revision(
            current=_initial(),
            structure_signature=_SIGNATURE,
            accepted_text_sha256=_TEXT_SHA256,
            note="rewrite paragraph two",
        )
        assert proposed.revision_id == "rev-2"
        assert proposed.parent_revision_id == "rev-1"
        assert proposed.status is RevisionStatus.PROPOSED
        assert proposed.base_token == 1
        assert proposed.token == 2
        assert proposed.created_note == "rewrite paragraph two"


class TestAcceptRevision:
    def test_matching_expected_current_succeeds(self) -> None:
        initial = _initial()
        proposed = propose_next_revision(
            current=initial,
            structure_signature=_SIGNATURE,
            accepted_text_sha256=_TEXT_SHA256,
        )
        accepted = accept_revision(proposed=proposed, expected_current=initial)
        assert accepted.status is RevisionStatus.ACCEPTED
        assert accepted.revision_id == "rev-2"
        assert accepted.token == 2
        assert accepted.base_token == 1
        # The accepted revision is a new object; the proposal is untouched.
        assert proposed.status is RevisionStatus.PROPOSED

    def test_stale_token_raises_conflict(self) -> None:
        initial = _initial()
        proposed = propose_next_revision(
            current=initial,
            structure_signature=_SIGNATURE,
            accepted_text_sha256=_TEXT_SHA256,
        )
        newer = propose_next_revision(
            current=proposed,
            structure_signature=_SIGNATURE,
            accepted_text_sha256=_TEXT_SHA256,
        )
        # Accepting the stale proposal against the newer current must fail.
        with pytest.raises(RevisionConflictError, match="token"):
            accept_revision(proposed=proposed, expected_current=newer)

    def test_wrong_parent_revision_id_raises_conflict(self) -> None:
        initial = _initial()
        proposed = propose_next_revision(
            current=initial,
            structure_signature=_SIGNATURE,
            accepted_text_sha256=_TEXT_SHA256,
        )
        # A current with the same token (1) but a different revision id
        # must still be rejected: token equality alone is not enough.
        expected = DocumentRevision(
            revision_id="rev-99",
            document_id="doc-1",
            parent_revision_id=None,
            status=RevisionStatus.ACCEPTED,
            base_token=0,
            token=1,
            structure_signature=_SIGNATURE,
            accepted_text_sha256=_TEXT_SHA256,
        )
        with pytest.raises(RevisionConflictError, match="parent"):
            accept_revision(proposed=proposed, expected_current=expected)


class TestRejectRevision:
    def test_reject_sets_rejected(self) -> None:
        proposed = propose_next_revision(
            current=_initial(),
            structure_signature=_SIGNATURE,
            accepted_text_sha256=_TEXT_SHA256,
        )
        rejected = reject_revision(proposed)
        assert rejected.status is RevisionStatus.REJECTED
        assert rejected.revision_id == proposed.revision_id
        assert rejected.token == proposed.token
        assert proposed.status is RevisionStatus.PROPOSED


class TestRevisionPayload:
    def test_round_trip(self) -> None:
        revision = propose_next_revision(
            current=_initial(),
            structure_signature=_SIGNATURE,
            accepted_text_sha256=_TEXT_SHA256,
            note="rewrite paragraph two",
        )
        assert revision_from_payload(revision_to_payload(revision)) == revision

    def test_initial_revision_round_trip(self) -> None:
        assert revision_from_payload(revision_to_payload(_initial())) == _initial()

    def test_deterministic_payload(self) -> None:
        first = revision_to_payload(_initial())
        second = revision_to_payload(_initial())
        assert first == second

    def test_rejects_unknown_status(self) -> None:
        payload = revision_to_payload(_initial())
        bad_payload: dict[str, object] = dict(payload)
        bad_payload["status"] = "bogus"
        with pytest.raises(DomainError, match="status"):
            revision_from_payload(bad_payload)

    def test_rejects_token_not_base_plus_one(self) -> None:
        payload = revision_to_payload(_initial())
        bad_payload: dict[str, object] = dict(payload)
        bad_payload["token"] = 3
        with pytest.raises(DomainError, match="base_token"):
            revision_from_payload(bad_payload)

    def test_rejects_malformed_text_sha256(self) -> None:
        payload = revision_to_payload(_initial())
        bad_payload: dict[str, object] = dict(payload)
        bad_payload["accepted_text_sha256"] = "not-hex"
        with pytest.raises(DomainError, match="sha256"):
            revision_from_payload(bad_payload)

    def test_rejects_negative_total_nodes(self) -> None:
        payload = revision_to_payload(_initial())
        bad_payload: dict[str, object] = dict(payload)
        raw_signature = bad_payload["structure_signature"]
        assert isinstance(raw_signature, dict)
        bad_signature: dict[str, object] = dict(raw_signature)
        bad_signature["total_nodes"] = -1
        bad_payload["structure_signature"] = bad_signature
        with pytest.raises(DomainError, match="total_nodes"):
            revision_from_payload(bad_payload)
