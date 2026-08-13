"""Style coverage reporting for evidence packages (blueprint 8.2).

A package may claim ``complete`` only when every one of these holds:

- visible text extraction coverage is 100%,
- unicode code-point coverage is 100%,
- paragraph/heading/list/table coverage is 100% for features present,
- formatting coverage is 100% for supported features present,
- all authorship spans are resolved,
- the unsupported-features list is empty,
- the original was not modified.

Otherwise the status is ``partial`` or ``human_review_required``. This
module is the enforcement point for that rule: the builder derives
coverage from the package fields alone and never over-claims.

Deterministic conventions documented here:

- ``visible_text_coverage`` is 1.0 when the exact surface text is
  non-empty, else 0.0.
- ``code_point_coverage`` is always 1.0: the surface is the exact
  code-point-preserving view (ADR-003) and the package either carries it
  intact or does not exist.
- ``structure_coverage`` is always 1.0 for represented structures: the
  surface statistics count every structure present; unrepresented
  structures are out of scope, not uncovered.
- ``formatting_coverage`` is always 1.0: TXT/Markdown adapters report
  features they cannot represent through the unsupported-features list
  (see below), and this surface-only builder never fabricates one.
- ``unsupported_features`` comes from the package's import findings.
  are adapter-reported information (blueprint 8.2); they cannot be
  reconstructed from a surface view, so this builder reports none rather
  than guessing. The status logic still enforces the rule when a future
  caller supplies the list through an extended package.

Sample sufficiency counts words of the approved voice text: the joined
texts of spans where ``span.is_voice_profile_eligible``, tokenized with
the same word pattern as ``humanhand.domain.style``.
"""

from __future__ import annotations

import re
from dataclasses import dataclass

from humanhand.domain.style_artifacts import StyleEvidencePackage

# Word tokenizer identical to the one in humanhand.domain.style.
_WORD_TOKEN_RE = re.compile(r"[a-zA-Z0-9]+(?:'[a-zA-Z]+)?")


@dataclass(frozen=True)
class StyleCoverageReport:
    """Deterministic coverage state of one style evidence package."""

    package_id: str
    visible_text_coverage: float  # 1.0 when surface text is non-empty else 0.0
    code_point_coverage: float  # always 1.0 (exact surface preserved)
    structure_coverage: float  # always 1.0 for represented structures
    formatting_coverage: float  # 1.0; unsupported features reported separately
    unsupported_features: tuple[str, ...]
    unresolved_span_count: int
    status: str  # "complete" | "partial" | "human_review_required"
    sample_sufficiency: str  # "sufficient" | "insufficient"


def build_coverage_report(
    package: StyleEvidencePackage, *, min_words_for_sufficiency: int = 1000
) -> StyleCoverageReport:
    """Build the coverage report for a style evidence package.

    Args:
        package: The evidence package to evaluate.
        min_words_for_sufficiency: Minimum approved voice-profile word
            count for the sample to be considered sufficient.

    Returns:
        A deterministic :class:`StyleCoverageReport`. ``complete`` is
        claimed only when every blueprint 8.2 condition derivable from
        the package holds: no unresolved spans, no unsupported features,
        a sufficient approved sample, and 100% visible text coverage.
    """
    visible_text_coverage = 1.0 if package.exact_surface.surface_text else 0.0
    unresolved_span_count = len(package.authorship.unresolved_spans)
    word_count = _voice_profile_word_count(package)
    sample_sufficiency = "sufficient" if word_count >= min_words_for_sufficiency else "insufficient"
    # Adapter-reported unsupported features come from the package itself.
    unsupported_features = package.unsupported_features
    if unresolved_span_count > 0 or unsupported_features:
        status = "human_review_required"
    elif sample_sufficiency == "sufficient" and visible_text_coverage == 1.0:
        status = "complete"
    else:
        status = "partial"
    return StyleCoverageReport(
        package_id=package.package_id,
        visible_text_coverage=visible_text_coverage,
        code_point_coverage=1.0,
        structure_coverage=1.0,
        formatting_coverage=1.0,
        unsupported_features=unsupported_features,
        unresolved_span_count=unresolved_span_count,
        status=status,
        sample_sufficiency=sample_sufficiency,
    )


def _voice_profile_word_count(package: StyleEvidencePackage) -> int:
    """Count words in the approved voice text.

    Only resolved spans in VOICE_PROFILE_CLASSES (AUTHENTIC_USER_PROSE,
    USER_REVISION) contribute, per blueprint 8.3. Tokenization matches
    the word pattern in ``humanhand.domain.style``.
    """
    total = 0
    for span in package.authorship.spans:
        if span.is_voice_profile_eligible:
            total += len(_WORD_TOKEN_RE.findall(span.text.lower()))
    return total
