"""Deterministic inspectable context for one document block (blueprint 9.6).

Capsules are pure projections of already-existing domain records — a
canonical document, a revision, a project, claims, protected spans,
citations, entities, and an optional style profile — assembled for
inspection and testing only. NO model client exists and this module must
not add one.

Determinism: ``capsule_id`` is the sha256 digest (24 hex chars, prefixed
``cap-``) of the stable JSON payload of the capsule WITHOUT its own
``capsule_id`` field (``dumps_stable`` conventions from
:mod:`humanhand.domain.document_serialization`). ``capsule_from_json``
re-derives the id from the parsed payload and rejects any mismatch — the
id is an integrity anchor, and a tampered capsule fails closed.

Documented heuristics (never invented, documented in the build docstring):

- ``adjacent_block_texts``: the ``block_window`` nearest preceding and
  following text-bearing nodes (PARAGRAPH or HEADING nodes with non-empty
  text, by document node order, excluding the block itself), exact texts;
  preceding blocks first in document order, then following blocks. At most
  ``2 * block_window`` entries total.
- ``section_goal``: the exact text of the nearest HEADING node before the
  block, or "".
- ``document_purpose``: the exact text of the first PARAGRAPH node, or "".
- ``open_loops``: the canonical propositions of claims whose status is
  PROPOSED.
- ``prohibited_changes``: the value of every hard invariant with kind
  PROHIBITED_PHRASES, parsed on "|" with empty segments dropped and
  duplicates removed in first-seen order; empty when the profile is None.
- ``untrusted_source_labels``: ``ai_assisted:{node_id}`` for every node
  whose authorship class is "ai_assisted" (document order), followed by
  ``excluded_span:{span_id}`` for every protected span with status
  EXCLUDED (given order); empty when ``include_untrusted_labels`` is
  False.

Caps: claims, protected spans, entities, invariants, and tendencies are
truncated to their policy limits; citations are not capped (the policy
defines no citation limit).

``approved_exemplars`` is always empty on this assembly path: the function
signature receives only a ``StyleEvidenceProfile``, and exemplars live on
``StyleEvidencePackage`` (style_artifacts), which this function does not
receive. No exemplars are ever invented.
"""

from __future__ import annotations

import dataclasses
import hashlib
import json
import types
import typing
from dataclasses import dataclass, replace
from enum import StrEnum
from typing import Any

from humanhand.domain.canonical_document import CanonicalDocument
from humanhand.domain.citations import Citation
from humanhand.domain.claims_v2 import ClaimStatus, ClaimV2
from humanhand.domain.context_policy import ContextPolicy, validate_policy
from humanhand.domain.document_nodes import DocumentNode, NodeType
from humanhand.domain.document_serialization import dumps_stable
from humanhand.domain.entities import Entity
from humanhand.domain.project import ProjectState
from humanhand.domain.protected_spans import ProtectedSpan, SpanStatus
from humanhand.domain.revisions import DocumentRevision
from humanhand.domain.style_artifacts import StyleExemplar
from humanhand.domain.style_invariants import (
    InvariantKind,
    StyleInvariant,
    StyleTendency,
)
from humanhand.domain.style_profiles import StyleEvidenceProfile
from humanhand.domain.types import DomainError

CONTEXT_CAPSULE_SCHEMA_VERSION = 1
_SCHEMA_NAME = "context-capsule"
_CAPSULE_ID_PREFIX = "cap-"
_CAPSULE_ID_HEX_LENGTH = 24
_HEX_DIGITS = frozenset("0123456789abcdef")
_AUTHORSHIP_AI_ASSISTED = "ai_assisted"


@dataclass(frozen=True)
class ContextCapsule:
    """Deterministic inspectable context for one document block (blueprint 9.6).

    Generated for inspection and testing only; NO model client exists and
    this module must not add one.
    """

    schema_version: int
    capsule_id: str  # "cap-" + sha256(dumps_stable(payload without capsule_id))[:24]
    project_id: str
    document_id: str
    revision_id: str
    block_id: str  # node id from the canonical document
    current_block_text: str
    adjacent_block_texts: tuple[str, ...]  # window each side, <= 2*window total, in order
    section_goal: str  # nearest preceding heading text or ""
    document_purpose: str  # first paragraph text or "" (documented heuristic)
    required_claims: tuple[ClaimV2, ...]
    protected_spans: tuple[ProtectedSpan, ...]
    citations: tuple[Citation, ...]
    entity_state: tuple[Entity, ...]
    open_loops: tuple[str, ...]  # canonical propositions of PROPOSED claims
    style_hard_invariants: tuple[StyleInvariant, ...]
    style_soft_tendencies: tuple[StyleTendency, ...]
    approved_exemplars: tuple[StyleExemplar, ...]
    prohibited_changes: tuple[str, ...]  # from PROHIBITED_PHRASES invariants, "|"-parsed
    untrusted_source_labels: tuple[str, ...]  # "ai_assisted:{node_id}" + "excluded_span:{span_id}"


def build_context_capsule(
    *,
    document: CanonicalDocument,
    revision: DocumentRevision,
    block_id: str,
    project_state: ProjectState,
    claims: tuple[ClaimV2, ...],
    protected_spans: tuple[ProtectedSpan, ...],
    citations: tuple[Citation, ...],
    entities: tuple[Entity, ...],
    profile: StyleEvidenceProfile | None,
    policy: ContextPolicy,
) -> ContextCapsule:
    """Deterministic assembly of one context capsule.

    Raises:
        DomainError: For an empty document, an unknown ``block_id``, or an
            invalid policy.
    """
    if not document.nodes:
        raise DomainError("Cannot build a context capsule for an empty document")
    try:
        block = document.node_by_id(block_id)
    except KeyError as exc:
        raise DomainError(f"Unknown block node id: {block_id}") from exc
    validate_policy(policy)
    positions = {node.node_id: index for index, node in enumerate(document.nodes)}
    provisional = ContextCapsule(
        schema_version=CONTEXT_CAPSULE_SCHEMA_VERSION,
        capsule_id="",
        project_id=project_state.project_id,
        document_id=revision.document_id,
        revision_id=revision.revision_id,
        block_id=block_id,
        current_block_text=block.text,
        adjacent_block_texts=_adjacent_block_texts(
            document.nodes, positions, block, policy.block_window
        ),
        section_goal=_nearest_heading_text(document.nodes, positions, block),
        document_purpose=_first_paragraph_text(document.nodes),
        required_claims=claims[: policy.max_claims],
        protected_spans=protected_spans[: policy.max_protected_spans],
        citations=citations,
        entity_state=entities[: policy.max_entities],
        open_loops=tuple(
            claim.canonical_proposition for claim in claims if claim.status is ClaimStatus.PROPOSED
        ),
        style_hard_invariants=profile.hard_invariants[: policy.max_invariants] if profile else (),
        style_soft_tendencies=profile.soft_tendencies[: policy.max_tendencies] if profile else (),
        approved_exemplars=(),  # no exemplar source in this signature; see module docstring
        prohibited_changes=_prohibited_changes(profile) if profile else (),
        untrusted_source_labels=(
            _untrusted_labels(document.nodes, protected_spans)
            if policy.include_untrusted_labels
            else ()
        ),
    )
    return replace(provisional, capsule_id=_derive_capsule_id(provisional))


def _is_text_bearing(node: DocumentNode) -> bool:
    """Text-bearing nodes are PARAGRAPH/HEADING nodes with exact text."""
    return node.node_type in (NodeType.PARAGRAPH, NodeType.HEADING) and bool(node.text)


def _adjacent_block_texts(
    nodes: tuple[DocumentNode, ...],
    positions: dict[str, int],
    block: DocumentNode,
    window: int,
) -> tuple[str, ...]:
    """Exact texts of the nearest ``window`` text-bearing nodes each side.

    The block itself is excluded; preceding blocks come first in document
    order, then following blocks, so the tuple reads in document order.
    """
    text_bearing = [
        node for node in nodes if node.node_id != block.node_id and _is_text_bearing(node)
    ]
    block_pos = positions[block.node_id]
    preceding = [node for node in text_bearing if positions[node.node_id] < block_pos][-window:]
    following = [node for node in text_bearing if positions[node.node_id] > block_pos][:window]
    return tuple(node.text for node in preceding + following)


def _nearest_heading_text(
    nodes: tuple[DocumentNode, ...],
    positions: dict[str, int],
    block: DocumentNode,
) -> str:
    """Exact text of the nearest HEADING node before the block, or ""."""
    block_pos = positions[block.node_id]
    heading: DocumentNode | None = None
    for node in nodes:
        if positions[node.node_id] < block_pos and node.node_type is NodeType.HEADING:
            heading = node
    return heading.text if heading is not None else ""


def _first_paragraph_text(nodes: tuple[DocumentNode, ...]) -> str:
    """Exact text of the first PARAGRAPH node, or "" (documented heuristic)."""
    for node in nodes:
        if node.node_type is NodeType.PARAGRAPH:
            return node.text
    return ""


def _prohibited_changes(profile: StyleEvidenceProfile) -> tuple[str, ...]:
    """Parse PROHIBITED_PHRASES invariant values on "|", deduplicated."""
    values: list[str] = []
    for invariant in profile.hard_invariants:
        if invariant.kind is not InvariantKind.PROHIBITED_PHRASES:
            continue
        for part in invariant.value.split("|"):
            stripped = part.strip()
            if stripped and stripped not in values:
                values.append(stripped)
    return tuple(values)


def _untrusted_labels(
    nodes: tuple[DocumentNode, ...],
    spans: tuple[ProtectedSpan, ...],
) -> tuple[str, ...]:
    """Documented untrusted labels: ai_assisted nodes then excluded spans."""
    labels: list[str] = [
        f"ai_assisted:{node.node_id}"
        for node in nodes
        if node.authorship_class == _AUTHORSHIP_AI_ASSISTED
    ]
    labels.extend(
        f"excluded_span:{span.span_id}" for span in spans if span.status is SpanStatus.EXCLUDED
    )
    return tuple(labels)


def capsule_to_payload(capsule: ContextCapsule) -> dict[str, object]:
    """Render the capsule as a stable, lossless JSON-ready payload."""
    return {
        "schema": _SCHEMA_NAME,
        "schema_version": capsule.schema_version,
        "capsule_id": capsule.capsule_id,
        "project_id": capsule.project_id,
        "document_id": capsule.document_id,
        "revision_id": capsule.revision_id,
        "block_id": capsule.block_id,
        "current_block_text": capsule.current_block_text,
        "adjacent_block_texts": list(capsule.adjacent_block_texts),
        "section_goal": capsule.section_goal,
        "document_purpose": capsule.document_purpose,
        "required_claims": [_render_value(claim) for claim in capsule.required_claims],
        "protected_spans": [_render_value(span) for span in capsule.protected_spans],
        "citations": [_render_value(citation) for citation in capsule.citations],
        "entity_state": [_render_value(entity) for entity in capsule.entity_state],
        "open_loops": list(capsule.open_loops),
        "style_hard_invariants": [
            _render_value(invariant) for invariant in capsule.style_hard_invariants
        ],
        "style_soft_tendencies": [
            _render_value(tendency) for tendency in capsule.style_soft_tendencies
        ],
        "approved_exemplars": [_render_value(exemplar) for exemplar in capsule.approved_exemplars],
        "prohibited_changes": list(capsule.prohibited_changes),
        "untrusted_source_labels": list(capsule.untrusted_source_labels),
    }


def capsule_to_json(capsule: ContextCapsule) -> str:
    """Serialize the capsule deterministically with one trailing newline."""
    return dumps_stable(capsule_to_payload(capsule))


def _payload_without_id(payload: dict[str, object]) -> dict[str, object]:
    """The capsule payload with the capsule_id anchor removed."""
    without_id = dict(payload)
    without_id.pop("capsule_id", None)
    return without_id


def _derive_capsule_id(capsule: ContextCapsule) -> str:
    """Deterministic capsule id: sha256 of the stable payload-without-id."""
    digest = hashlib.sha256(
        dumps_stable(_payload_without_id(capsule_to_payload(capsule))).encode("utf-8")
    )
    return f"{_CAPSULE_ID_PREFIX}{digest.hexdigest()[:_CAPSULE_ID_HEX_LENGTH]}"


def capsule_from_json(text: str) -> ContextCapsule:
    """Load a capsule from its stable JSON, verifying the integrity anchor.

    The ``capsule_id`` is re-derived from the payload (without the id) and
    must match the stored id exactly; any mismatch fails closed.

    Raises:
        DomainError: If the payload is not valid capsule JSON, any field
            is malformed, or the capsule id does not match the payload
            digest.
    """
    try:
        payload = json.loads(text)
    except json.JSONDecodeError as exc:
        raise DomainError("Invalid context capsule JSON: not valid JSON") from exc
    if not isinstance(payload, dict):
        raise DomainError("Invalid context capsule JSON: top level must be an object")
    if payload.get("schema") != _SCHEMA_NAME:
        raise DomainError("Invalid context capsule JSON: schema must be 'context-capsule'")
    if payload.get("schema_version") != CONTEXT_CAPSULE_SCHEMA_VERSION:
        raise DomainError("Unsupported context capsule schema version")
    capsule_id = _expect_str(payload, "capsule_id")
    _expect_capsule_id_format(capsule_id)
    derived = _derive_capsule_id_from_payload(payload)
    if derived != capsule_id:
        raise DomainError(
            "Invalid context capsule JSON: capsule_id does not match the payload digest"
        )
    string_list_keys = (
        "adjacent_block_texts",
        "open_loops",
        "prohibited_changes",
        "untrusted_source_labels",
    )
    record_keys = {
        "required_claims": ClaimV2,
        "protected_spans": ProtectedSpan,
        "citations": Citation,
        "entity_state": Entity,
        "style_hard_invariants": StyleInvariant,
        "style_soft_tendencies": StyleTendency,
        "approved_exemplars": StyleExemplar,
    }
    rebuilt_string_lists: dict[str, tuple[str, ...]] = {}
    for key in string_list_keys:
        rebuilt_string_lists[key] = _expect_string_list(payload, key)
    rebuilt_records: dict[str, tuple[Any, ...]] = {}
    for key, record_type in record_keys.items():
        rebuilt_records[key] = _expect_record_list(payload, key, record_type)
    return ContextCapsule(
        schema_version=CONTEXT_CAPSULE_SCHEMA_VERSION,
        capsule_id=capsule_id,
        project_id=_expect_str(payload, "project_id"),
        document_id=_expect_str(payload, "document_id"),
        revision_id=_expect_str(payload, "revision_id"),
        block_id=_expect_str(payload, "block_id"),
        current_block_text=_expect_str(payload, "current_block_text"),
        adjacent_block_texts=rebuilt_string_lists["adjacent_block_texts"],
        section_goal=_expect_str(payload, "section_goal"),
        document_purpose=_expect_str(payload, "document_purpose"),
        required_claims=rebuilt_records["required_claims"],
        protected_spans=rebuilt_records["protected_spans"],
        citations=rebuilt_records["citations"],
        entity_state=rebuilt_records["entity_state"],
        open_loops=rebuilt_string_lists["open_loops"],
        style_hard_invariants=rebuilt_records["style_hard_invariants"],
        style_soft_tendencies=rebuilt_records["style_soft_tendencies"],
        approved_exemplars=rebuilt_records["approved_exemplars"],
        prohibited_changes=rebuilt_string_lists["prohibited_changes"],
        untrusted_source_labels=rebuilt_string_lists["untrusted_source_labels"],
    )


def _derive_capsule_id_from_payload(payload: dict[str, object]) -> str:
    """Re-derive the capsule id from a parsed payload (order-independent)."""
    digest = hashlib.sha256(dumps_stable(_payload_without_id(payload)).encode("utf-8"))
    return f"{_CAPSULE_ID_PREFIX}{digest.hexdigest()[:_CAPSULE_ID_HEX_LENGTH]}"


def _expect_capsule_id_format(capsule_id: str) -> None:
    """Require the capsule id to be "cap-" plus 24 lowercase hex chars."""
    suffix = capsule_id[len(_CAPSULE_ID_PREFIX) :]
    if not capsule_id.startswith(_CAPSULE_ID_PREFIX) or len(suffix) != _CAPSULE_ID_HEX_LENGTH:
        raise DomainError(
            "Invalid context capsule JSON: capsule_id must be 'cap-' plus 24 hex chars"
        )
    if any(char not in _HEX_DIGITS for char in suffix):
        raise DomainError("Invalid context capsule JSON: capsule_id suffix must be hex")


def _expect_str(payload: dict[str, object], key: str) -> str:
    value = payload.get(key)
    if not isinstance(value, str):
        raise DomainError(f"Invalid context capsule JSON: {key} must be a string")
    return value


def _expect_string_list(payload: dict[str, object], key: str) -> tuple[str, ...]:
    raw = payload.get(key)
    if not isinstance(raw, list) or not all(isinstance(item, str) for item in raw):
        raise DomainError(f"Invalid context capsule JSON: {key} must be a list of strings")
    return tuple(raw)


def _expect_record_list(
    payload: dict[str, object],
    key: str,
    record_type: type[Any],
) -> tuple[Any, ...]:
    raw = payload.get(key)
    if not isinstance(raw, list):
        raise DomainError(f"Invalid context capsule JSON: {key} must be a list")
    return tuple(_rebuild_value(record_type, item) for item in raw)


def _render_value(value: Any) -> Any:
    """Render one capsule value as JSON-ready data (deterministic)."""
    if value is None:
        return None
    if isinstance(value, bool):
        return value
    if isinstance(value, int):
        return value
    if isinstance(value, float):
        return value
    if isinstance(value, StrEnum):
        return value.value
    if isinstance(value, str):
        return value
    if isinstance(value, dict):
        return {key: _render_value(item) for key, item in value.items()}
    if isinstance(value, tuple):
        return [_render_value(item) for item in value]
    if isinstance(value, list):
        return [_render_value(item) for item in value]
    if dataclasses.is_dataclass(value):
        return {
            field.name: _render_value(getattr(value, field.name))
            for field in dataclasses.fields(value)
        }
    raise DomainError(f"Cannot render context capsule field: {type(value).__name__}")


def _rebuild_value(expected: Any, raw: Any) -> Any:
    """Rebuild one capsule field from JSON data, validating strictly.

    ``expected`` is the annotated type of the field (a class or a typing
    construct such as ``tuple[str, ...]`` or ``float | None``). ``raw`` is
    the JSON-decoded value. Mismatches raise :class:`DomainError`; nothing
    is coerced silently.
    """
    origin = typing.get_origin(expected)
    if origin is typing.Union or origin is types.UnionType:
        args = typing.get_args(expected)
        if raw is None:
            if any(arg is types.NoneType for arg in args):
                return None
            raise DomainError("Invalid context capsule JSON: null value")
        non_none = [arg for arg in args if arg is not types.NoneType]
        if len(non_none) == 1:
            return _rebuild_value(non_none[0], raw)
        raise DomainError("Invalid context capsule JSON: ambiguous union field")
    if raw is None:
        raise DomainError("Invalid context capsule JSON: null value")
    if origin is tuple:
        if not isinstance(raw, list):
            raise DomainError("Invalid context capsule JSON: expected a list")
        args = typing.get_args(expected)
        item_type = args[0] if args else Any
        return tuple(_rebuild_value(item_type, item) for item in raw)
    if origin is dict:
        if not isinstance(raw, dict):
            raise DomainError("Invalid context capsule JSON: expected an object")
        args = typing.get_args(expected)
        value_type = args[1] if len(args) > 1 else Any
        return {key: _rebuild_value(value_type, item) for key, item in raw.items()}
    if isinstance(expected, type) and dataclasses.is_dataclass(expected):
        return _rebuild_dataclass(expected, raw)
    if isinstance(expected, type) and issubclass(expected, StrEnum):
        try:
            return expected(raw)
        except ValueError as exc:
            raise DomainError(
                f"Invalid context capsule JSON: {expected.__name__} must be a known value"
            ) from exc
    if isinstance(expected, type) and issubclass(expected, bool):
        if not isinstance(raw, bool):
            raise DomainError("Invalid context capsule JSON: expected a boolean")
        return raw
    if isinstance(expected, type) and issubclass(expected, int):
        if not isinstance(raw, int) or isinstance(raw, bool):
            raise DomainError("Invalid context capsule JSON: expected an integer")
        return raw
    if isinstance(expected, type) and issubclass(expected, float):
        if not isinstance(raw, (int, float)) or isinstance(raw, bool):
            raise DomainError("Invalid context capsule JSON: expected a number")
        return float(raw)
    if isinstance(expected, type) and issubclass(expected, str):
        if not isinstance(raw, str):
            raise DomainError("Invalid context capsule JSON: expected a string")
        return raw
    raise DomainError(f"Invalid context capsule JSON: unsupported field type {expected!r}")


def _rebuild_dataclass(cls: type[Any], raw: Any) -> Any:
    """Rebuild a frozen dataclass value from a JSON object."""
    if not isinstance(raw, dict):
        raise DomainError(f"Invalid context capsule JSON: {cls.__name__} must be an object")
    hints = typing.get_type_hints(cls)
    known = {field.name for field in dataclasses.fields(cls)}
    unknown = set(raw) - known
    if unknown:
        raise DomainError(
            f"Invalid context capsule JSON: unknown {cls.__name__} fields "
            f"{', '.join(sorted(unknown))}"
        )
    values: dict[str, Any] = {}
    for field in dataclasses.fields(cls):
        if field.name not in raw:
            raise DomainError(f"Invalid context capsule JSON: missing {cls.__name__}.{field.name}")
        values[field.name] = _rebuild_value(hints[field.name], raw[field.name])
    return cls(**values)


def validate_capsule(capsule: ContextCapsule, policy: ContextPolicy) -> tuple[str, ...]:
    """Report policy violations for a capsule (empty tuple means valid)."""
    violations: list[str] = []
    if capsule.schema_version != CONTEXT_CAPSULE_SCHEMA_VERSION:
        violations.append(
            f"schema_version mismatch: expected {CONTEXT_CAPSULE_SCHEMA_VERSION}, "
            f"got {capsule.schema_version}"
        )
    adjacent_limit = policy.block_window * 2
    if len(capsule.adjacent_block_texts) > adjacent_limit:
        violations.append(
            f"adjacent_block_texts exceeds block_window*2 "
            f"({len(capsule.adjacent_block_texts)} > {adjacent_limit})"
        )
    if len(capsule.protected_spans) > policy.max_protected_spans:
        violations.append(
            f"protected_spans exceeds max_protected_spans "
            f"({len(capsule.protected_spans)} > {policy.max_protected_spans})"
        )
    if len(capsule.required_claims) > policy.max_claims:
        violations.append(
            f"required_claims exceeds max_claims "
            f"({len(capsule.required_claims)} > {policy.max_claims})"
        )
    if len(capsule.entity_state) > policy.max_entities:
        violations.append(
            f"entity_state exceeds max_entities "
            f"({len(capsule.entity_state)} > {policy.max_entities})"
        )
    if len(capsule.approved_exemplars) > policy.max_exemplars:
        violations.append(
            f"approved_exemplars exceeds max_exemplars "
            f"({len(capsule.approved_exemplars)} > {policy.max_exemplars})"
        )
    if len(capsule.style_hard_invariants) > policy.max_invariants:
        violations.append(
            f"style_hard_invariants exceeds max_invariants "
            f"({len(capsule.style_hard_invariants)} > {policy.max_invariants})"
        )
    if len(capsule.style_soft_tendencies) > policy.max_tendencies:
        violations.append(
            f"style_soft_tendencies exceeds max_tendencies "
            f"({len(capsule.style_soft_tendencies)} > {policy.max_tendencies})"
        )
    return tuple(violations)
