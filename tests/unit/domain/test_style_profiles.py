"""Unit tests for style evidence profiles (EP-014)."""

from __future__ import annotations

import json

import pytest

from humanhand.domain.canonical_document import build_document
from humanhand.domain.document_nodes import NodeBuilder, NodeType, SourceLocation
from humanhand.domain.import_policy import ImportPolicy
from humanhand.domain.style_artifacts import (
    STYLE_EVIDENCE_PACKAGE_SCHEMA_VERSION,
    STYLE_RULESET_VERSION,
    OriginalStyleArtifact,
    StyleEvidencePackage,
)
from humanhand.domain.style_authorship import (
    AuthorshipClass,
    AuthorshipMap,
    AuthorshipSpan,
)
from humanhand.domain.style_coverage import StyleCoverageReport
from humanhand.domain.style_profiles import (
    STYLE_PROFILE_SCHEMA_VERSION,
    aggregate_coverage,
    build_profile,
    profile_from_json,
    profile_to_json,
    profile_to_payload,
)
from humanhand.domain.style_surface import build_surface_document
from humanhand.domain.types import DomainError


def _span(
    text: str, *, span_id: str = "a1", voice: bool = True, resolved: bool = True
) -> AuthorshipSpan:
    authorship_class = AuthorshipClass.AUTHENTIC_USER_PROSE if voice else AuthorshipClass.QUOTATION
    if not resolved:
        authorship_class = AuthorshipClass.UNKNOWN
    return AuthorshipSpan(
        span_id=span_id,
        source_location=SourceLocation(0, len(text)),
        text=text,
        authorship_class=authorship_class,
        review_status="resolved" if resolved else "unresolved",
    )


def _package(
    package_id: str,
    text: str,
    *,
    profile_label: str = "default",
    spans: tuple[AuthorshipSpan, ...] | None = None,
) -> StyleEvidencePackage:
    root = NodeBuilder(node_type=NodeType.DOCUMENT)
    root.add_child(NodeBuilder(node_type=NodeType.PARAGRAPH, text=text))
    document = build_document(
        root=root,
        lane="style",
        parser_name="text",
        parser_version="1",
        policy=ImportPolicy(lane="style"),
        surface_text=text,
    )
    surface = build_surface_document(artifact_id=f"art-{package_id}", document=document)
    return StyleEvidencePackage(
        schema_version=STYLE_EVIDENCE_PACKAGE_SCHEMA_VERSION,
        package_id=package_id,
        profile_label=profile_label,
        original_artifact=OriginalStyleArtifact(
            artifact_id=f"art-{package_id}",
            sha256=f"sha-{package_id}",
            size_bytes=len(text.encode("utf-8")),
            stored=True,
        ),
        exact_surface=surface,
        authorship=AuthorshipMap(spans=spans if spans is not None else (_span(text),), excluded=()),
        approved_exemplars=(),
        parser_version="1",
        ruleset_version=STYLE_RULESET_VERSION,
    )


def _prose(word_count: int, *, prefix: str = "word") -> str:
    tokens = [f"{prefix}{i}" for i in range(word_count)]
    sentences = [" ".join(tokens[i : i + 10]) + "." for i in range(0, word_count, 10)]
    paragraphs = [" ".join(sentences[i : i + 3]) for i in range(0, len(sentences), 3)]
    return "\n\n".join(paragraphs)


class TestBuildProfile:
    def test_builds_profile_from_approved_voice_spans(self) -> None:
        text = _prose(200)
        profile = build_profile(profile_id="default", packages=(_package("sty-a", text),))
        assert profile.schema_version == STYLE_PROFILE_SCHEMA_VERSION
        assert profile.profile_id == "default"
        assert profile.profile_label == "default"
        assert profile.package_ids == ("sty-a",)
        assert profile.voice_text == text
        assert profile.sample_word_count == 200
        assert profile.min_words_for_sufficiency == 1000
        assert profile.metrics.word_count == 200
        assert len(profile.hard_invariants) == 10
        assert len(profile.soft_tendencies) == 4
        assert profile.coverage.package_id == "default"
        assert profile.coverage.sample_sufficiency == "insufficient"
        assert profile.status == "partial"
        assert profile.status == profile.coverage.status

    def test_voice_text_uses_only_resolved_authentic_spans(self) -> None:
        voice = _span("authentic prose words.")
        quotation = _span("quoted material.", span_id="a2", voice=False)
        package = _package(
            "sty-b", "authentic prose words. quoted material.", spans=(voice, quotation)
        )
        profile = build_profile(profile_id="default", packages=(package,))
        assert profile.voice_text == "authentic prose words."
        assert profile.sample_word_count == 3

        unresolved = _span("unresolved text here.", span_id="a3", resolved=False)
        review_package = _package(
            "sty-c",
            "authentic prose words. unresolved text here.",
            spans=(voice, unresolved),
        )
        profile = build_profile(profile_id="default", packages=(review_package,))
        assert profile.voice_text == "authentic prose words."
        assert profile.coverage.unresolved_span_count == 1
        assert profile.status == "human_review_required"

    def test_build_profile_aggregates_packages_fail_closed(self) -> None:
        first = _package("sty-1", _prose(200))
        second = _package("sty-2", _prose(100))
        unresolved = _package(
            "sty-3",
            _prose(150),
            spans=(_span(_prose(150), span_id="a1", resolved=False),),
        )
        profile = build_profile(profile_id="default", packages=(first, second, unresolved))
        assert profile.package_ids == ("sty-1", "sty-2", "sty-3")
        assert profile.voice_text == _prose(200) + "\n\n" + _prose(100)
        assert profile.sample_word_count == 300
        assert profile.coverage.unresolved_span_count == 1
        assert profile.status == "human_review_required"
        assert profile.status == profile.coverage.status

        with pytest.raises(DomainError):
            build_profile(profile_id="default", packages=())

    def test_min_words_for_sufficiency_and_joined_reconciliation(self) -> None:
        package = _package("sty-t", _prose(200))
        default = build_profile(profile_id="default", packages=(package,))
        assert default.coverage.sample_sufficiency == "insufficient"
        assert default.status == "partial"

        raised = build_profile(
            profile_id="default", packages=(package,), min_words_for_sufficiency=100
        )
        assert raised.coverage.sample_sufficiency == "sufficient"
        assert raised.coverage.visible_text_coverage == 1.0
        assert raised.status == "complete"

        joined = build_profile(
            profile_id="default",
            packages=(_package("sty-t1", _prose(600)), _package("sty-t2", _prose(600))),
        )
        assert joined.coverage.sample_sufficiency == "sufficient"
        assert joined.status == "complete"

    def test_aggregate_coverage_is_fail_closed(self) -> None:
        complete = StyleCoverageReport(
            package_id="p1",
            visible_text_coverage=1.0,
            code_point_coverage=1.0,
            structure_coverage=1.0,
            formatting_coverage=1.0,
            unsupported_features=(),
            unresolved_span_count=0,
            status="complete",
            sample_sufficiency="sufficient",
        )
        partial = StyleCoverageReport(
            package_id="p2",
            visible_text_coverage=1.0,
            code_point_coverage=1.0,
            structure_coverage=1.0,
            formatting_coverage=1.0,
            unsupported_features=(),
            unresolved_span_count=0,
            status="partial",
            sample_sufficiency="insufficient",
        )
        review = StyleCoverageReport(
            package_id="p3",
            visible_text_coverage=0.5,
            code_point_coverage=1.0,
            structure_coverage=1.0,
            formatting_coverage=1.0,
            unsupported_features=("tables",),
            unresolved_span_count=2,
            status="human_review_required",
            sample_sufficiency="sufficient",
        )
        aggregated = aggregate_coverage(
            ("p1", "p2", "p3"), (complete, partial, review), profile_id="default"
        )
        assert aggregated.package_id == "default"
        assert aggregated.visible_text_coverage == 0.5
        assert aggregated.unresolved_span_count == 2
        assert aggregated.unsupported_features == ("tables",)
        assert aggregated.sample_sufficiency == "insufficient"
        assert aggregated.status == "human_review_required"

        empty = aggregate_coverage((), (), profile_id="default")
        assert empty.status == "human_review_required"
        assert empty.sample_sufficiency == "insufficient"
        assert empty.visible_text_coverage == 0.0

        with pytest.raises(DomainError):
            aggregate_coverage(("p9",), (complete,), profile_id="default")

    def test_profile_json_round_trip_is_stable_and_validated(self) -> None:
        profile = build_profile(
            profile_id="default",
            packages=(_package("sty-r", _prose(200)),),
            min_words_for_sufficiency=100,
        )
        text = profile_to_json(profile)
        assert text.endswith("\n")
        rebuilt = profile_from_json(text)
        assert rebuilt == profile
        assert profile_to_json(rebuilt) == text

        with pytest.raises(DomainError):
            profile_from_json("not json")
        with pytest.raises(DomainError):
            profile_from_json("[]")
        with pytest.raises(DomainError):
            profile_from_json('{"schema": "style-evidence-package", "schema_version": 1}')
        with pytest.raises(DomainError):
            profile_from_json('{"schema": "style-evidence-profile", "schema_version": 2}')

        payload = profile_to_payload(profile)
        del payload["metrics"]
        with pytest.raises(DomainError):
            profile_from_json(json.dumps(payload))
