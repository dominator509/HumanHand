"""Lexical rule and ruleset data model — versioned, deterministic, local.

SPEC-014 / ADR-007: rulesets are versioned and immutable, precedence is
explicit, and resources are bundled with the package (resolved relative to
the infra loader) — never fetched over the network.
"""

from __future__ import annotations

import hashlib
from dataclasses import dataclass
from enum import StrEnum

from humanhand.domain.document_serialization import dumps_stable
from humanhand.domain.types import DomainError

_LEXICON_SCHEMA = "lexicon"
_LEXICON_SCHEMA_VERSION = 1
_CURATED_PROVENANCE = "curated-in-repo"

_RULE_FIELDS = (
    "rule_id",
    "source_token",
    "target_token",
    "sense",
    "precedence",
    "confidence",
    "provenance",
)


class LexicalPrecedence(StrEnum):
    """Precedence of a lexical source, strongest first (SPEC-014)."""

    PROTECTED_SPAN = "protected_span"
    USER_PREFERENCE = "user_preference"
    PROJECT_GLOSSARY = "project_glossary"
    REGISTER_EVIDENCE = "register_evidence"
    DOMAIN_GLOSSARY = "domain_glossary"
    CURATED_RULE = "curated_rule"
    LICENSED_RESOURCE = "licensed_resource"
    NO_CHANGE = "no_change"


# Strongest first; mirrors SPEC-014 invariants and blueprint section 12.3.
PRECEDENCE_ORDER: tuple[LexicalPrecedence, ...] = (
    LexicalPrecedence.PROTECTED_SPAN,
    LexicalPrecedence.USER_PREFERENCE,
    LexicalPrecedence.PROJECT_GLOSSARY,
    LexicalPrecedence.REGISTER_EVIDENCE,
    LexicalPrecedence.DOMAIN_GLOSSARY,
    LexicalPrecedence.CURATED_RULE,
    LexicalPrecedence.LICENSED_RESOURCE,
    LexicalPrecedence.NO_CHANGE,
)


class SenseStatus(StrEnum):
    """Deterministic sense resolution outcome for one token occurrence."""

    SUPPORTED = "supported"
    AMBIGUOUS = "ambiguous"
    UNSUPPORTED = "unsupported"


@dataclass(frozen=True)
class LexicalRule:
    """One deterministic source-to-target lexical preference.

    ``source_token`` is the lowercase lemma that occurrences are matched
    against; ``confidence`` is the documented author judgment in [0, 1].
    """

    rule_id: str
    source_token: str
    target_token: str
    sense: str
    precedence: LexicalPrecedence
    confidence: float
    provenance: str

    def __post_init__(self) -> None:
        if not 0.0 <= self.confidence <= 1.0:
            raise DomainError(f"Rule {self.rule_id} confidence must be in [0, 1]")


@dataclass(frozen=True)
class RulesetVersion:
    """An immutable, versioned collection of lexical rules."""

    version: str
    rules: tuple[LexicalRule, ...]

    def hash(self) -> str:
        """sha256 hex digest of the deterministic ruleset payload."""
        return hashlib.sha256(dumps_stable(ruleset_to_payload(self)).encode("utf-8")).hexdigest()


def ruleset_from_resource(payload: dict[str, object]) -> RulesetVersion:
    """Validate a loaded curated English rules resource."""
    file_name = "core-en-rules.json"
    _validate_resource_metadata(payload, file_name)
    version = _expect_string(payload, "version", file_name)
    if not version:
        raise DomainError(f"{file_name}: version must be non-empty")
    raw_rules = payload.get("rules")
    if not isinstance(raw_rules, list):
        raise DomainError(f"{file_name}: rules must be a list")
    rules: list[LexicalRule] = []
    seen_ids: set[str] = set()
    for index, raw in enumerate(raw_rules):
        what = f"{file_name}: rules[{index}]"
        if not isinstance(raw, dict):
            raise DomainError(f"{what} must be an object")
        rule_id = _expect_string(raw, "rule_id", what)
        if rule_id in seen_ids:
            raise DomainError(f"{what}: duplicate rule_id {rule_id!r}")
        seen_ids.add(rule_id)
        source_token = _expect_string(raw, "source_token", what)
        target_token = _expect_string(raw, "target_token", what)
        sense = _expect_string(raw, "sense", what)
        if not (rule_id and source_token and target_token and sense):
            raise DomainError(f"{what}: rule_id, tokens, and sense must be non-empty")
        confidence = _expect_number(raw, "confidence", what)
        rules.append(
            LexicalRule(
                rule_id=rule_id,
                source_token=source_token.lower(),
                target_token=target_token.lower(),
                sense=sense,
                precedence=LexicalPrecedence.CURATED_RULE,
                confidence=confidence,
                provenance=_CURATED_PROVENANCE,
            )
        )
    return RulesetVersion(version=version, rules=tuple(rules))


def protected_terms_from_resource(payload: dict[str, object]) -> frozenset[str]:
    """Validate a loaded protected-term resource."""
    domain = _expect_string(payload, "domain", "protected-terms resource")
    if domain not in {"general", "medical", "legal"}:
        raise DomainError(
            f"Unknown protected-term domain {domain!r}; expected general, medical, or legal"
        )
    file_name = f"protected-{domain}-terms.json"
    _validate_resource_metadata(payload, file_name)
    declared_domain = _expect_string(payload, "domain", file_name)
    if declared_domain != domain:
        raise DomainError(f"{file_name}: domain must match {domain!r}")
    raw_terms = payload.get("terms")
    if not isinstance(raw_terms, list):
        raise DomainError(f"{file_name}: terms must be a list")
    terms: list[str] = []
    for index, raw in enumerate(raw_terms):
        if not isinstance(raw, str) or not raw:
            raise DomainError(f"{file_name}: terms[{index}] must be a non-empty string")
        terms.append(raw)
    return frozenset(terms)


def ruleset_to_payload(ruleset: RulesetVersion) -> dict[str, object]:
    """Render a ruleset as a deterministic JSON-ready mapping."""
    return {
        "schema": _LEXICON_SCHEMA,
        "schema_version": _LEXICON_SCHEMA_VERSION,
        "version": ruleset.version,
        "rules": [
            {
                "rule_id": rule.rule_id,
                "source_token": rule.source_token,
                "target_token": rule.target_token,
                "sense": rule.sense,
                "precedence": rule.precedence.value,
                "confidence": rule.confidence,
                "provenance": rule.provenance,
            }
            for rule in ruleset.rules
        ],
    }


def ruleset_from_payload(payload: dict[str, object]) -> RulesetVersion:
    """Strictly validate and rebuild a ruleset from its payload.

    Raises :class:`DomainError` on any unknown or missing key, wrong type,
    unknown enum value, or out-of-range confidence.
    """
    _expect_keys(payload, ("schema", "schema_version", "version", "rules"), "ruleset")
    if _expect_string(payload, "schema", "ruleset") != _LEXICON_SCHEMA:
        raise DomainError("ruleset: schema must be 'lexicon'")
    if payload.get("schema_version") != _LEXICON_SCHEMA_VERSION:
        raise DomainError("ruleset: unsupported schema_version")
    version = _expect_string(payload, "version", "ruleset")
    if not version:
        raise DomainError("ruleset: version must be non-empty")
    raw_rules = payload.get("rules")
    if not isinstance(raw_rules, list):
        raise DomainError("ruleset: rules must be a list")
    rules: list[LexicalRule] = []
    for index, raw in enumerate(raw_rules):
        what = f"ruleset: rules[{index}]"
        if not isinstance(raw, dict):
            raise DomainError(f"{what} must be an object")
        _expect_keys(raw, _RULE_FIELDS, what)
        try:
            precedence = LexicalPrecedence(_expect_string(raw, "precedence", what))
        except ValueError as exc:
            raise DomainError(f"{what}: unknown precedence") from exc
        rule_id = _expect_string(raw, "rule_id", what)
        source_token = _expect_string(raw, "source_token", what)
        target_token = _expect_string(raw, "target_token", what)
        sense = _expect_string(raw, "sense", what)
        provenance = _expect_string(raw, "provenance", what)
        if not (rule_id and source_token and target_token and sense and provenance):
            raise DomainError(f"{what}: rule fields must be non-empty")
        rules.append(
            LexicalRule(
                rule_id=rule_id,
                source_token=source_token,
                target_token=target_token,
                sense=sense,
                precedence=precedence,
                confidence=_expect_number(raw, "confidence", what),
                provenance=provenance,
            )
        )
    return RulesetVersion(version=version, rules=tuple(rules))


def _validate_resource_metadata(payload: dict[str, object], file_name: str) -> None:
    if _expect_string(payload, "schema", file_name) != _LEXICON_SCHEMA:
        raise DomainError(f"{file_name}: schema must be 'lexicon'")
    if payload.get("schema_version") != _LEXICON_SCHEMA_VERSION:
        raise DomainError(f"{file_name}: unsupported schema_version")
    if _expect_string(payload, "provenance", file_name) != _CURATED_PROVENANCE:
        raise DomainError(f"{file_name}: provenance must be 'curated-in-repo'")
    license_note = _expect_string(payload, "license", file_name)
    if not license_note:
        raise DomainError(f"{file_name}: license note must be non-empty")


def _expect_string(payload: dict[str, object], key: str, what: str) -> str:
    value = payload.get(key)
    if not isinstance(value, str):
        raise DomainError(f"{what}: {key} must be a string")
    return value


def _expect_number(payload: dict[str, object], key: str, what: str) -> float:
    value = payload.get(key)
    if not isinstance(value, (int, float)) or isinstance(value, bool):
        raise DomainError(f"{what}: {key} must be a number")
    return float(value)


def _expect_keys(payload: dict[str, object], expected: tuple[str, ...], what: str) -> None:
    for key in payload:
        if key not in expected:
            raise DomainError(f"{what}: unexpected key {key!r}")
    for key in expected:
        if key not in payload:
            raise DomainError(f"{what}: missing key {key!r}")
