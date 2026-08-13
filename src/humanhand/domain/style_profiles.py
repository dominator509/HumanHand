"""Style evidence profiles — the aggregated voice of one profile label (EP-014).

A profile joins the approved voice text of every stored package for one
profile label (resolved AUTHENTIC_USER_PROSE / USER_REVISION spans only,
blueprint 8.3) and derives deterministic metrics, hard invariants, soft
tendencies, and a fail-closed coverage summary. Profiles never infer
authorship (SPEC-011) and never claim ``complete`` without resolved
authorship, full coverage, and a sufficient approved sample.

The approved voice text itself is carried by the profile so that the
profile-side punctuation denominator and serialized payload stay
self-contained. The voice text joins package voice texts through
``humanhand.domain.style_authorship.approved_voice_text`` — the single
voice-span filter defined by the vault use cases.

Serialization mirrors :mod:`humanhand.domain.style_serialization`: stable
JSON via :func:`humanhand.domain.document_serialization.dumps_stable`,
with strict per-field validation on load. ``voice_text`` is part of the
payload because the profile JSON is an evidence record (the package JSON
already carries surface and span texts); style text never enters logs or
caches.

Coverage aggregation is fail-closed and conservative: the aggregated
report is at most as good as the worst package. Sufficiency is then
reconciled against the true joined voice word count, which can exceed
every per-package sample.
"""

from __future__ import annotations

import dataclasses
import json
import typing
from collections.abc import Sequence
from dataclasses import dataclass, replace
from enum import StrEnum
from typing import Any

from humanhand.domain.document_serialization import dumps_stable
from humanhand.domain.style_artifacts import StyleEvidencePackage
from humanhand.domain.style_authorship import approved_voice_text
from humanhand.domain.style_coverage import (
    StyleCoverageReport,
    build_coverage_report,
)
from humanhand.domain.style_invariants import (
    StyleInvariant,
    StyleTendency,
    extract_invariants,
    extract_tendencies,
)
from humanhand.domain.style_metrics import (
    Distribution,
    StyleMetricsBundle,
    compute_all_metrics,
)
from humanhand.domain.types import DomainError

_SCHEMA_NAME = "style-evidence-profile"
STYLE_PROFILE_SCHEMA_VERSION = 1

_DISTRIBUTION_KEYS = (
    "count",
    "minimum",
    "p10",
    "p25",
    "median",
    "p75",
    "p90",
    "maximum",
    "mean",
    "stdev",
)


@dataclass(frozen=True)
class StyleEvidenceProfile:
    """Deterministic aggregated voice profile of one profile label."""

    schema_version: int
    profile_id: str
    profile_label: str
    package_ids: tuple[str, ...]
    voice_text: str
    sample_word_count: int
    min_words_for_sufficiency: int
    metrics: StyleMetricsBundle
    hard_invariants: tuple[StyleInvariant, ...]
    soft_tendencies: tuple[StyleTendency, ...]
    coverage: StyleCoverageReport
    status: str  # mirrors coverage.status: complete | partial | human_review_required


def build_profile(
    *,
    profile_id: str,
    packages: tuple[StyleEvidencePackage, ...],
    min_words_for_sufficiency: int = 1000,
) -> StyleEvidenceProfile:
    """Build the deterministic style evidence profile for a profile label.

    Args:
        profile_id: The profile label, as used at import time.
        packages: Every stored package carrying this label, with the
            effective review decisions already replayed.
        min_words_for_sufficiency: Minimum approved voice word count for
            the sample to be considered sufficient.

    Raises:
        DomainError: If no packages are supplied. A profile built from
            zero evidence would be a false ``complete`` claim.
    """
    if not packages:
        raise DomainError("Style profile requires at least one package")
    voice_parts = [approved_voice_text(package.authorship) for package in packages]
    voice_text = "\n\n".join(part for part in voice_parts if part)
    metrics = compute_all_metrics(voice_text)
    reports = tuple(
        build_coverage_report(package, min_words_for_sufficiency=min_words_for_sufficiency)
        for package in packages
    )
    coverage = _reconcile_sufficiency(
        aggregate_coverage(
            tuple(package.package_id for package in packages),
            reports,
            profile_id=profile_id,
        ),
        sample_word_count=metrics.word_count,
        min_words_for_sufficiency=min_words_for_sufficiency,
    )
    return StyleEvidenceProfile(
        schema_version=STYLE_PROFILE_SCHEMA_VERSION,
        profile_id=profile_id,
        profile_label=profile_id,
        package_ids=tuple(package.package_id for package in packages),
        voice_text=voice_text,
        sample_word_count=metrics.word_count,
        min_words_for_sufficiency=min_words_for_sufficiency,
        metrics=metrics,
        hard_invariants=extract_invariants(voice_text, metrics),
        soft_tendencies=extract_tendencies(voice_text, metrics),
        coverage=coverage,
        status=coverage.status,
    )


def aggregate_coverage(
    package_ids: tuple[str, ...],
    reports: Sequence[StyleCoverageReport],
    *,
    profile_id: str,
) -> StyleCoverageReport:
    """Aggregate per-package coverage reports fail-closed.

    The aggregated report is at most as good as the worst package:
    unresolved spans and unsupported features are summed and unioned, every
    coverage ratio is the minimum across packages, and the sample is
    ``insufficient`` when any package reports its own sample insufficient.
    Sufficiency is reconciled against the true joined voice word count by
    :func:`build_profile`, which can exceed every single-package sample.

    Raises:
        DomainError: If the package id order does not match ``reports``.
    """
    report_ids = [report.package_id for report in reports]
    if report_ids != list(package_ids):
        raise DomainError("Coverage package ids do not match the package set")
    if not reports:
        return StyleCoverageReport(
            package_id=profile_id,
            visible_text_coverage=0.0,
            code_point_coverage=1.0,
            structure_coverage=1.0,
            formatting_coverage=1.0,
            unsupported_features=(),
            unresolved_span_count=0,
            status="human_review_required",
            sample_sufficiency="insufficient",
        )
    visible_text_coverage = min(report.visible_text_coverage for report in reports)
    code_point_coverage = min(report.code_point_coverage for report in reports)
    structure_coverage = min(report.structure_coverage for report in reports)
    formatting_coverage = min(report.formatting_coverage for report in reports)
    unresolved_span_count = sum(report.unresolved_span_count for report in reports)
    unsupported: list[str] = []
    for report in reports:
        for feature in report.unsupported_features:
            if feature not in unsupported:
                unsupported.append(feature)
    if unresolved_span_count > 0 or unsupported:
        status = "human_review_required"
    elif any(report.status == "partial" for report in reports):
        status = "partial"
    elif all(report.status == "complete" for report in reports):
        status = "complete"
    else:
        status = "human_review_required"
    sample_sufficiency = (
        "insufficient"
        if any(report.sample_sufficiency == "insufficient" for report in reports)
        else "sufficient"
    )
    return StyleCoverageReport(
        package_id=profile_id,
        visible_text_coverage=visible_text_coverage,
        code_point_coverage=code_point_coverage,
        structure_coverage=structure_coverage,
        formatting_coverage=formatting_coverage,
        unsupported_features=tuple(unsupported),
        unresolved_span_count=unresolved_span_count,
        status=status,
        sample_sufficiency=sample_sufficiency,
    )


def _reconcile_sufficiency(
    coverage: StyleCoverageReport,
    *,
    sample_word_count: int,
    min_words_for_sufficiency: int,
) -> StyleCoverageReport:
    """Align coverage sufficiency with the true joined voice word count.

    Per-package reports are conservative: a package of 600 words reports
    its own sample insufficient even though two such packages together
    are sufficient. When the true count disagrees with the aggregated
    report, the report is corrected and the status recomputed from the
    aggregate fields (never over-claiming ``complete``).
    """
    sufficiency = "sufficient" if sample_word_count >= min_words_for_sufficiency else "insufficient"
    if coverage.sample_sufficiency == sufficiency:
        return coverage
    if sufficiency == "insufficient":
        status = "partial" if coverage.status == "complete" else coverage.status
        return replace(coverage, sample_sufficiency="insufficient", status=status)
    if coverage.unresolved_span_count > 0 or coverage.unsupported_features:
        status = "human_review_required"
    elif coverage.visible_text_coverage == 1.0:
        status = "complete"
    else:
        status = "partial"
    return replace(coverage, sample_sufficiency="sufficient", status=status)


def profile_to_payload(profile: StyleEvidenceProfile) -> dict[str, object]:
    """Render the profile as a stable, lossless JSON-ready payload."""
    return {
        "schema": _SCHEMA_NAME,
        "schema_version": profile.schema_version,
        "profile_id": profile.profile_id,
        "profile_label": profile.profile_label,
        "package_ids": list(profile.package_ids),
        "voice_text": profile.voice_text,
        "sample_word_count": profile.sample_word_count,
        "min_words_for_sufficiency": profile.min_words_for_sufficiency,
        "metrics": _render_value(profile.metrics),
        "hard_invariants": [_render_value(invariant) for invariant in profile.hard_invariants],
        "soft_tendencies": [_render_value(tendency) for tendency in profile.soft_tendencies],
        "coverage": _render_value(profile.coverage),
        "status": profile.status,
    }


def profile_to_json(profile: StyleEvidenceProfile) -> str:
    """Render the profile as stable JSON with a trailing newline."""
    return dumps_stable(profile_to_payload(profile))


def profile_from_json(text: str) -> StyleEvidenceProfile:
    """Load a profile from its stable JSON, validating every field.

    Raises:
        DomainError: If the payload is not valid profile JSON or any
            field, nested field, or cross-field invariant is invalid.
    """
    try:
        payload = json.loads(text)
    except json.JSONDecodeError as exc:
        raise DomainError("Invalid style profile JSON: not valid JSON") from exc
    if not isinstance(payload, dict):
        raise DomainError("Invalid style profile JSON: top level must be an object")
    _expect(payload, "schema", _SCHEMA_NAME, "schema")
    _expect(payload, "schema_version", STYLE_PROFILE_SCHEMA_VERSION, "schema_version")
    # "schema" is a pure discriminator; "schema_version" is also a real
    # dataclass field, so only the discriminator is stripped before the
    # strict rebuild.
    rebuild_payload = dict(payload)
    rebuild_payload.pop("schema", None)
    rebuilt = _rebuild_value(StyleEvidenceProfile, rebuild_payload)
    if not isinstance(rebuilt, StyleEvidenceProfile):
        raise DomainError("Invalid style profile JSON: profile rebuild failed")
    profile = rebuilt
    if profile.status != profile.coverage.status:
        raise DomainError("Invalid style profile JSON: status does not match coverage status")
    if (
        profile.coverage.sample_sufficiency == "sufficient"
        and profile.sample_word_count < profile.min_words_for_sufficiency
    ):
        raise DomainError(
            "Invalid style profile JSON: sample_sufficiency contradicts sample_word_count"
        )
    if profile.coverage.package_id != profile.profile_id:
        raise DomainError(
            "Invalid style profile JSON: coverage package_id does not match profile_id"
        )
    if profile.sample_word_count != profile.metrics.word_count:
        raise DomainError(
            "Invalid style profile JSON: sample_word_count does not match metrics word_count"
        )
    return profile


def _expect(payload: dict[str, object], key: str, expected: object, what: str) -> None:
    """Require ``payload[key] == expected`` or fail closed."""
    if payload.get(key) != expected:
        raise DomainError(f"Invalid style profile JSON: {what} must be {expected!r}")


def _render_value(value: Any) -> Any:
    """Render one profile value as JSON-ready data (deterministic)."""
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
    if isinstance(value, Distribution):
        return {
            "count": value.count,
            "minimum": value.minimum,
            "p10": value.p10,
            "p25": value.p25,
            "median": value.median,
            "p75": value.p75,
            "p90": value.p90,
            "maximum": value.maximum,
            "mean": value.mean,
            "stdev": value.stdev,
        }
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
    raise DomainError(f"Cannot render style profile field: {type(value).__name__}")


def _rebuild_value(expected: Any, raw: Any) -> Any:
    """Rebuild one profile field from JSON data, validating strictly.

    ``expected`` is the annotated type of the field (a class or a typing
    construct such as ``tuple[str, ...]``). ``raw`` is the JSON-decoded
    value. Mismatches raise :class:`DomainError`; nothing is coerced
    silently.
    """
    if raw is None:
        raise DomainError("Invalid style profile JSON: null value")
    if expected is Distribution:
        return _rebuild_distribution(raw)
    origin = typing.get_origin(expected)
    if origin is tuple:
        if not isinstance(raw, list):
            raise DomainError("Invalid style profile JSON: expected a list")
        args = typing.get_args(expected)
        item_type = args[0] if args else Any
        return tuple(_rebuild_value(item_type, item) for item in raw)
    if origin is dict:
        if not isinstance(raw, dict):
            raise DomainError("Invalid style profile JSON: expected an object")
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
                f"Invalid style profile JSON: {expected.__name__} must be a known value"
            ) from exc
    if isinstance(expected, type) and issubclass(expected, bool):
        if not isinstance(raw, bool):
            raise DomainError("Invalid style profile JSON: expected a boolean")
        return raw
    if isinstance(expected, type) and issubclass(expected, int):
        if not isinstance(raw, int) or isinstance(raw, bool):
            raise DomainError("Invalid style profile JSON: expected an integer")
        return raw
    if isinstance(expected, type) and issubclass(expected, float):
        if not isinstance(raw, (int, float)) or isinstance(raw, bool):
            raise DomainError("Invalid style profile JSON: expected a number")
        return float(raw)
    if isinstance(expected, type) and issubclass(expected, str):
        if not isinstance(raw, str):
            raise DomainError("Invalid style profile JSON: expected a string")
        return raw
    raise DomainError(f"Invalid style profile JSON: unsupported field type {expected!r}")


def _rebuild_dataclass(cls: type[Any], raw: Any) -> Any:
    """Rebuild a frozen dataclass value from a JSON object."""
    if not isinstance(raw, dict):
        raise DomainError(f"Invalid style profile JSON: {cls.__name__} must be an object")
    hints = typing.get_type_hints(cls)
    known = {field.name for field in dataclasses.fields(cls)}
    unknown = set(raw) - known
    if unknown:
        raise DomainError(
            f"Invalid style profile JSON: unknown {cls.__name__} fields "
            f"{', '.join(sorted(unknown))}"
        )
    values: dict[str, Any] = {}
    for field in dataclasses.fields(cls):
        if field.name not in raw:
            raise DomainError(f"Invalid style profile JSON: missing {cls.__name__}.{field.name}")
        raw_value = raw[field.name]
        if raw_value is None:
            raise DomainError(f"Invalid style profile JSON: {cls.__name__}.{field.name} is null")
        values[field.name] = _rebuild_value(hints[field.name], raw_value)
    return cls(**values)


def _rebuild_distribution(raw: Any) -> Distribution:
    """Rebuild a Distribution from its documented ten keys."""
    if not isinstance(raw, dict):
        raise DomainError("Invalid style profile JSON: Distribution must be an object")
    for key in _DISTRIBUTION_KEYS:
        if key not in raw:
            raise DomainError(f"Invalid style profile JSON: missing Distribution.{key}")
    return Distribution(
        count=_rebuild_value(int, raw["count"]),
        minimum=_rebuild_value(float, raw["minimum"]),
        p10=_rebuild_value(float, raw["p10"]),
        p25=_rebuild_value(float, raw["p25"]),
        median=_rebuild_value(float, raw["median"]),
        p75=_rebuild_value(float, raw["p75"]),
        p90=_rebuild_value(float, raw["p90"]),
        maximum=_rebuild_value(float, raw["maximum"]),
        mean=_rebuild_value(float, raw["mean"]),
        stdev=_rebuild_value(float, raw["stdev"]),
    )
