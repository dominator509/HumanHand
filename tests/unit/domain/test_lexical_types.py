"""Unit tests for the lexical rule data model and bundled resources."""

from __future__ import annotations

import pytest

from humanhand.domain.lexical_types import (
    PRECEDENCE_ORDER,
    LexicalPrecedence,
    LexicalRule,
    RulesetVersion,
    SenseStatus,
    ruleset_from_payload,
    ruleset_to_payload,
)
from humanhand.domain.types import DomainError
from humanhand.infra.lexicons import load_bundled_rules, load_protected_terms


def _rule(
    rule_id: str = "cr-test",
    source: str = "utilize",
    target: str = "use",
) -> LexicalRule:
    return LexicalRule(
        rule_id=rule_id,
        source_token=source,
        target_token=target,
        sense="general",
        precedence=LexicalPrecedence.CURATED_RULE,
        confidence=0.9,
        provenance="curated-in-repo",
    )


class TestPrecedenceOrder:
    def test_matches_spec_014_order(self) -> None:
        assert PRECEDENCE_ORDER == (
            LexicalPrecedence.PROTECTED_SPAN,
            LexicalPrecedence.USER_PREFERENCE,
            LexicalPrecedence.PROJECT_GLOSSARY,
            LexicalPrecedence.REGISTER_EVIDENCE,
            LexicalPrecedence.DOMAIN_GLOSSARY,
            LexicalPrecedence.CURATED_RULE,
            LexicalPrecedence.LICENSED_RESOURCE,
            LexicalPrecedence.NO_CHANGE,
        )


class TestSenseStatus:
    def test_members(self) -> None:
        assert (
            SenseStatus.SUPPORTED.value,
            SenseStatus.AMBIGUOUS.value,
            SenseStatus.UNSUPPORTED.value,
        ) == ("supported", "ambiguous", "unsupported")


class TestLexicalRule:
    def test_fields(self) -> None:
        rule = _rule()
        assert rule.rule_id == "cr-test"
        assert rule.source_token == "utilize"
        assert rule.target_token == "use"
        assert rule.sense == "general"
        assert rule.precedence is LexicalPrecedence.CURATED_RULE
        assert rule.confidence == 0.9
        assert rule.provenance == "curated-in-repo"

    def test_is_frozen(self) -> None:
        rule = _rule()
        with pytest.raises(AttributeError):
            rule.target_token = "employ"  # type: ignore[misc]

    @pytest.mark.parametrize("confidence", [1.5, -0.1])
    def test_rejects_confidence_out_of_range(self, confidence: float) -> None:
        with pytest.raises(DomainError, match="confidence"):
            LexicalRule(
                rule_id="cr-x",
                source_token="a",
                target_token="b",
                sense="general",
                precedence=LexicalPrecedence.CURATED_RULE,
                confidence=confidence,
                provenance="curated-in-repo",
            )


class TestRulesetVersion:
    def test_hash_deterministic(self) -> None:
        ruleset = RulesetVersion(version="v1", rules=(_rule(),))
        digest = ruleset.hash()
        assert digest == ruleset.hash()
        assert len(digest) == 64

    def test_hash_changes_with_rules(self) -> None:
        base = RulesetVersion(version="v1", rules=(_rule(),))
        other = RulesetVersion(
            version="v1", rules=(_rule(rule_id="cr-2", source="commence", target="begin"),)
        )
        assert base.hash() != other.hash()

    def test_hash_changes_with_version(self) -> None:
        base = RulesetVersion(version="v1", rules=(_rule(),))
        other = RulesetVersion(version="v2", rules=(_rule(),))
        assert base.hash() != other.hash()


class TestLoadBundledRules:
    def test_loads_real_curated_rules(self) -> None:
        ruleset = load_bundled_rules()
        assert len(ruleset.rules) >= 3
        assert ruleset.version
        for rule in ruleset.rules:
            assert rule.provenance == "curated-in-repo"
            assert rule.precedence is LexicalPrecedence.CURATED_RULE
            assert 0.0 <= rule.confidence <= 1.0

    def test_rule_ids_unique(self) -> None:
        ruleset = load_bundled_rules()
        ids = [rule.rule_id for rule in ruleset.rules]
        assert len(ids) == len(set(ids))

    def test_known_rule_present(self) -> None:
        ruleset = load_bundled_rules()
        by_id = {rule.rule_id: rule for rule in ruleset.rules}
        assert by_id["cr-001"].source_token == "utilize"
        assert by_id["cr-001"].target_token == "use"
        assert by_id["cr-001"].sense == "general"


class TestLoadProtectedTerms:
    @pytest.mark.parametrize("domain", ["general", "medical", "legal"])
    def test_non_empty_for_each_domain(self, domain: str) -> None:
        terms = load_protected_terms(domain)
        assert len(terms) >= 1
        assert all(isinstance(term, str) and term for term in terms)

    def test_unknown_domain_rejected(self) -> None:
        with pytest.raises(DomainError, match="Unknown protected-term domain"):
            load_protected_terms("chemistry")

    def test_known_general_term_present(self) -> None:
        assert "GDPR" in load_protected_terms("general")

    def test_known_medical_term_present(self) -> None:
        assert "tachycardia" in load_protected_terms("medical")

    def test_known_legal_term_present(self) -> None:
        assert "force majeure" in load_protected_terms("legal")


class TestPayloadRoundTrip:
    def test_round_trip_preserves_bundled_ruleset(self) -> None:
        ruleset = load_bundled_rules()
        rebuilt = ruleset_from_payload(ruleset_to_payload(ruleset))
        assert rebuilt == ruleset
        assert rebuilt.hash() == ruleset.hash()

    def test_payload_shape(self) -> None:
        ruleset = RulesetVersion(version="v1", rules=(_rule(),))
        payload = ruleset_to_payload(ruleset)
        assert payload["schema"] == "lexicon"
        assert payload["schema_version"] == 1
        assert payload["version"] == "v1"
        raw_rules = payload["rules"]
        assert isinstance(raw_rules, list)
        item = raw_rules[0]
        assert isinstance(item, dict)
        assert item["rule_id"] == "cr-test"
        assert item["precedence"] == "curated_rule"
        assert item["provenance"] == "curated-in-repo"


class TestRulesetFromPayloadStrict:
    @staticmethod
    def _rule_payload(**overrides: object) -> dict[str, object]:
        base: dict[str, object] = {
            "rule_id": "cr-1",
            "source_token": "utilize",
            "target_token": "use",
            "sense": "general",
            "precedence": "curated_rule",
            "confidence": 0.9,
            "provenance": "curated-in-repo",
        }
        base.update(overrides)
        return base

    @staticmethod
    def _payload(**overrides: object) -> dict[str, object]:
        base: dict[str, object] = {
            "schema": "lexicon",
            "schema_version": 1,
            "version": "v1",
            "rules": [TestRulesetFromPayloadStrict._rule_payload()],
        }
        base.update(overrides)
        return base

    def test_valid_payload_round_trips(self) -> None:
        ruleset = ruleset_from_payload(self._payload())
        assert ruleset.version == "v1"
        assert ruleset.rules[0].rule_id == "cr-1"

    @pytest.mark.parametrize(
        ("field", "value"),
        [
            ("schema", "other"),
            ("schema_version", 2),
            ("version", ""),
            ("version", 7),
            ("rules", "not-a-list"),
            ("rules", ["utilize"]),
        ],
    )
    def test_invalid_top_level_rejected(self, field: str, value: object) -> None:
        with pytest.raises(DomainError):
            ruleset_from_payload(self._payload(**{field: value}))

    def test_unknown_key_rejected(self) -> None:
        with pytest.raises(DomainError, match="unexpected key"):
            ruleset_from_payload(self._payload(extra="x"))

    def test_missing_key_rejected(self) -> None:
        payload = self._payload()
        del payload["version"]
        with pytest.raises(DomainError, match="missing key"):
            ruleset_from_payload(payload)

    def test_unknown_precedence_rejected(self) -> None:
        with pytest.raises(DomainError, match="unknown precedence"):
            ruleset_from_payload(self._payload(rules=[self._rule_payload(precedence="bogus")]))

    @pytest.mark.parametrize("confidence", ["high", 7, True])
    def test_bad_confidence_rejected(self, confidence: object) -> None:
        with pytest.raises(DomainError, match="confidence"):
            ruleset_from_payload(self._payload(rules=[self._rule_payload(confidence=confidence)]))

    def test_missing_rule_field_rejected(self) -> None:
        rule = self._rule_payload()
        del rule["target_token"]
        with pytest.raises(DomainError, match="missing key"):
            ruleset_from_payload(self._payload(rules=[rule]))

    def test_empty_rule_fields_rejected(self) -> None:
        with pytest.raises(DomainError, match="non-empty"):
            ruleset_from_payload(self._payload(rules=[self._rule_payload(source_token="")]))
