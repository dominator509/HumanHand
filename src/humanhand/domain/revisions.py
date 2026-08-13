"""Deterministic document revision semantics (SPEC-012, blueprint 9.5).

Revisions are optimistic: every proposed revision records the token of
the revision it was based on, and acceptance only succeeds when the
caller's ``expected_current`` still matches that base. A stale attempt
raises :class:`RevisionConflictError`; nothing is overwritten silently.
"""

from __future__ import annotations

from dataclasses import dataclass, replace
from enum import StrEnum

from humanhand.domain.structure_signature import StructureSignature
from humanhand.domain.types import DomainError

REVISION_SCHEMA_VERSION = 1
_SCHEMA_NAME = "document-revision"
_HEX_DIGITS = frozenset("0123456789abcdef")


class RevisionStatus(StrEnum):
    """Typed state of one document revision."""

    DRAFT = "draft"
    PROPOSED = "proposed"
    ACCEPTED = "accepted"
    REJECTED = "rejected"


class RevisionConflictError(DomainError):
    """Raised when a stale revision token attempts to overwrite state."""


@dataclass(frozen=True)
class DocumentRevision:
    """One immutable revision of a canonical document."""

    revision_id: str  # deterministic "rev-{token}" or provided string
    document_id: str
    parent_revision_id: str | None
    status: RevisionStatus
    base_token: int  # token this revision was based on
    token: int  # new token = base_token + 1 (monotonic)
    structure_signature: StructureSignature
    accepted_text_sha256: str
    created_note: str = ""


def create_initial_revision(
    *,
    document_id: str,
    structure_signature: StructureSignature,
    accepted_text_sha256: str,
) -> DocumentRevision:
    """Create the first ACCEPTED revision of a document (token 1).

    The initial revision has no parent (``parent_revision_id`` is None),
    ``base_token`` 0, and ``revision_id`` ``rev-1``.
    """
    return DocumentRevision(
        revision_id="rev-1",
        document_id=document_id,
        parent_revision_id=None,
        status=RevisionStatus.ACCEPTED,
        base_token=0,
        token=1,
        structure_signature=structure_signature,
        accepted_text_sha256=accepted_text_sha256,
    )


def propose_next_revision(
    *,
    current: DocumentRevision,
    structure_signature: StructureSignature,
    accepted_text_sha256: str,
    note: str = "",
) -> DocumentRevision:
    """Propose the next revision on top of ``current``.

    The proposal records ``current.token`` as its base token and
    ``current.revision_id`` as its parent, so a later acceptance is
    optimistic and conflict-checked.
    """
    return DocumentRevision(
        revision_id=f"rev-{current.token + 1}",
        document_id=current.document_id,
        parent_revision_id=current.revision_id,
        status=RevisionStatus.PROPOSED,
        base_token=current.token,
        token=current.token + 1,
        structure_signature=structure_signature,
        accepted_text_sha256=accepted_text_sha256,
        created_note=note,
    )


def accept_revision(
    *, proposed: DocumentRevision, expected_current: DocumentRevision
) -> DocumentRevision:
    """Optimistically accept ``proposed``.

    Returns the ACCEPTED revision only when ``expected_current`` still is
    the revision ``proposed`` was based on (token and revision id both
    match); otherwise raises :class:`RevisionConflictError`. No silent
    overwrite is possible.
    """
    if expected_current.token != proposed.base_token:
        raise RevisionConflictError(
            f"Stale revision: expected current token {proposed.base_token}, "
            f"got {expected_current.token}"
        )
    if expected_current.revision_id != proposed.parent_revision_id:
        raise RevisionConflictError(
            f"Stale revision: expected parent {proposed.parent_revision_id!r}, "
            f"got {expected_current.revision_id!r}"
        )
    return replace(proposed, status=RevisionStatus.ACCEPTED)


def reject_revision(proposed: DocumentRevision) -> DocumentRevision:
    """Mark ``proposed`` REJECTED without changing its tokens."""
    return replace(proposed, status=RevisionStatus.REJECTED)


def revision_to_payload(revision: DocumentRevision) -> dict[str, object]:
    """Render a revision as a stable JSON-ready payload."""
    return {
        "schema": _SCHEMA_NAME,
        "schema_version": REVISION_SCHEMA_VERSION,
        "revision_id": revision.revision_id,
        "document_id": revision.document_id,
        "parent_revision_id": revision.parent_revision_id,
        "status": revision.status.value,
        "base_token": revision.base_token,
        "token": revision.token,
        "accepted_text_sha256": revision.accepted_text_sha256,
        "created_note": revision.created_note,
        "structure_signature": {
            "signature": revision.structure_signature.signature,
            "section_order": list(revision.structure_signature.section_order),
            "node_type_counts": dict(revision.structure_signature.node_type_counts),
            "total_nodes": revision.structure_signature.total_nodes,
        },
    }


def _expect_str(payload: dict[str, object], key: str) -> str:
    value = payload.get(key)
    if not isinstance(value, str):
        raise DomainError(f"Invalid revision payload: {key} must be a string")
    return value


def _expect_int(payload: dict[str, object], key: str) -> int:
    value = payload.get(key)
    if not isinstance(value, int) or isinstance(value, bool):
        raise DomainError(f"Invalid revision payload: {key} must be an integer")
    return value


def _expect_sha256_hex(value: str, what: str) -> str:
    if len(value) != 64 or any(char not in _HEX_DIGITS for char in value):
        raise DomainError(f"Invalid revision payload: {what} must be a 64-char sha256 hex digest")
    return value


def _signature_from_payload(payload: dict[str, object]) -> StructureSignature:
    signature = _expect_sha256_hex(
        _expect_str(payload, "signature"), "structure_signature.signature"
    )
    raw_order = payload.get("section_order")
    if not isinstance(raw_order, list):
        raise DomainError(
            "Invalid revision payload: structure_signature.section_order must be a list"
        )
    if not all(isinstance(item, str) for item in raw_order):
        raise DomainError(
            "Invalid revision payload: structure_signature.section_order must contain only strings"
        )
    raw_counts = payload.get("node_type_counts")
    if not isinstance(raw_counts, dict):
        raise DomainError(
            "Invalid revision payload: structure_signature.node_type_counts must be an object"
        )
    counts: dict[str, int] = {}
    for key, value in raw_counts.items():
        if not isinstance(key, str) or not isinstance(value, int) or isinstance(value, bool):
            raise DomainError(
                "Invalid revision payload: structure_signature.node_type_counts "
                "must map strings to integers"
            )
        if value < 0:
            raise DomainError(
                "Invalid revision payload: structure_signature.node_type_counts "
                "values must be non-negative"
            )
        counts[key] = value
    total_nodes = _expect_int(payload, "total_nodes")
    if total_nodes < 0:
        raise DomainError(
            "Invalid revision payload: structure_signature.total_nodes must be non-negative"
        )
    return StructureSignature(
        signature=signature,
        section_order=tuple(raw_order),
        node_type_counts=counts,
        total_nodes=total_nodes,
    )


def revision_from_payload(payload: dict[str, object]) -> DocumentRevision:
    """Deserialize and validate a revision payload (strict, fails closed)."""
    if payload.get("schema") != _SCHEMA_NAME:
        raise DomainError("Invalid revision payload: schema must be 'document-revision'")
    if payload.get("schema_version") != REVISION_SCHEMA_VERSION:
        raise DomainError("Unsupported revision payload schema version")
    revision_id = _expect_str(payload, "revision_id")
    document_id = _expect_str(payload, "document_id")
    parent_value = payload.get("parent_revision_id")
    if parent_value is not None and not isinstance(parent_value, str):
        raise DomainError("Invalid revision payload: parent_revision_id must be a string or null")
    status_value = _expect_str(payload, "status")
    try:
        status = RevisionStatus(status_value)
    except ValueError as exc:
        raise DomainError(f"Invalid revision payload: unknown status {status_value!r}") from exc
    base_token = _expect_int(payload, "base_token")
    token = _expect_int(payload, "token")
    if token != base_token + 1:
        raise DomainError("Invalid revision payload: token must be base_token + 1")
    accepted_text_sha256 = _expect_sha256_hex(
        _expect_str(payload, "accepted_text_sha256"), "accepted_text_sha256"
    )
    created_note = _expect_str(payload, "created_note")
    raw_signature = payload.get("structure_signature")
    if not isinstance(raw_signature, dict):
        raise DomainError("Invalid revision payload: structure_signature must be an object")
    return DocumentRevision(
        revision_id=revision_id,
        document_id=document_id,
        parent_revision_id=parent_value,
        status=status,
        base_token=base_token,
        token=token,
        structure_signature=_signature_from_payload(raw_signature),
        accepted_text_sha256=accepted_text_sha256,
        created_note=created_note,
    )
