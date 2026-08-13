"""Deterministic lexical proposal pipeline (EP-017).

This module turns a ruleset, contexts, and precedence inputs into a
deterministic proposal of lexical changes plus findings. It never
invents changes: only rules from the bundled curated ruleset may
propose a change, and anything ambiguous is a no-op. The pipeline is
NOT a synonym spinner.

Parallel-module contract
------------------------
- ``humanhand.domain.lexical_types``: ``LexicalRule`` (fields
  ``rule_id``, ``source_token``, ``target_token``, ``sense``,
  ``precedence``, ``confidence``, ``provenance``), ``RulesetVersion``
  (fields ``version``, ``rules``; ``hash()`` returns the sha256 ruleset
  digest), ``LexicalPrecedence`` (StrEnum including ``NO_CHANGE`` and
  ``CURATED_RULE``), ``SenseStatus``, ``PRECEDENCE_ORDER`` (tuple of
  ``LexicalPrecedence``, strongest first), ``load_bundled_rules``,
  ``load_protected_terms``.
- ``humanhand.domain.lexical_context``: ``LexicalContext`` (fields
  ``token``, ``lemma``, ``offset``, ``left_window``, ``right_window``,
  ``protected_span_ids``, ``part_of_speech``), ``build_contexts``,
  ``context_in_protected_span``, ``resolve_precedence`` (keyword-only
  ``in_protected_span``, ``rule``, ``user_preference``,
  ``project_glossary``, ``register_rule``, ``domain_glossary``;
  returns ``LexicalPrecedence``).
- ``humanhand.domain.lexical_rules``: ``select_rule_for_lemma``
  (deterministic strongest-match rule selection), ``token_to_lemma``,
  ``rule_applies``, ``estimate_part_of_speech``.

Precedence semantics
--------------------
Ranks come from ``PRECEDENCE_ORDER`` (strongest first). A change is
``SAFE`` only when the winning rule's confidence is at least
``safe_threshold`` AND the effective precedence rank is at most the
rank of ``CURATED_RULE`` (stronger-or-equal); otherwise ``PROPOSED``.
A precedence value absent from ``PRECEDENCE_ORDER`` ranks below
everything (documented fallback).

Findings (format ``{code}:{token}``, one per declined context, first
reason wins)
------------
- ``protected_skip``: the context overlaps a protected span, either
  through the explicit ``protected_spans`` argument or the context's
  own ``protected_span_ids``.
- ``precedence_no_change``: precedence resolution returned NO_CHANGE.
- ``inflection_unsupported``: the inflection cannot be preserved.
- ``collocation_unsafe``: the inflected target fails the conservative
  collocation check.

Tokens whose lowercase lemma does not match any rule's ``source_token``
are skipped silently: no change, no finding.

Run ids and payloads
--------------------
A proposal's ``run_id`` (and ``proposal_id``, equal by contract) is
``"run-"`` plus the first 24 hex characters of the sha256 digest of
the canonical payload WITHOUT the ``run_id``/``proposal_id`` keys
(``dumps_stable``, see ``compute_run_id``). Payload schema name is
``"lexical-proposal"`` with ``LEXICAL_PROPOSAL_SCHEMA_VERSION == 1``;
parsing is strict and rejects tampered payloads with ``DomainError``.

Collocation windows
-------------------
Neighbor windows come from the contexts built by ``build_contexts``
(up to three surface tokens per side; the left window is lowercased,
the right window keeps original casing). Callers may supply explicit
``left_window``/``right_window`` strings to override them.
"""

from __future__ import annotations

import hashlib
import re
import string
from collections.abc import Mapping
from dataclasses import dataclass
from enum import StrEnum

from humanhand.domain.collocations import collocation_preserved
from humanhand.domain.document_serialization import dumps_stable
from humanhand.domain.inflection import inflect_target
from humanhand.domain.lexical_context import (
    LexicalContext,
    context_in_protected_span,
    resolve_precedence,
)
from humanhand.domain.lexical_rules import select_rule_for_lemma
from humanhand.domain.lexical_types import (
    PRECEDENCE_ORDER,
    LexicalPrecedence,
    LexicalRule,
    RulesetVersion,
)
from humanhand.domain.protected_spans import ProtectedSpan, ProtectedSpanSet
from humanhand.domain.types import DomainError

LEXICAL_PROPOSAL_SCHEMA_VERSION = 1
_PROPOSAL_SCHEMA_NAME = "lexical-proposal"
_RUN_ID_PREFIX = "run-"
_RUN_ID_HEX_LENGTH = 24

_FINDING_PROTECTED = "protected_skip"
_FINDING_PRECEDENCE = "precedence_no_change"
_FINDING_INFLECTION = "inflection_unsupported"
_FINDING_COLLOCATION = "collocation_unsafe"
_FINDING_AMBIGUOUS = "ambiguous_sense"

# Strongest-first rank of the curated-rule precedence level; any rule
# with a rank at or below this level is strong enough to be SAFE.
_CURATED_RULE_RANK: int = PRECEDENCE_ORDER.index(LexicalPrecedence.CURATED_RULE)


class ChangeStatus(StrEnum):
    """Review state of one proposed lexical change."""

    SAFE = "SAFE"
    PROPOSED = "PROPOSED"


@dataclass(frozen=True)
class LexicalChange:
    """One proposed lexical replacement with its provenance."""

    change_id: str
    offset: int
    length: int
    source_surface: str
    target: str
    reason: str
    precedence: str
    confidence: float
    status: ChangeStatus
    rule_id: str
    sense: str
    ruleset_hash: str


@dataclass(frozen=True)
class LexicalProposal:
    """Deterministic proposal of lexical changes plus findings."""

    proposal_id: str
    run_id: str
    ruleset_hash: str
    document_hash: str
    schema_version: int
    changes: tuple[LexicalChange, ...]
    findings: tuple[str, ...]


def compute_run_id(payload_without_run_id: dict[str, object]) -> str:
    """Deterministic run id over a payload without the run_id keys."""
    digest = hashlib.sha256(dumps_stable(payload_without_run_id).encode("utf-8")).hexdigest()
    return f"{_RUN_ID_PREFIX}{digest[:_RUN_ID_HEX_LENGTH]}"


def _precedence_rank(precedence: LexicalPrecedence) -> int:
    """Strongest-first rank; values outside the order rank below all."""
    try:
        return PRECEDENCE_ORDER.index(precedence)
    except ValueError:
        return len(PRECEDENCE_ORDER)


def _user_preference_rule(lemma: str, preferences: Mapping[str, str]) -> LexicalRule | None:
    """A real user-preference rule for ``lemma``, or None when unset.

    The mapping is explicit user input: when it names ``lemma``, the
    preference target becomes a real rule with USER_PREFERENCE
    precedence and full confidence, never an invented token.
    """
    target = preferences.get(lemma)
    if target is None:
        return None
    return LexicalRule(
        rule_id="user-preference",
        source_token=lemma,
        target_token=target,
        sense="",
        precedence=LexicalPrecedence.USER_PREFERENCE,
        confidence=1.0,
        provenance="user-preference",
    )


def _winning_rule(
    precedence: LexicalPrecedence,
    user_preference: LexicalRule | None,
    project_glossary: LexicalRule | None,
    register_rule: LexicalRule | None,
    domain_glossary: LexicalRule | None,
    base_rule: LexicalRule | None,
) -> LexicalRule:
    """The rule behind the resolved precedence; the base rule always wins."""
    if precedence is LexicalPrecedence.USER_PREFERENCE and user_preference is not None:
        return user_preference
    if precedence is LexicalPrecedence.PROJECT_GLOSSARY and project_glossary is not None:
        return project_glossary
    if precedence is LexicalPrecedence.REGISTER_EVIDENCE and register_rule is not None:
        return register_rule
    if precedence is LexicalPrecedence.DOMAIN_GLOSSARY and domain_glossary is not None:
        return domain_glossary
    if base_rule is None:
        raise DomainError("No winning lexical rule for resolved precedence")
    return base_rule


def propose_changes(
    text: str,
    ruleset: RulesetVersion,
    contexts: tuple[LexicalContext, ...],
    *,
    user_preferences: Mapping[str, str],
    project_glossary: tuple[LexicalRule, ...],
    register_rules: tuple[LexicalRule, ...],
    domain_glossary: tuple[LexicalRule, ...],
    safe_threshold: float,
    protected_spans: ProtectedSpanSet | None = None,
    left_window: str = "",
    right_window: str = "",
) -> LexicalProposal:
    """Propose deterministic lexical changes for ``text``.

    Only tokens whose lowercase lemma matches a rule's ``source_token``
    may propose a change; every decline records a finding and leaves the
    token untouched. Contexts must lie inside ``text`` (DomainError
    otherwise). ``safe_threshold`` must be within [0.0, 1.0].
    """
    if safe_threshold < 0.0 or safe_threshold > 1.0:
        raise DomainError(f"safe_threshold must be within [0.0, 1.0], got {safe_threshold}")
    if not ruleset.rules:
        raise DomainError("ruleset must contain at least one rule")
    ruleset_hash = ruleset.hash()
    spans = protected_spans.spans if protected_spans is not None else ()
    all_rule_sets = (ruleset.rules, project_glossary, register_rules, domain_glossary)
    surface_index = frozenset(
        (
            *user_preferences.keys(),
            *(rule.source_token for rules in all_rule_sets for rule in rules),
        )
    )
    candidate_contexts = _contexts_with_multiword_candidates(text, contexts, surface_index, spans)
    changes: list[LexicalChange] = []
    findings: list[str] = []
    for context in candidate_contexts:
        surface = _match_surface(context, surface_index)
        if surface is None:
            continue
        token, lemma, offset = surface
        length = len(token)
        if offset < 0 or length <= 0 or offset + length > len(text):
            raise DomainError(f"Context outside document: offset={offset} length={length}")
        overlaps_span = any(
            offset < span.source_location.end_offset
            and span.source_location.start_offset < offset + length
            for span in spans
        )
        if overlaps_span or context_in_protected_span(context):
            findings.append(f"{_FINDING_PROTECTED}:{token}")
            continue
        rule = select_rule_for_lemma(ruleset.rules, lemma)
        user_preference = _user_preference_rule(lemma, user_preferences)
        project_glossary_rule = select_rule_for_lemma(project_glossary, lemma)
        register_rule = select_rule_for_lemma(register_rules, lemma)
        domain_glossary_rule = select_rule_for_lemma(domain_glossary, lemma)
        precedence = resolve_precedence(
            in_protected_span=False,
            rule=rule,
            user_preference=user_preference,
            project_glossary=project_glossary_rule,
            register_rule=register_rule,
            domain_glossary=domain_glossary_rule,
        )
        if precedence is LexicalPrecedence.NO_CHANGE:
            findings.append(f"{_FINDING_PRECEDENCE}:{token}")
            continue
        matching_at_winner = _matching_rules_at_precedence(
            lemma,
            precedence,
            user_preference,
            project_glossary,
            register_rules,
            domain_glossary,
            ruleset.rules,
        )
        if len({(item.target_token, item.sense) for item in matching_at_winner}) > 1:
            findings.append(f"{_FINDING_AMBIGUOUS}:{token}")
            continue
        winner = _winning_rule(
            precedence,
            user_preference,
            project_glossary_rule,
            register_rule,
            domain_glossary_rule,
            rule,
        )
        inflected = inflect_target(token, lemma, winner.target_token)
        if inflected is None:
            findings.append(f"{_FINDING_INFLECTION}:{token}")
            continue
        if not collocation_preserved(
            text,
            offset,
            length,
            inflected,
            left_window=left_window or context.left_window,
            right_window=right_window or context.right_window,
        ):
            findings.append(f"{_FINDING_COLLOCATION}:{token}")
            continue
        status = (
            ChangeStatus.PROPOSED
            if winner.confidence < safe_threshold
            or _precedence_rank(precedence) > _CURATED_RULE_RANK
            else ChangeStatus.SAFE
        )
        changes.append(
            LexicalChange(
                change_id=f"ch{len(changes) + 1}",
                offset=offset,
                length=length,
                source_surface=token,
                target=inflected,
                reason=f"{winner.rule_id}:{winner.sense}",
                precedence=precedence.value,
                confidence=float(winner.confidence),
                status=status,
                rule_id=winner.rule_id,
                sense=winner.sense,
                ruleset_hash=ruleset_hash,
            )
        )
    document_hash = hashlib.sha256(text.encode("utf-8")).hexdigest()
    run_id = compute_run_id(
        core_proposal_payload(ruleset_hash, document_hash, tuple(changes), tuple(findings))
    )
    return LexicalProposal(
        proposal_id=run_id,
        run_id=run_id,
        ruleset_hash=ruleset_hash,
        document_hash=document_hash,
        schema_version=LEXICAL_PROPOSAL_SCHEMA_VERSION,
        changes=tuple(changes),
        findings=tuple(findings),
    )


def _match_surface(
    context: LexicalContext, source_tokens: frozenset[str]
) -> tuple[str, str, int] | None:
    """Resolve punctuation and supported -ing/-ed forms to a known source token."""
    raw = context.token
    core = raw.strip(string.punctuation)
    if not core:
        return None
    offset = context.offset + raw.find(core)
    lowered = core.lower()
    direct = [source for source in source_tokens if source.lower() == lowered]
    if len(direct) == 1:
        return core, direct[0], offset
    inflected: list[str] = []
    for source in source_tokens:
        if " " in source:
            continue
        source_lower = source.lower()
        ing = (source_lower[:-1] if source_lower.endswith("e") else source_lower) + "ing"
        ed = source_lower + ("d" if source_lower.endswith("e") else "ed")
        if lowered in {ing, ed}:
            inflected.append(source)
    if len(inflected) == 1:
        return core, inflected[0], offset
    return None


def _contexts_with_multiword_candidates(
    text: str,
    contexts: tuple[LexicalContext, ...],
    source_tokens: frozenset[str],
    spans: tuple[ProtectedSpan, ...],
) -> tuple[LexicalContext, ...]:
    """Add longest-first phrase contexts and suppress overlapping token contexts."""
    phrases: list[LexicalContext] = []
    phrase_ranges: list[tuple[int, int]] = []
    for source in sorted(
        (item for item in source_tokens if " " in item), key=lambda x: (-len(x), x)
    ):
        pattern = re.compile(rf"(?<!\w){re.escape(source)}(?!\w)", re.IGNORECASE)
        for match in pattern.finditer(text):
            start, end = match.span()
            if any(
                start < prior_end and prior_start < end for prior_start, prior_end in phrase_ranges
            ):
                continue
            protected_ids = tuple(
                span.span_id
                for span in spans
                if start < span.source_location.end_offset
                and span.source_location.start_offset < end
            )
            phrases.append(
                LexicalContext(
                    token=match.group(0),
                    lemma=source,
                    offset=start,
                    left_window=text[max(0, start - 40) : start],
                    right_window=text[end : end + 40],
                    protected_span_ids=protected_ids,
                    part_of_speech="other",
                )
            )
            phrase_ranges.append((start, end))
    singles = [
        context
        for context in contexts
        if not any(
            context.offset < end and start < context.offset + len(context.token)
            for start, end in phrase_ranges
        )
    ]
    return tuple(sorted((*phrases, *singles), key=lambda item: (item.offset, -len(item.token))))


def _matching_rules_at_precedence(
    lemma: str,
    precedence: LexicalPrecedence,
    user_preference: LexicalRule | None,
    project_glossary: tuple[LexicalRule, ...],
    register_rules: tuple[LexicalRule, ...],
    domain_glossary: tuple[LexicalRule, ...],
    curated_rules: tuple[LexicalRule, ...],
) -> tuple[LexicalRule, ...]:
    if precedence is LexicalPrecedence.USER_PREFERENCE:
        return (user_preference,) if user_preference is not None else ()
    source_for_precedence = {
        LexicalPrecedence.PROJECT_GLOSSARY: project_glossary,
        LexicalPrecedence.REGISTER_EVIDENCE: register_rules,
        LexicalPrecedence.DOMAIN_GLOSSARY: domain_glossary,
    }.get(precedence, curated_rules)
    return tuple(rule for rule in source_for_precedence if rule.source_token == lemma)


def core_proposal_payload(
    ruleset_hash: str,
    document_hash: str,
    changes: tuple[LexicalChange, ...],
    findings: tuple[str, ...],
) -> dict[str, object]:
    """Canonical proposal payload WITHOUT the run_id/proposal_id keys."""
    return {
        "schema": _PROPOSAL_SCHEMA_NAME,
        "schema_version": LEXICAL_PROPOSAL_SCHEMA_VERSION,
        "document_hash": document_hash,
        "ruleset_hash": ruleset_hash,
        "changes": [_change_payload(change) for change in changes],
        "findings": list(findings),
    }


def _change_payload(change: LexicalChange) -> dict[str, object]:
    return {
        "change_id": change.change_id,
        "offset": change.offset,
        "length": change.length,
        "source_surface": change.source_surface,
        "target": change.target,
        "reason": change.reason,
        "precedence": change.precedence,
        "confidence": change.confidence,
        "status": change.status.value,
        "rule_id": change.rule_id,
        "sense": change.sense,
        "ruleset_hash": change.ruleset_hash,
    }


def proposal_to_payload(proposal: LexicalProposal) -> dict[str, object]:
    """Render a proposal as its canonical JSON-ready mapping."""
    payload = core_proposal_payload(
        proposal.ruleset_hash, proposal.document_hash, proposal.changes, proposal.findings
    )
    payload["run_id"] = proposal.run_id
    payload["proposal_id"] = proposal.proposal_id
    return payload


def proposal_from_payload(payload: dict[str, object]) -> LexicalProposal:
    """Strictly parse and validate a lexical proposal payload."""
    if payload.get("schema") != _PROPOSAL_SCHEMA_NAME:
        raise DomainError(
            f"Invalid lexical proposal JSON: schema must be {_PROPOSAL_SCHEMA_NAME!r}"
        )
    schema_version = _expect_int(payload, "schema_version", "schema_version")
    if schema_version != LEXICAL_PROPOSAL_SCHEMA_VERSION:
        raise DomainError(f"Unsupported lexical proposal schema version: {schema_version}")
    run_id = payload.get("run_id")
    proposal_id = payload.get("proposal_id")
    if not isinstance(run_id, str) or not isinstance(proposal_id, str):
        raise DomainError("Invalid lexical proposal JSON: run_id and proposal_id must be strings")
    _validate_run_id(run_id)
    document_hash = _expect_str(payload, "document_hash", "document_hash")
    _validate_sha256_hex(document_hash, "document_hash")
    ruleset_hash = _expect_str(payload, "ruleset_hash", "ruleset_hash")
    if not ruleset_hash:
        raise DomainError("Invalid lexical proposal JSON: ruleset_hash must be non-empty")
    raw_changes = payload.get("changes")
    if not isinstance(raw_changes, list):
        raise DomainError("Invalid lexical proposal JSON: changes must be a list")
    changes = tuple(
        _change_from_payload(item, index, ruleset_hash)
        for index, item in enumerate(raw_changes)
        if isinstance(item, dict)
    )
    if len(changes) != len(raw_changes):
        raise DomainError("Invalid lexical proposal JSON: changes must contain only objects")
    raw_findings = payload.get("findings")
    if not isinstance(raw_findings, list):
        raise DomainError("Invalid lexical proposal JSON: findings must be a list")
    findings = tuple(item for item in raw_findings if isinstance(item, str))
    if len(findings) != len(raw_findings):
        raise DomainError("Invalid lexical proposal JSON: findings must contain only strings")
    for finding in findings:
        if not finding:
            raise DomainError("Invalid lexical proposal JSON: findings must be non-empty")
    expected_run_id = compute_run_id(
        {key: value for key, value in payload.items() if key not in ("run_id", "proposal_id")}
    )
    if run_id != expected_run_id or proposal_id != expected_run_id:
        raise DomainError("Invalid lexical proposal JSON: run_id does not match payload")
    return LexicalProposal(
        proposal_id=proposal_id,
        run_id=run_id,
        ruleset_hash=ruleset_hash,
        document_hash=document_hash,
        schema_version=schema_version,
        changes=changes,
        findings=findings,
    )


def _change_from_payload(item: dict[str, object], index: int, ruleset_hash: str) -> LexicalChange:
    """Strictly parse one change; ids must be sequential ``ch1..chN``."""
    expected_id = f"ch{index + 1}"
    change_id = _expect_str(item, "change_id", f"changes[{index}].change_id")
    if change_id != expected_id:
        raise DomainError(
            f"Invalid lexical proposal JSON: unexpected change_id {change_id!r}, "
            f"expected {expected_id!r}"
        )
    offset = _expect_int(item, "offset", f"changes[{index}].offset")
    if offset < 0:
        raise DomainError(f"Invalid lexical proposal JSON: changes[{index}].offset must be >= 0")
    length = _expect_int(item, "length", f"changes[{index}].length")
    if length <= 0:
        raise DomainError(f"Invalid lexical proposal JSON: changes[{index}].length must be > 0")
    confidence = _expect_float(item, "confidence", f"changes[{index}].confidence")
    if confidence < 0.0 or confidence > 1.0:
        raise DomainError(
            f"Invalid lexical proposal JSON: changes[{index}].confidence must be within [0.0, 1.0]"
        )
    change_ruleset_hash = _expect_str(item, "ruleset_hash", f"changes[{index}].ruleset_hash")
    if change_ruleset_hash != ruleset_hash:
        raise DomainError(
            f"Invalid lexical proposal JSON: changes[{index}].ruleset_hash does not match proposal"
        )
    status_value = _expect_str(item, "status", f"changes[{index}].status")
    try:
        status = ChangeStatus(status_value)
    except ValueError as exc:
        raise DomainError(
            f"Invalid lexical proposal JSON: unknown change status {status_value!r}"
        ) from exc
    precedence_value = _expect_str(item, "precedence", f"changes[{index}].precedence")
    try:
        LexicalPrecedence(precedence_value)
    except ValueError as exc:
        raise DomainError(
            f"Invalid lexical proposal JSON: unknown precedence {precedence_value!r}"
        ) from exc
    source_surface = _expect_str(item, "source_surface", f"changes[{index}].source_surface")
    target = _expect_str(item, "target", f"changes[{index}].target")
    reason = _expect_str(item, "reason", f"changes[{index}].reason")
    rule_id = _expect_str(item, "rule_id", f"changes[{index}].rule_id")
    sense = _expect_str(item, "sense", f"changes[{index}].sense")
    if (
        not source_surface
        or not target
        or not reason
        or not precedence_value
        or not rule_id
        or not sense
    ):
        raise DomainError(
            f"Invalid lexical proposal JSON: changes[{index}] fields must be non-empty"
        )
    return LexicalChange(
        change_id=change_id,
        offset=offset,
        length=length,
        source_surface=source_surface,
        target=target,
        reason=reason,
        precedence=precedence_value,
        confidence=confidence,
        status=status,
        rule_id=rule_id,
        sense=sense,
        ruleset_hash=change_ruleset_hash,
    )


def apply_changes(
    text: str, proposal: LexicalProposal, only_status: ChangeStatus | None = None
) -> str:
    """Apply a proposal's changes to ``text``, back-to-front.

    Changes are applied in descending (offset, length) order so earlier
    offsets stay valid while later spans are replaced. Each change is
    verified against the working text before it is applied (the span
    must still equal ``source_surface``); a mismatch raises DomainError
    and leaves ``text`` untouched. ``only_status`` restricts the applied
    changes; ``None`` (the default) applies every change.
    """
    if proposal.schema_version != LEXICAL_PROPOSAL_SCHEMA_VERSION:
        raise DomainError(f"Unsupported lexical proposal schema version: {proposal.schema_version}")
    current_hash = hashlib.sha256(text.encode("utf-8")).hexdigest()
    if current_hash != proposal.document_hash:
        raise DomainError("Document hash does not match lexical proposal input")
    selected = [
        change for change in proposal.changes if only_status is None or change.status is only_status
    ]
    working = text
    for change in sorted(selected, key=lambda item: (item.offset, item.length), reverse=True):
        if change.offset < 0 or change.length <= 0 or change.offset + change.length > len(working):
            raise DomainError(
                f"Change {change.change_id} outside document at offset {change.offset}"
            )
        if working[change.offset : change.offset + change.length] != change.source_surface:
            raise DomainError(f"Change {change.change_id} text mismatch at offset {change.offset}")
        working = (
            working[: change.offset] + change.target + working[change.offset + change.length :]
        )
    return working


def _expect_str(payload: dict[str, object], key: str, what: str) -> str:
    value = payload.get(key)
    if not isinstance(value, str):
        raise DomainError(f"Invalid lexical proposal JSON: {what} must be a string")
    return value


def _expect_int(payload: dict[str, object], key: str, what: str) -> int:
    value = payload.get(key)
    if not isinstance(value, int) or isinstance(value, bool):
        raise DomainError(f"Invalid lexical proposal JSON: {what} must be an integer")
    return value


def _expect_float(payload: dict[str, object], key: str, what: str) -> float:
    value = payload.get(key)
    if isinstance(value, bool) or not isinstance(value, (int, float)):
        raise DomainError(f"Invalid lexical proposal JSON: {what} must be a number")
    return float(value)


def _validate_run_id(run_id: str) -> None:
    if not run_id.startswith(_RUN_ID_PREFIX) or len(run_id) != (
        len(_RUN_ID_PREFIX) + _RUN_ID_HEX_LENGTH
    ):
        raise DomainError("Invalid lexical proposal JSON: malformed run_id")
    if any(char not in "0123456789abcdef" for char in run_id[len(_RUN_ID_PREFIX) :]):
        raise DomainError("Invalid lexical proposal JSON: run_id must be lowercase hex")


def _validate_sha256_hex(value: str, what: str) -> None:
    if len(value) != 64 or any(char not in "0123456789abcdef" for char in value):
        raise DomainError(f"Invalid lexical proposal JSON: {what} must be 64 lowercase hex chars")
