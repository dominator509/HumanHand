"""Integration tests for the deterministic lexical proposal pipeline (EP-017).

The pipeline imports the parallel lexical modules (lexical_rules,
lexical_types, lexical_context) owned by other workstreams; this module
tests the pipeline end to end against the real bundled ruleset.
"""

from __future__ import annotations

from dataclasses import replace

import pytest

from humanhand.domain.document_nodes import SourceLocation
from humanhand.domain.document_serialization import dumps_stable
from humanhand.domain.lexical_context import build_contexts
from humanhand.domain.lexical_normalizer import (
    ChangeStatus,
    LexicalProposal,
    apply_changes,
    proposal_from_payload,
    proposal_to_payload,
    propose_changes,
)
from humanhand.domain.lexical_types import LexicalPrecedence, LexicalRule, RulesetVersion
from humanhand.domain.protected_spans import ProtectedSpan, ProtectedSpanSet, SpanKind, SpanStatus
from humanhand.domain.types import DomainError
from humanhand.infra.lexicons import load_bundled_rules


@pytest.fixture()
def ruleset() -> RulesetVersion:
    return load_bundled_rules()


def _propose(
    text: str, ruleset: RulesetVersion, protected_spans: ProtectedSpanSet | None = None
) -> LexicalProposal:
    spans = protected_spans if protected_spans is not None else ProtectedSpanSet(spans=())
    contexts = build_contexts(text, spans)
    return propose_changes(
        text=text,
        ruleset=ruleset,
        contexts=contexts,
        user_preferences={},
        project_glossary=(),
        register_rules=(),
        domain_glossary=(),
        safe_threshold=0.8,
        protected_spans=protected_spans,
    )


class TestProposeChanges:
    def test_proposes_utilize_to_use(self, ruleset: RulesetVersion) -> None:
        text = "We utilize this tool."
        proposal = _propose(text, ruleset)
        changes = [c for c in proposal.changes if c.source_surface == "utilize"]
        assert changes, "bundled ruleset must propose the utilize -> use change"
        change = changes[0]
        assert change.target == "use"
        assert change.status in {ChangeStatus.SAFE, ChangeStatus.PROPOSED}

    def test_unknown_token_is_silent_noop(self, ruleset: RulesetVersion) -> None:
        surfaces = {rule.source_token for rule in ruleset.rules}
        unknown = next(word for word in ("zzqxm", "qwzxl", "xqzwr") if word not in surfaces)
        proposal = _propose(f"{unknown}.", ruleset)
        assert proposal.changes == ()
        assert proposal.findings == ()

    def test_punctuation_is_preserved_around_a_change(self, ruleset: RulesetVersion) -> None:
        text = "We utilize, this tool."
        proposal = _propose(text, ruleset)
        assert proposal.changes[0].source_surface == "utilize"
        assert apply_changes(text, proposal) == "We use, this tool."

    def test_supported_inflection_uses_valid_spelling(self, ruleset: RulesetVersion) -> None:
        text = "We are utilizing this tool."
        proposal = _propose(text, ruleset)
        assert proposal.changes[0].target == "using"
        assert apply_changes(text, proposal) == "We are using this tool."

    def test_project_glossary_can_introduce_a_non_curated_source(
        self, ruleset: RulesetVersion
    ) -> None:
        text = "A bespoke result."
        glossary_rule = LexicalRule(
            rule_id="pg-1",
            source_token="bespoke",
            target_token="custom",
            sense="general",
            precedence=LexicalPrecedence.PROJECT_GLOSSARY,
            confidence=1.0,
            provenance="project-glossary",
        )
        spans = ProtectedSpanSet(spans=())
        proposal = propose_changes(
            text=text,
            ruleset=ruleset,
            contexts=build_contexts(text, spans),
            user_preferences={},
            project_glossary=(glossary_rule,),
            register_rules=(),
            domain_glossary=(),
            safe_threshold=0.8,
            protected_spans=spans,
        )
        assert proposal.changes[0].target == "custom"

    def test_ambiguous_same_precedence_rules_are_a_noop(self, ruleset: RulesetVersion) -> None:
        text = "A bespoke result."
        rules = tuple(
            LexicalRule(
                rule_id=f"pg-{index}",
                source_token="bespoke",
                target_token=target,
                sense=sense,
                precedence=LexicalPrecedence.PROJECT_GLOSSARY,
                confidence=1.0,
                provenance="project-glossary",
            )
            for index, (target, sense) in enumerate(
                (("custom", "product"), ("tailored", "service")), start=1
            )
        )
        spans = ProtectedSpanSet(spans=())
        proposal = propose_changes(
            text=text,
            ruleset=ruleset,
            contexts=build_contexts(text, spans),
            user_preferences={},
            project_glossary=rules,
            register_rules=(),
            domain_glossary=(),
            safe_threshold=0.8,
            protected_spans=spans,
        )
        assert proposal.changes == ()
        assert proposal.findings == ("ambiguous_sense:bespoke",)

    def test_multiword_rule_precedes_overlapping_tokens(self) -> None:
        phrase_rule = LexicalRule(
            rule_id="cr-phrase",
            source_token="in order to",
            target_token="to",
            sense="general",
            precedence=LexicalPrecedence.CURATED_RULE,
            confidence=1.0,
            provenance="curated-in-repo",
        )
        ruleset = RulesetVersion(version="phrases-v1", rules=(phrase_rule,))
        text = "We paused in order to check."
        proposal = _propose(text, ruleset)
        assert len(proposal.changes) == 1
        assert proposal.changes[0].source_surface == "in order to"
        assert apply_changes(text, proposal) == "We paused to check."

    def test_protected_span_yields_protected_skip_finding(self, ruleset: RulesetVersion) -> None:
        text = 'They said "We utilize this tool."'
        start = text.index('"')
        end = text.index('"', start + 1) + 1
        span = ProtectedSpan(
            span_id="s1",
            kind=SpanKind.QUOTATION,
            source_location=SourceLocation(start_offset=start, end_offset=end),
            text=text[start:end],
            label="",
            status=SpanStatus.EXTRACTED,
        )
        protected = ProtectedSpanSet(spans=(span,))
        proposal = _propose(text, ruleset, protected_spans=protected)
        assert any(finding == "protected_skip:utilize" for finding in proposal.findings)

    def test_findings_are_compact_codes(self, ruleset: RulesetVersion) -> None:
        proposal = _propose("We utilize this tool.", ruleset)
        for finding in proposal.findings:
            assert " " not in finding
            assert len(finding) <= 60

    def test_repeated_proposals_are_byte_identical(self, ruleset: RulesetVersion) -> None:
        text = "We utilize this tool."
        first = proposal_to_payload(_propose(text, ruleset))
        second = proposal_to_payload(_propose(text, ruleset))
        assert first == second
        assert dumps_stable(first) == dumps_stable(second)


class TestProposalPayloadRoundTrip:
    def test_real_proposal_round_trips(self, ruleset: RulesetVersion) -> None:
        text = "We utilize this tool."
        proposal = _propose(text, ruleset)
        restored = proposal_from_payload(proposal_to_payload(proposal))
        assert restored == proposal


class TestApplyChanges:
    def test_applied_text_uses_target_and_drops_source(self, ruleset: RulesetVersion) -> None:
        text = "We utilize this tool."
        proposal = _propose(text, ruleset)
        applied = apply_changes(text, proposal)
        assert "use" in applied
        assert "utilize" not in applied

    def test_drifted_text_is_rejected(self, ruleset: RulesetVersion) -> None:
        text = "We utilize this tool."
        proposal = _propose(text, ruleset)
        drifted = replace(
            proposal, changes=tuple(replace(c, offset=c.offset + 1) for c in proposal.changes)
        )
        with pytest.raises(DomainError, match="offset"):
            apply_changes(text, drifted)

    def test_only_status_applies_matching_changes(self, ruleset: RulesetVersion) -> None:
        text = "We utilize this tool."
        proposal = _propose(text, ruleset)
        assert proposal.changes, "bundled ruleset must propose a change"
        status = proposal.changes[0].status
        applied = apply_changes(text, proposal, only_status=status)
        assert "utilize" not in applied

    def test_only_status_other_leaves_text_untouched(self, ruleset: RulesetVersion) -> None:
        text = "We utilize this tool."
        proposal = _propose(text, ruleset)
        assert proposal.changes, "bundled ruleset must propose a change"
        status = proposal.changes[0].status
        other = ChangeStatus.PROPOSED if status is ChangeStatus.SAFE else ChangeStatus.SAFE
        assert apply_changes(text, proposal, only_status=other) == text
