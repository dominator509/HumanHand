"""Deterministic lexical review journal (EP-017).

A review journal records accept/reject decisions for a proposal's
changes. Review semantics (documented):

- A change is applied only when its change_id has an explicit
  ``"accept"`` decision; missing approval means the change is dropped
  (no change).
- Duplicate decisions for the same change_id are rejected; first-
  mention-wins is NOT used.
- Decisions for change_ids unknown to the proposal are rejected.
- The journal's ``proposal_run_id`` is NOT cross-checked against the
  proposal by design: the journal is an append-only record and the
  caller decides which proposal it belongs to (documented contract).
- The reviewed proposal is a new run: ``run_id``/``proposal_id`` are
  recomputed over the reviewed payload; ``document_hash`` and
  ``ruleset_hash`` are preserved.

Payload schema name is ``"lexical-review"`` with
``LEXICAL_REVIEW_SCHEMA_VERSION == 1``; parsing is strict and rejects
tampered payloads with DomainError. The ``journal_id`` is
``"journal-"`` plus the first 24 hex characters of the sha256 digest
of the payload WITHOUT the ``journal_id`` key.

Structure revalidation
----------------------
``revalidate_structure`` compares the structure signature of the
document as it stands against the signature recorded when the proposal
was created, and reports drift findings. ``text_before``/``text_after``
seams were considered and deliberately left out of the signature;
callers that need text-level drift checks should compare hashes
themselves (reserved for a future integration that re-extracts
structure from text).
"""

from __future__ import annotations

import hashlib
from dataclasses import dataclass

from humanhand.domain.document_serialization import dumps_stable
from humanhand.domain.facts import diff_facts, extract_fact_anchors
from humanhand.domain.lexical_normalizer import (
    LEXICAL_PROPOSAL_SCHEMA_VERSION,
    LexicalProposal,
    compute_run_id,
    core_proposal_payload,
)
from humanhand.domain.structure_signature import StructureSignature
from humanhand.domain.types import DomainError

LEXICAL_REVIEW_SCHEMA_VERSION = 1
_REVIEW_SCHEMA_NAME = "lexical-review"
_JOURNAL_ID_PREFIX = "journal-"
_JOURNAL_ID_HEX_LENGTH = 24
_ACCEPT = "accept"
_REJECT = "reject"
_VALID_DECISIONS = frozenset({_ACCEPT, _REJECT})


@dataclass(frozen=True)
class ReviewDecision:
    """One accept/reject decision for one change."""

    change_id: str
    decision: str


@dataclass(frozen=True)
class LexicalReviewJournal:
    """Immutable record of review decisions for one proposal run."""

    journal_id: str
    schema_version: int
    proposal_run_id: str
    decisions: tuple[ReviewDecision, ...]


def build_review_journal(
    proposal_run_id: str, decisions: tuple[ReviewDecision, ...]
) -> LexicalReviewJournal:
    """Build a deterministic review journal for a proposal run."""
    _validate_run_id(proposal_run_id)
    _validate_decisions(decisions)
    payload = _journal_core_payload(proposal_run_id, decisions)
    journal_id = _journal_id(payload)
    return LexicalReviewJournal(
        journal_id=journal_id,
        schema_version=LEXICAL_REVIEW_SCHEMA_VERSION,
        proposal_run_id=proposal_run_id,
        decisions=decisions,
    )


def review_to_payload(journal: LexicalReviewJournal) -> dict[str, object]:
    """Render a journal as its canonical JSON-ready mapping."""
    payload = _journal_core_payload(journal.proposal_run_id, journal.decisions)
    payload["journal_id"] = journal.journal_id
    return payload


def review_from_payload(payload: dict[str, object]) -> LexicalReviewJournal:
    """Strictly parse and validate a review journal payload."""
    if payload.get("schema") != _REVIEW_SCHEMA_NAME:
        raise DomainError(f"Invalid review journal JSON: schema must be {_REVIEW_SCHEMA_NAME!r}")
    schema_version = _expect_int(payload, "schema_version", "schema_version")
    if schema_version != LEXICAL_REVIEW_SCHEMA_VERSION:
        raise DomainError(f"Unsupported review journal schema version: {schema_version}")
    journal_id = payload.get("journal_id")
    if not isinstance(journal_id, str):
        raise DomainError("Invalid review journal JSON: journal_id must be a string")
    proposal_run_id = _expect_str(payload, "proposal_run_id", "proposal_run_id")
    _validate_run_id(proposal_run_id)
    raw_decisions = payload.get("decisions")
    if not isinstance(raw_decisions, list):
        raise DomainError("Invalid review journal JSON: decisions must be a list")
    decisions = tuple(
        _decision_from_payload(item, index)
        for index, item in enumerate(raw_decisions)
        if isinstance(item, dict)
    )
    if len(decisions) != len(raw_decisions):
        raise DomainError("Invalid review journal JSON: decisions must contain only objects")
    _validate_decisions(decisions)
    core = {key: value for key, value in payload.items() if key != "journal_id"}
    if journal_id != _journal_id(core):
        raise DomainError("Invalid review journal JSON: journal_id does not match payload")
    return LexicalReviewJournal(
        journal_id=journal_id,
        schema_version=schema_version,
        proposal_run_id=proposal_run_id,
        decisions=decisions,
    )


def apply_review(proposal: LexicalProposal, journal: LexicalReviewJournal) -> LexicalProposal:
    """Return a new proposal containing only explicitly accepted changes.

    Changes without an explicit ``"accept"`` decision are dropped
    (missing approval -> no change). The journal must be valid
    (schema version, decision values, duplicates) and may only name
    change_ids that exist in the proposal. The reviewed proposal is a
    new run: ``run_id``/``proposal_id`` are recomputed over the
    reviewed payload; ``document_hash`` and ``ruleset_hash`` are
    preserved.
    """
    if journal.schema_version != LEXICAL_REVIEW_SCHEMA_VERSION:
        raise DomainError(f"Unsupported review journal schema version: {journal.schema_version}")
    _validate_decisions(journal.decisions)
    known_ids = {change.change_id for change in proposal.changes}
    for decision in journal.decisions:
        if decision.change_id not in known_ids:
            raise DomainError(f"Review decision for unknown change {decision.change_id}")
    accepted_ids = frozenset(
        decision.change_id for decision in journal.decisions if decision.decision == _ACCEPT
    )
    accepted = tuple(change for change in proposal.changes if change.change_id in accepted_ids)
    run_id = compute_run_id(
        core_proposal_payload(
            proposal.ruleset_hash, proposal.document_hash, accepted, proposal.findings
        )
    )
    return LexicalProposal(
        proposal_id=run_id,
        run_id=run_id,
        ruleset_hash=proposal.ruleset_hash,
        document_hash=proposal.document_hash,
        schema_version=LEXICAL_PROPOSAL_SCHEMA_VERSION,
        changes=accepted,
        findings=proposal.findings,
    )


def revalidate_structure(
    current: StructureSignature, expected: StructureSignature
) -> tuple[bool, tuple[str, ...]]:
    """Detect structural drift between two structure signatures.

    Returns ``(False, findings)`` with one finding when the section
    order changed (``structure_section_order_drift:first_diff_index=N``,
    N = first differing index) or when the section order matches but
    the structural digest differs (``structure_signature_drift:
    same_section_order``); ``(True, ())`` when signatures agree. The
    digest covers node types and counts, so equal digests imply equal
    structures; comparing section order first only improves the
    diagnostic message.
    """
    if current.section_order != expected.section_order:
        index = _first_diff_index(current.section_order, expected.section_order)
        return False, (f"structure_section_order_drift:first_diff_index={index}",)
    if current.signature != expected.signature:
        return False, ("structure_signature_drift:same_section_order",)
    return True, ()


def revalidate_facts_and_citations(
    original_text: str, finalized_text: str
) -> tuple[bool, tuple[str, ...]]:
    """Fail closed when lexical finalization changes factual anchors or citations.

    Findings contain counts only so callers can report drift without copying
    document text into logs or journals.
    """
    findings: list[str] = []
    report = diff_facts(original_text, finalized_text)
    if report.has_drift:
        findings.append(
            "fact_anchor_drift:"
            f"omissions={len(report.omissions)},"
            f"additions={len(report.additions)},"
            f"contradictions={len(report.contradictions)}"
        )
    original_citations = tuple(
        anchor.text
        for anchor in extract_fact_anchors(original_text)
        if anchor.category == "citation"
    )
    finalized_citations = tuple(
        anchor.text
        for anchor in extract_fact_anchors(finalized_text)
        if anchor.category == "citation"
    )
    if finalized_citations != original_citations:
        findings.append(
            f"citation_drift:expected={len(original_citations)},current={len(finalized_citations)}"
        )
    return not findings, tuple(findings)


def _validate_decisions(decisions: tuple[ReviewDecision, ...]) -> None:
    seen: set[str] = set()
    for decision in decisions:
        if not decision.change_id:
            raise DomainError("Review decision change_id must be non-empty")
        if decision.decision not in _VALID_DECISIONS:
            raise DomainError(
                f"Invalid review decision {decision.decision!r} for change {decision.change_id}"
            )
        if decision.change_id in seen:
            raise DomainError(f"Duplicate review decision for change {decision.change_id}")
        seen.add(decision.change_id)


def _journal_core_payload(
    proposal_run_id: str, decisions: tuple[ReviewDecision, ...]
) -> dict[str, object]:
    return {
        "schema": _REVIEW_SCHEMA_NAME,
        "schema_version": LEXICAL_REVIEW_SCHEMA_VERSION,
        "proposal_run_id": proposal_run_id,
        "decisions": [
            {"change_id": decision.change_id, "decision": decision.decision}
            for decision in decisions
        ],
    }


def _journal_id(core_payload: dict[str, object]) -> str:
    digest = hashlib.sha256(dumps_stable(core_payload).encode("utf-8")).hexdigest()
    return f"{_JOURNAL_ID_PREFIX}{digest[:_JOURNAL_ID_HEX_LENGTH]}"


def _decision_from_payload(item: dict[str, object], index: int) -> ReviewDecision:
    return ReviewDecision(
        change_id=_expect_str(item, "change_id", f"decisions[{index}].change_id"),
        decision=_expect_str(item, "decision", f"decisions[{index}].decision"),
    )


def _first_diff_index(left: tuple[str, ...], right: tuple[str, ...]) -> int:
    for index, (left_item, right_item) in enumerate(zip(left, right, strict=False)):
        if left_item != right_item:
            return index
    return min(len(left), len(right))


def _expect_str(payload: dict[str, object], key: str, what: str) -> str:
    value = payload.get(key)
    if not isinstance(value, str):
        raise DomainError(f"Invalid review journal JSON: {what} must be a string")
    return value


def _expect_int(payload: dict[str, object], key: str, what: str) -> int:
    value = payload.get(key)
    if not isinstance(value, int) or isinstance(value, bool):
        raise DomainError(f"Invalid review journal JSON: {what} must be an integer")
    return value


def _validate_run_id(run_id: str) -> None:
    if not run_id.startswith("run-") or len(run_id) != 28:
        raise DomainError("Invalid review journal JSON: malformed proposal_run_id")
    if any(char not in "0123456789abcdef" for char in run_id[4:]):
        raise DomainError("Invalid review journal JSON: proposal_run_id must be lowercase hex")
