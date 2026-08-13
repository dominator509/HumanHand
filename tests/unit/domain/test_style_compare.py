"""Unit tests for deterministic style comparison (EP-014)."""

from __future__ import annotations

import pytest

from humanhand.domain.canonical_document import CanonicalDocument, build_document
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
from humanhand.domain.style_compare import StyleComparisonReport, compare_profile
from humanhand.domain.style_invariants import InvariantKind, InvariantStatus
from humanhand.domain.style_profiles import build_profile
from humanhand.domain.style_surface import build_surface_document


def _span(text: str, *, span_id: str = "a1") -> AuthorshipSpan:
    return AuthorshipSpan(
        span_id=span_id,
        source_location=SourceLocation(0, len(text)),
        text=text,
        authorship_class=AuthorshipClass.AUTHENTIC_USER_PROSE,
        review_status="resolved",
    )


def _package(package_id: str, text: str) -> StyleEvidencePackage:
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
        profile_label="default",
        original_artifact=OriginalStyleArtifact(
            artifact_id=f"art-{package_id}",
            sha256=f"sha-{package_id}",
            size_bytes=len(text.encode("utf-8")),
            stored=True,
        ),
        exact_surface=surface,
        authorship=AuthorshipMap(spans=(_span(text),), excluded=()),
        approved_exemplars=(),
        parser_version="1",
        ruleset_version=STYLE_RULESET_VERSION,
    )


def _document(text: str) -> CanonicalDocument:
    root = NodeBuilder(node_type=NodeType.DOCUMENT)
    root.add_child(NodeBuilder(node_type=NodeType.PARAGRAPH, text=text))
    return build_document(
        root=root,
        lane="style",
        parser_name="text",
        parser_version="1",
        policy=ImportPolicy(lane="style"),
        surface_text=text,
    )


def _prose(word_count: int, *, prefix: str = "word") -> str:
    tokens = [f"{prefix}{i}" for i in range(word_count)]
    sentences = [" ".join(tokens[i : i + 10]) + "." for i in range(0, word_count, 10)]
    paragraphs = [" ".join(sentences[i : i + 3]) for i in range(0, len(sentences), 3)]
    return "\n\n".join(paragraphs)


def _varied_prose(
    word_count: int,
    *,
    em_dash: bool = False,
    hyphen: bool = False,
    contractions: bool = False,
) -> str:
    sizes = [8, 9, 10, 11, 12]
    sentences: list[str] = []
    count = 0
    while count < word_count:
        size = sizes[len(sentences) % 5]
        sentence: list[str] = []
        for _ in range(size):
            token = "don't" if contractions and count % 5 == 0 else f"token{count}"
            sentence.append(token)
            count += 1
        text = " ".join(sentence)
        if em_dash:
            text = text.replace("token1", "token1 —", 1)
        elif hyphen:
            text = text.replace("token0", "token0-", 1)
        sentences.append(text + ".")
    paragraph_sizes = [2, 3, 4]
    paragraphs: list[str] = []
    start = 0
    while start < len(sentences):
        size = paragraph_sizes[start % 3]
        paragraphs.append(" ".join(sentences[start : start + size]))
        start += size
    return "\n\n".join(paragraphs)


class TestCompareProfile:
    def test_identical_text_has_zero_distances_and_no_violations(self) -> None:
        text = _varied_prose(300)
        profile = build_profile(profile_id="default", packages=(_package("cmp-1", text),))
        report = compare_profile(profile, _document(text))
        assert isinstance(report, StyleComparisonReport)
        assert report.profile_id == "default"
        assert set(report.metric_distances) == {
            "sentence_mean",
            "sentence_stdev",
            "type_token_ratio",
            "function_word_ratio",
            "contraction_frequency",
            "punctuation_per_100_chars",
            "question_frequency",
        }
        assert all(distance == 0.0 for distance in report.metric_distances.values())
        assert report.hard_invariant_violations == ()
        assert report.outlier_sentences == ()
        assert report.outlier_paragraphs == ()
        assert report.lexical_preference_conflicts == ()
        assert report.formatting_conflicts == ()
        assert report.sample_sufficiency == "insufficient"
        assert report.authorship_status == "resolved"
        assert report.confidence == pytest.approx(300 / 5000.0)
        assert report.evidence_coverage == pytest.approx(300 / 1000.0)
        assert not hasattr(report, "authorship")

    def test_detects_hard_invariant_violations_and_formatting_conflicts(self) -> None:
        profile_text = _varied_prose(300, em_dash=True, contractions=True)
        document_text = _varied_prose(300, hyphen=True)
        profile = build_profile(profile_id="default", packages=(_package("cmp-2", profile_text),))
        report = compare_profile(profile, _document(document_text))
        by_kind = {violation.kind for violation in report.hard_invariant_violations}
        assert by_kind == {InvariantKind.DASH_TYPE, InvariantKind.CONTRACTION_POLICY}
        dash = next(
            violation
            for violation in report.hard_invariant_violations
            if violation.kind is InvariantKind.DASH_TYPE
        )
        assert dash.value == "em"
        assert dash.status is InvariantStatus.VIOLATED
        assert dash.evidence == "profile=em document=hyphen"
        assert report.formatting_conflicts == ("dash: em vs hyphen",)
        contraction = next(
            violation
            for violation in report.hard_invariant_violations
            if violation.kind is InvariantKind.CONTRACTION_POLICY
        )
        assert contraction.value == "contractions_present"
        assert report.metric_distances["contraction_frequency"] > 0.0

    def test_metric_distances_are_documented_and_bounded(self) -> None:
        profile = build_profile(profile_id="default", packages=(_package("cmp-3", _prose(200)),))
        report = compare_profile(profile, _document(_varied_prose(200, contractions=True)))
        for value in report.metric_distances.values():
            assert 0.0 <= value <= 1.0
        assert report.metric_distances["sentence_stdev"] == pytest.approx(1.0)
        assert report.metric_distances["contraction_frequency"] == pytest.approx(0.2)

    def test_outlier_sentences_and_paragraphs_are_reported(self) -> None:
        profile_text = _varied_prose(300)
        long_sentence = " ".join(f"big{i}" for i in range(80)) + "."
        short_sentence = " ".join(f"short{i}" for i in range(10)) + "."
        long_paragraph = " ".join(short_sentence for _ in range(60))
        document_text = profile_text + "\n\n" + long_sentence + "\n\n" + long_paragraph
        profile = build_profile(profile_id="default", packages=(_package("cmp-4", profile_text),))
        report = compare_profile(profile, _document(document_text))
        assert report.outlier_sentences == ("80",)
        assert report.outlier_paragraphs == ("60",)

    def test_sample_sufficiency_and_lexical_preference_conflicts(self) -> None:
        profile = build_profile(profile_id="default", packages=(_package("cmp-5", _prose(200)),))
        small = compare_profile(profile, _document(_prose(40, prefix="alt")))
        assert small.sample_sufficiency == "insufficient"
        assert small.evidence_coverage == pytest.approx(40 / 1000.0)
        assert small.confidence < 1.0
        assert small.lexical_preference_conflicts == (
            "word0 word1",
            "word1 word2",
            "word2 word3",
        )

        large = compare_profile(profile, _document(_prose(1200)), min_words_for_sufficiency=1000)
        assert large.sample_sufficiency == "sufficient"
        assert large.evidence_coverage == 1.0
        assert large.confidence > 0.0
