"""Style coverage reporting for evidence packages (EP-014/EP-019).

A package may claim ``complete`` only when visible text/code points are exact,
all authorship spans are resolved, the approved sample is sufficient, and the
import adapter reported no unsupported structures or error findings.

The importer currently reports unsupported features as named capability gaps,
not fractional per-feature measurements. This module therefore uses a strict
binary contract rather than fabricating precision: structure and formatting
coverage are 1.0 only when no unsupported feature is reported, otherwise 0.0.
That is deliberately conservative and prevents rich-format imports from being
misrepresented as 100% faithful.
"""

from __future__ import annotations

import re
from dataclasses import dataclass

from humanhand.domain.style_artifacts import StyleEvidencePackage

_WORD_TOKEN_RE = re.compile(r"[a-zA-Z0-9]+(?:'[a-zA-Z]+)?")


@dataclass(frozen=True)
class StyleCoverageReport:
    """Deterministic coverage state of one style evidence package."""

    package_id: str
    visible_text_coverage: float
    code_point_coverage: float
    structure_coverage: float
    formatting_coverage: float
    unsupported_features: tuple[str, ...]
    unresolved_span_count: int
    status: str  # complete | partial | human_review_required
    sample_sufficiency: str  # sufficient | insufficient


def build_coverage_report(
    package: StyleEvidencePackage, *, min_words_for_sufficiency: int = 1000
) -> StyleCoverageReport:
    """Build an honest deterministic coverage report.

    Exact surface text provides full visible-text/code-point preservation for
    the represented surface. Importer-declared unsupported features block
    structure/formatting completeness and require human review. An insufficient
    but otherwise clean sample is partial rather than complete.
    """
    visible_text_coverage = 1.0 if package.exact_surface.surface_text else 0.0
    code_point_coverage = 1.0 if package.exact_surface.surface_text else 0.0
    unresolved_span_count = len(package.authorship.unresolved_spans)
    word_count = _voice_profile_word_count(package)
    sample_sufficiency = "sufficient" if word_count >= min_words_for_sufficiency else "insufficient"
    unsupported_features = package.unsupported_features
    structure_coverage = 0.0 if unsupported_features else 1.0
    formatting_coverage = 0.0 if unsupported_features else 1.0

    if unresolved_span_count > 0 or unsupported_features:
        status = "human_review_required"
    elif sample_sufficiency == "sufficient" and visible_text_coverage == 1.0:
        status = "complete"
    else:
        status = "partial"
    return StyleCoverageReport(
        package_id=package.package_id,
        visible_text_coverage=visible_text_coverage,
        code_point_coverage=code_point_coverage,
        structure_coverage=structure_coverage,
        formatting_coverage=formatting_coverage,
        unsupported_features=unsupported_features,
        unresolved_span_count=unresolved_span_count,
        status=status,
        sample_sufficiency=sample_sufficiency,
    )


def _voice_profile_word_count(package: StyleEvidencePackage) -> int:
    """Count words in resolved voice-profile-eligible spans only."""
    total = 0
    for span in package.authorship.spans:
        if span.is_voice_profile_eligible:
            total += len(_WORD_TOKEN_RE.findall(span.text.lower()))
    return total
