"""Integration tests for the Style Fidelity Vault round trip (EP-014).

Every test uses the REAL file-backed ``StyleVault`` in a pytest
``tmp_path`` plus the real application and domain modules. The profile
and comparison modules (``style_profiles``, ``style_compare``) are EP-014
parallel work; when they are absent at run time the profile-dependent
classes skip with an explicit report instead of failing at import time.
"""

from __future__ import annotations

import dataclasses
from pathlib import Path
from typing import Any

import pytest

from humanhand.application.style_services import (
    build_style_evidence_package,
    load_effective_package,
    record_review_decision,
)
from humanhand.domain.canonical_document import (
    CoverageSummary,
    ImportInspection,
    build_document,
    make_inspection,
)
from humanhand.domain.document_nodes import NodeBuilder, NodeType
from humanhand.domain.file_identity import derive_identity
from humanhand.domain.import_policy import ImportPolicy
from humanhand.domain.style_artifacts import StyleEvidencePackage
from humanhand.domain.style_authorship import AuthorshipClass
from humanhand.domain.style_serialization import package_to_json
from humanhand.infra.stores.style_vault import StyleVault

# Invented prose for the style-lane samples (no user text).
_PARAGRAPHS = (
    "The morning light fell across the desk and the kettle began to hum softly.",
    "She opened the notebook and wrote down the first thought that came to mind.",
    "By evening the pages were full and the day felt complete.",
)
_SURFACE_TEXT = "\n\n".join(_PARAGRAPHS)
_RAW = _SURFACE_TEXT.encode("utf-8")


@pytest.fixture
def vault(tmp_path: Path) -> StyleVault:
    return StyleVault(tmp_path / "vault")


def _style_inspection() -> ImportInspection:
    """Build a real style-lane import inspection over three paragraphs."""
    root = NodeBuilder(node_type=NodeType.DOCUMENT)
    for paragraph in _PARAGRAPHS:
        root.add_child(NodeBuilder(node_type=NodeType.PARAGRAPH, text=paragraph))
    document = build_document(
        root=root,
        lane="style",
        parser_name="text",
        parser_version="1",
        policy=ImportPolicy(lane="style"),
        surface_text=_SURFACE_TEXT,
    )
    return make_inspection(
        raw=_RAW,
        identity=derive_identity("sample.txt", _RAW),
        lane="style",
        parser_name="text",
        parser_version="1",
        policy=ImportPolicy(lane="style"),
        findings=(),
        coverage=CoverageSummary(
            adapter="text",
            supported_structures=("paragraph",),
            unsupported_structures=(),
            status="complete",
        ),
        document=document,
    )


def _build_package(vault: StyleVault) -> StyleEvidencePackage:
    """Build and persist one style evidence package in the real vault."""
    return build_style_evidence_package(
        inspection=_style_inspection(),
        raw=_RAW,
        vault=vault,
        profile_label="voice-a",
        parser_version="1",
    )


def _approve_all_spans(package: StyleEvidencePackage, vault: StyleVault) -> StyleEvidencePackage:
    """Record AUTHENTIC_USER_PROSE for every span; return the effective package."""
    for span in package.authorship.spans:
        record_review_decision(
            package=package,
            span_id=span.span_id,
            authorship_class=AuthorshipClass.AUTHENTIC_USER_PROSE,
            vault=vault,
        )
    return load_effective_package(package_id=package.package_id, vault=vault)


def _profile_tooling() -> tuple[Any, Any]:
    """Return (style_profiles, style_compare) modules or skip with a report."""
    try:
        import humanhand.domain.style_compare as compare_mod
        import humanhand.domain.style_profiles as profiles_mod
    except ModuleNotFoundError as exc:
        pytest.skip(f"EP-014 profile modules not merged yet: {exc}")
    return profiles_mod, compare_mod


@pytest.mark.importers
class TestPackageRoundTrip:
    def test_build_store_load_serialization_round_trip(self, vault: StyleVault) -> None:
        package = _build_package(vault)
        loaded = load_effective_package(package_id=package.package_id, vault=vault)
        assert package_to_json(loaded) == package_to_json(package)

    def test_vault_holds_exactly_one_original_and_one_package(self, vault: StyleVault) -> None:
        _build_package(vault)
        assert len(list((vault.root / "originals").glob("*.bin"))) == 1
        assert len(list((vault.root / "packages").glob("*.json"))) == 1

    def test_restoring_same_package_id_is_idempotent(self, vault: StyleVault) -> None:
        package = _build_package(vault)
        payload = package_to_json(package).encode("utf-8")
        vault.store_package(package.package_id, payload)
        vault.store_package(package.package_id, payload)
        assert len(list((vault.root / "packages").glob("*.json"))) == 1

    def test_same_original_bytes_return_same_artifact_id(self, vault: StyleVault) -> None:
        package = _build_package(vault)
        first = vault.store_original(_RAW)
        second = vault.store_original(_RAW)
        assert first == second
        assert first == package.original_artifact.artifact_id
        assert len(list((vault.root / "originals").glob("*.bin"))) == 1

    def test_rebuilding_same_package_is_idempotent(self, vault: StyleVault) -> None:
        first = _build_package(vault)
        second = _build_package(vault)
        assert first.package_id == second.package_id
        assert first.original_artifact.artifact_id == second.original_artifact.artifact_id
        assert len(list((vault.root / "originals").glob("*.bin"))) == 1
        assert len(list((vault.root / "packages").glob("*.json"))) == 1


@pytest.mark.importers
class TestDecisionPersistence:
    def test_decision_recorded_replayed_and_latest_wins(self, vault: StyleVault) -> None:
        package = _build_package(vault)
        span_id = package.authorship.spans[0].span_id
        record_review_decision(
            package=package,
            span_id=span_id,
            authorship_class=AuthorshipClass.AUTHENTIC_USER_PROSE,
            vault=vault,
        )
        decision_lines = (vault.root / "decisions.jsonl").read_text(encoding="utf-8").splitlines()
        assert len(decision_lines) == 1
        effective = load_effective_package(package_id=package.package_id, vault=vault)
        span = effective.authorship.by_id(span_id)
        assert span.authorship_class is AuthorshipClass.AUTHENTIC_USER_PROSE
        assert span.is_resolved is True
        assert span.decided_by == "cli"
        record_review_decision(
            package=package,
            span_id=span_id,
            authorship_class=AuthorshipClass.USER_REVISION,
            vault=vault,
        )
        assert len((vault.root / "decisions.jsonl").read_text(encoding="utf-8").splitlines()) == 2
        effective = load_effective_package(package_id=package.package_id, vault=vault)
        assert effective.authorship.by_id(span_id).authorship_class is AuthorshipClass.USER_REVISION

    def test_exclude_shrinks_spans_and_records_reason(self, vault: StyleVault) -> None:
        package = _build_package(vault)
        span_id = package.authorship.spans[0].span_id
        record_review_decision(
            package=package,
            span_id=span_id,
            authorship_class=AuthorshipClass.EXCLUDE,
            vault=vault,
        )
        effective = load_effective_package(package_id=package.package_id, vault=vault)
        assert len(effective.authorship.spans) == 2
        assert [span.span_id for span in effective.authorship.spans] == ["a2", "a3"]
        assert len(effective.authorship.excluded) == 1
        excluded = effective.authorship.excluded[0]
        assert excluded.span_id == span_id
        assert excluded.reason == "excluded by review"


@pytest.mark.importers
class TestProfileRoundTrip:
    def test_profile_json_round_trip_is_lossless_and_stable(self, vault: StyleVault) -> None:
        profiles_mod, _ = _profile_tooling()
        package = _approve_all_spans(_build_package(vault), vault)
        profile = profiles_mod.build_profile(
            profile_id="voice-a",
            packages=(package,),
            min_words_for_sufficiency=1,
        )
        serialized = profiles_mod.profile_to_json(profile)
        restored = profiles_mod.profile_from_json(serialized)
        assert isinstance(restored, profiles_mod.StyleEvidenceProfile)
        assert restored == profile
        assert profiles_mod.profile_to_json(restored) == serialized

    def test_compare_profile_reports_confidences_without_authorship_field(
        self, vault: StyleVault
    ) -> None:
        profiles_mod, compare_mod = _profile_tooling()
        package = _approve_all_spans(_build_package(vault), vault)
        profile = profiles_mod.build_profile(
            profile_id="voice-a",
            packages=(package,),
            min_words_for_sufficiency=1,
        )
        inspection = _style_inspection()
        assert inspection.document is not None
        report = compare_mod.compare_profile(profile, inspection.document)
        assert 0.0 <= report.confidence <= 1.0
        assert set(report.metric_distances) == {
            "sentence_mean",
            "sentence_stdev",
            "type_token_ratio",
            "function_word_ratio",
            "contraction_frequency",
            "punctuation_per_100_chars",
            "question_frequency",
        }
        for distance in report.metric_distances.values():
            assert 0.0 <= distance <= 1.0
        field_names = [
            field.name for field in dataclasses.fields(compare_mod.StyleComparisonReport)
        ]
        assert "authorship" not in field_names


@pytest.mark.importers
class TestSampleSufficiency:
    def test_insufficient_sample_reports_partial_coverage(self, vault: StyleVault) -> None:
        profiles_mod, _ = _profile_tooling()
        package = _approve_all_spans(_build_package(vault), vault)
        profile = profiles_mod.build_profile(
            profile_id="voice-a",
            packages=(package,),
            min_words_for_sufficiency=1_000_000,
        )
        # Every span is resolved and the approved sample is far below one
        # million words, so build_coverage_report yields "partial" (with
        # unresolved spans it would yield "human_review_required" instead).
        assert profile.coverage.status == "partial"
        assert profile.coverage.sample_sufficiency == "insufficient"
        assert profile.status == "partial"


@pytest.mark.importers
class TestDeterminism:
    def test_two_profile_builds_serialize_identically(self, vault: StyleVault) -> None:
        profiles_mod, _ = _profile_tooling()
        package = _approve_all_spans(_build_package(vault), vault)
        first = profiles_mod.build_profile(
            profile_id="voice-a",
            packages=(package,),
            min_words_for_sufficiency=1,
        )
        second = profiles_mod.build_profile(
            profile_id="voice-a",
            packages=(package,),
            min_words_for_sufficiency=1,
        )
        assert profiles_mod.profile_to_json(first) == profiles_mod.profile_to_json(second)
