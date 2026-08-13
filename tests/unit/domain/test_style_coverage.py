"""Unit tests for style coverage reporting (EP-014)."""

from __future__ import annotations

import hashlib

from humanhand.domain.document_nodes import SourceLocation
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
from humanhand.domain.style_coverage import StyleCoverageReport, build_coverage_report
from humanhand.domain.style_surface import CanonicalSurfaceDocument, SurfaceStatistics

SURFACE_TEXT = "A reviewed style sample surface."
VOICE_WORD_COUNT = 1200


def _voice_text(word_count: int = VOICE_WORD_COUNT) -> str:
    # Hand-verified: the style word tokenizer pattern
    # re.findall(r"[a-zA-Z0-9]+(?:'[a-zA-Z]+)?", ...) matches every
    # "wordN" token exactly once, so the count is exactly `word_count`.
    return " ".join(f"word{i}" for i in range(word_count))


def _surface(text: str) -> CanonicalSurfaceDocument:
    # Hand-verified: sha256 over the utf-8 bytes of the surface text,
    # statistics derived directly from the text.
    return CanonicalSurfaceDocument(
        artifact_id="surf-1",
        surface_text=text,
        sha256=hashlib.sha256(text.encode("utf-8")).hexdigest(),
        statistics=SurfaceStatistics(
            code_points=len(text),
            bytes_utf8=len(text.encode("utf-8")),
            lines=1,
            paragraphs=1,
            headings=0,
            list_items=0,
            table_cells=0,
            quotations=0,
            code_blocks=0,
            hyperlinks=0,
        ),
        node_count=1,
    )


def _span(
    span_id: str,
    text: str,
    *,
    authorship_class: AuthorshipClass,
    resolved: bool,
) -> AuthorshipSpan:
    return AuthorshipSpan(
        span_id=span_id,
        source_location=SourceLocation(
            start_offset=0, end_offset=len(text), line_start=1, line_end=1
        ),
        text=text,
        authorship_class=authorship_class,
        review_status="resolved" if resolved else "unresolved",
        decided_by="cli" if resolved else "",
    )


def _package(
    spans: tuple[AuthorshipSpan, ...], surface_text: str = SURFACE_TEXT
) -> StyleEvidencePackage:
    surface = _surface(surface_text)
    return StyleEvidencePackage(
        schema_version=STYLE_EVIDENCE_PACKAGE_SCHEMA_VERSION,
        package_id="pkg-1",
        profile_label="default",
        original_artifact=OriginalStyleArtifact(
            artifact_id="art-1",
            sha256=surface.sha256,
            size_bytes=len(surface_text.encode("utf-8")),
            stored=True,
        ),
        exact_surface=surface,
        authorship=AuthorshipMap(spans=spans, excluded=()),
        approved_exemplars=(),
        parser_version="1",
        ruleset_version=STYLE_RULESET_VERSION,
    )


def _resolved_voice_span() -> AuthorshipSpan:
    return _span(
        "s1",
        _voice_text(),
        authorship_class=AuthorshipClass.AUTHENTIC_USER_PROSE,
        resolved=True,
    )


def test_resolved_sufficient_sample_is_complete() -> None:
    package = _package((_resolved_voice_span(),))
    report = build_coverage_report(package)

    # 1200 words >= the default 1000-word sufficiency threshold.
    assert report.sample_sufficiency == "sufficient"
    # Surface text is non-empty, so visible extraction coverage is 100%.
    assert report.visible_text_coverage == 1.0
    # Exact surface preservation is guaranteed by construction (ADR-003).
    assert report.code_point_coverage == 1.0
    assert report.structure_coverage == 1.0
    assert report.formatting_coverage == 1.0
    # No unresolved spans and no unsupported features, so the blueprint
    # 8.2 conditions derivable from the package all hold.
    assert report.unresolved_span_count == 0
    assert report.unsupported_features == ()
    assert report.status == "complete"
    assert report.package_id == "pkg-1"


def test_unresolved_span_requires_human_review() -> None:
    resolved = _resolved_voice_span()
    unresolved = _span(
        "s2",
        "Unreviewed region of the sample.",
        authorship_class=AuthorshipClass.UNKNOWN,
        resolved=False,
    )
    report = build_coverage_report(_package((resolved, unresolved)))

    # Even with a sufficient sample, an unresolved authorship span forces
    # human review; the report must never claim complete.
    assert report.unresolved_span_count == 1
    assert report.sample_sufficiency == "sufficient"
    assert report.visible_text_coverage == 1.0
    assert report.status == "human_review_required"


def test_insufficient_sample_is_partial() -> None:
    package = _package((_resolved_voice_span(),))
    # 1200 words is far below this threshold, so the sample is
    # insufficient even though everything else is resolved and covered.
    report = build_coverage_report(package, min_words_for_sufficiency=100000)

    assert report.sample_sufficiency == "insufficient"
    assert report.unresolved_span_count == 0
    assert report.visible_text_coverage == 1.0
    assert report.status == "partial"


def test_build_coverage_report_deterministic_replay() -> None:
    package = _package((_resolved_voice_span(),))
    first = build_coverage_report(package)
    second = build_coverage_report(package)
    assert first == second
    # Report is a frozen dataclass value with no hidden state.
    assert isinstance(first, StyleCoverageReport)
