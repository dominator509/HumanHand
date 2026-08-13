"""Unit tests for style vault use cases with a fake vault port."""

from __future__ import annotations

import json
from dataclasses import replace

import pytest

from humanhand.application.style_services import (
    approved_voice_text,
    build_style_evidence_package,
    derive_authorship_spans,
    load_effective_package,
    packages_for_label,
    record_review_decision,
    replay_decisions,
    verify_package_integrity,
)
from humanhand.domain.canonical_document import (
    CanonicalDocument,
    CoverageSummary,
    ImportInspection,
    build_document,
    make_inspection,
)
from humanhand.domain.document_nodes import NodeBuilder, NodeType, SourceLocation
from humanhand.domain.file_identity import derive_identity
from humanhand.domain.import_findings import (
    FindingCategory,
    FindingCode,
    FindingSeverity,
    ImportFinding,
)
from humanhand.domain.import_policy import ImportPolicy
from humanhand.domain.style_authorship import AuthorshipClass
from humanhand.domain.style_serialization import package_from_json
from humanhand.domain.types import DomainError


class FakeVault:
    """In-memory vault port with the same write-once semantics."""

    def __init__(self) -> None:
        self.originals: dict[str, bytes] = {}
        self.packages: dict[str, bytes] = {}
        self.decisions: list[dict[str, object]] = []

    def store_original(self, raw: bytes) -> str:
        import hashlib

        artifact_id = hashlib.sha256(raw).hexdigest()
        existing = self.originals.get(artifact_id)
        if existing is not None and existing != raw:
            raise AssertionError("write-once collision")
        self.originals[artifact_id] = raw
        return artifact_id

    def load_original(self, artifact_id: str) -> bytes:
        return self.originals[artifact_id]

    def store_package(self, package_id: str, package_json: bytes) -> None:
        existing = self.packages.get(package_id)
        if existing is not None and existing != package_json:
            raise AssertionError("write-once collision")
        self.packages[package_id] = package_json

    def load_package(self, package_id: str) -> bytes:
        return self.packages[package_id]

    def list_packages(self) -> tuple[str, ...]:
        return tuple(sorted(self.packages))

    def append_decision(self, decision: dict[str, object]) -> None:
        self.decisions.append(decision)

    def read_decisions(self) -> tuple[dict[str, object], ...]:
        return tuple(self.decisions)


def _style_document(text: str) -> CanonicalDocument:
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


def _inspection(text: str) -> ImportInspection:
    raw = text.encode("utf-8")
    return make_inspection(
        raw=raw,
        identity=derive_identity("sample.txt", raw),
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
        document=_style_document(text),
    )


class TestDeriveAuthorshipSpans:
    def test_paragraphs_start_unknown(self) -> None:
        mapping = derive_authorship_spans(_style_document("Hello world."))
        assert len(mapping.spans) == 1
        assert mapping.spans[0].authorship_class is AuthorshipClass.UNKNOWN
        assert mapping.spans[0].is_resolved is False

    def test_quotations_are_structurally_resolved(self) -> None:
        root = NodeBuilder(node_type=NodeType.DOCUMENT)
        root.add_child(NodeBuilder(node_type=NodeType.PARAGRAPH, text="My prose here."))
        root.add_child(
            NodeBuilder(
                node_type=NodeType.QUOTATION,
                text="A quoted passage from elsewhere.",
            )
        )
        document = build_document(
            root=root,
            lane="style",
            parser_name="text",
            parser_version="1",
            policy=ImportPolicy(lane="style"),
            surface_text="My prose here.\n\nA quoted passage from elsewhere.",
        )
        mapping = derive_authorship_spans(document)
        quotation_spans = [
            span for span in mapping.spans if span.authorship_class is AuthorshipClass.QUOTATION
        ]
        assert len(quotation_spans) == 1
        assert quotation_spans[0].is_resolved is True
        assert quotation_spans[0].decided_by == "structural"

    def test_exact_duplicate_nodes_are_not_double_counted(self) -> None:
        text = "table evidence"
        location = SourceLocation(0, len(text))
        root = NodeBuilder(node_type=NodeType.DOCUMENT)
        root.add_child(
            NodeBuilder(node_type=NodeType.PARAGRAPH, text=text, source_location=location)
        )
        root.add_child(
            NodeBuilder(node_type=NodeType.TABLE_CELL, text=text, source_location=location)
        )
        document = build_document(
            root=root,
            lane="style",
            parser_name="docx",
            parser_version="1",
            policy=ImportPolicy(lane="style"),
            surface_text=text,
        )

        mapping = derive_authorship_spans(document)

        assert len(mapping.spans) == 1
        assert mapping.spans[0].text == text


class TestBuildStyleEvidencePackage:
    def test_builds_and_persists(self) -> None:
        vault = FakeVault()
        inspection = _inspection("My very own writing sample.")
        package = build_style_evidence_package(
            inspection=inspection,
            raw=b"My very own writing sample.",
            vault=vault,
            profile_label="default",
            parser_version="1",
        )
        assert package.package_id.startswith("sty-")
        assert len(package.package_id) == len("sty-") + 24
        assert package.original_artifact.stored is True
        assert vault.originals
        assert package.package_id in vault.packages

    def test_rejects_non_style_lane(self) -> None:
        vault = FakeVault()
        raw = b"x"
        inspection = make_inspection(
            raw=raw,
            identity=derive_identity("s.txt", raw),
            lane="source",
            parser_name="text",
            parser_version="1",
            policy=ImportPolicy(lane="source"),
            findings=(),
            coverage=CoverageSummary(
                adapter="text",
                supported_structures=("paragraph",),
                unsupported_structures=(),
                status="complete",
            ),
            document=_style_document("x"),
        )
        with pytest.raises(DomainError, match="style lane"):
            build_style_evidence_package(
                inspection=inspection,
                raw=raw,
                vault=vault,
                profile_label="default",
                parser_version="1",
            )

    def test_retains_unsupported_coverage_and_error_findings(self) -> None:
        vault = FakeVault()
        inspection = replace(
            _inspection("PDF sample text."),
            coverage=CoverageSummary(
                adapter="pdf",
                supported_structures=("paragraph",),
                unsupported_structures=("reading_order_verification",),
                status="partial",
            ),
            findings=(
                ImportFinding(
                    code=FindingCode.STRUCTURE_READING_ORDER_UNVERIFIED,
                    severity=FindingSeverity.ERROR,
                    category=FindingCategory.STRUCTURE,
                    description="reading order",
                ),
            ),
        )

        package = build_style_evidence_package(
            inspection=inspection,
            raw=b"PDF sample text.",
            vault=vault,
            profile_label="default",
            parser_version="pdf-1",
        )

        assert package.unsupported_features == (
            "reading_order_verification",
            FindingCode.STRUCTURE_READING_ORDER_UNVERIFIED,
        )


class TestReviewFlow:
    def test_review_decision_recorded_and_replayed(self) -> None:
        vault = FakeVault()
        inspection = _inspection("My very own writing sample.")
        package = build_style_evidence_package(
            inspection=inspection,
            raw=b"My very own writing sample.",
            vault=vault,
            profile_label="default",
            parser_version="1",
        )
        span_id = package.authorship.spans[0].span_id
        result = record_review_decision(
            package=package,
            span_id=span_id,
            authorship_class=AuthorshipClass.AUTHENTIC_USER_PROSE,
            vault=vault,
        )
        assert result.package.authorship.is_fully_resolved is True
        assert approved_voice_text(result.package) == "My very own writing sample."
        # Loading from the vault replays the decision log deterministically.
        reloaded = load_effective_package(package_id=package.package_id, vault=vault)
        assert reloaded.authorship.is_fully_resolved is True

    def test_latest_decision_wins(self) -> None:
        vault = FakeVault()
        inspection = _inspection("Sample text for review.")
        package = build_style_evidence_package(
            inspection=inspection,
            raw=b"Sample text for review.",
            vault=vault,
            profile_label="default",
            parser_version="1",
        )
        span_id = package.authorship.spans[0].span_id
        record_review_decision(
            package=package,
            span_id=span_id,
            authorship_class=AuthorshipClass.BOILERPLATE,
            vault=vault,
        )
        record_review_decision(
            package=package,
            span_id=span_id,
            authorship_class=AuthorshipClass.AUTHENTIC_USER_PROSE,
            vault=vault,
        )
        effective = replay_decisions(package, vault.read_decisions())
        assert (
            effective.authorship.by_id(span_id).authorship_class
            is AuthorshipClass.AUTHENTIC_USER_PROSE
        )

    def test_exclude_removes_from_voice_text(self) -> None:
        vault = FakeVault()
        inspection = _inspection("Kept prose sentence here.")
        package = build_style_evidence_package(
            inspection=inspection,
            raw=b"Kept prose sentence here.",
            vault=vault,
            profile_label="default",
            parser_version="1",
        )
        span_id = package.authorship.spans[0].span_id
        record_review_decision(
            package=package,
            span_id=span_id,
            authorship_class=AuthorshipClass.EXCLUDE,
            vault=vault,
        )
        effective = replay_decisions(package, vault.read_decisions())
        assert effective.authorship.spans == ()
        assert len(effective.authorship.excluded) == 1
        assert approved_voice_text(effective) == ""

    def test_unknown_cannot_be_recorded_as_resolved(self) -> None:
        vault = FakeVault()
        package = build_style_evidence_package(
            inspection=_inspection("Unresolved sample."),
            raw=b"Unresolved sample.",
            vault=vault,
            profile_label="default",
            parser_version="1",
        )

        with pytest.raises(DomainError, match="Unknown authorship"):
            record_review_decision(
                package=package,
                span_id=package.authorship.spans[0].span_id,
                authorship_class=AuthorshipClass.UNKNOWN,
                vault=vault,
            )

    def test_replay_rejects_resolved_unknown_decision(self) -> None:
        package = build_style_evidence_package(
            inspection=_inspection("Unresolved sample."),
            raw=b"Unresolved sample.",
            vault=FakeVault(),
            profile_label="default",
            parser_version="1",
        )
        decision: dict[str, object] = {
            "package_id": package.package_id,
            "span_id": package.authorship.spans[0].span_id,
            "authorship_class": AuthorshipClass.UNKNOWN.value,
        }

        with pytest.raises(DomainError, match="cannot be resolved"):
            replay_decisions(package, (decision,))


class TestPackageSelection:
    def test_packages_for_label(self) -> None:
        vault = FakeVault()
        first = _inspection("First sample paragraph.")
        second = _inspection("Second sample paragraph.")
        package_one = build_style_evidence_package(
            inspection=first,
            raw=b"First sample paragraph.",
            vault=vault,
            profile_label="voice-a",
            parser_version="1",
        )
        package_two = build_style_evidence_package(
            inspection=second,
            raw=b"Second sample paragraph.",
            vault=vault,
            profile_label="voice-b",
            parser_version="1",
        )
        assert package_one.package_id != package_two.package_id
        selected = packages_for_label(vault.list_packages(), vault, "voice-a")
        assert len(selected) == 1
        assert selected[0].package_id == package_one.package_id

    def test_round_trip_via_serialization(self) -> None:
        vault = FakeVault()
        inspection = _inspection("Round trip sample text.")
        package = build_style_evidence_package(
            inspection=inspection,
            raw=b"Round trip sample text.",
            vault=vault,
            profile_label="default",
            parser_version="1",
        )
        restored = package_from_json(vault.load_package(package.package_id).decode("utf-8"))
        assert restored.package_id == package.package_id
        assert restored.exact_surface.surface_text == package.exact_surface.surface_text
        from humanhand.domain.style_serialization import package_to_json

        assert package_to_json(restored) == package_to_json(package)

    def test_load_rejects_embedded_package_id_mismatch(self) -> None:
        vault = FakeVault()
        package = build_style_evidence_package(
            inspection=_inspection("Identity-bound sample."),
            raw=b"Identity-bound sample.",
            vault=vault,
            profile_label="default",
            parser_version="1",
        )
        requested_id = "sty-000000000000000000000000"
        vault.packages[requested_id] = vault.packages[package.package_id]

        with pytest.raises(DomainError, match="package id mismatch"):
            load_effective_package(package_id=requested_id, vault=vault)

    def test_integrity_rejects_original_size_mismatch(self) -> None:
        vault = FakeVault()
        package = build_style_evidence_package(
            inspection=_inspection("Size-bound sample."),
            raw=b"Size-bound sample.",
            vault=vault,
            profile_label="default",
            parser_version="1",
        )
        tampered = replace(
            package,
            original_artifact=replace(
                package.original_artifact,
                size_bytes=package.original_artifact.size_bytes + 1,
            ),
        )

        with pytest.raises(DomainError, match="size mismatch"):
            verify_package_integrity(tampered, vault)

    @pytest.mark.parametrize(
        ("mutate", "message"),
        [
            (lambda payload: payload["original_artifact"].update(stored="yes"), "stored"),
            (
                lambda payload: payload["authorship"]["spans"][0]["source_location"].update(
                    start_offset="0"
                ),
                "start_offset",
            ),
            (
                lambda payload: payload.update(unsupported_features={"bad": "shape"}),
                "unsupported_features",
            ),
        ],
    )
    def test_package_json_rejects_type_coercion(self, mutate: object, message: str) -> None:
        vault = FakeVault()
        package = build_style_evidence_package(
            inspection=_inspection("Strict JSON sample."),
            raw=b"Strict JSON sample.",
            vault=vault,
            profile_label="default",
            parser_version="1",
        )
        payload = json.loads(vault.packages[package.package_id])
        assert callable(mutate)
        mutate(payload)

        with pytest.raises(DomainError, match=message):
            package_from_json(json.dumps(payload))
