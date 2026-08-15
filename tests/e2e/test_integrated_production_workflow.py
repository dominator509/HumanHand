"""Golden end-to-end test for the integrated EP-019 production workflow."""

from __future__ import annotations

from pathlib import Path

import pytest

from humanhand.application.import_services import (
    build_import_policy,
    import_source_package,
    import_style_package,
)
from humanhand.application.integrated_workflow import (
    build_integrated_context,
    finalize_reviewed_revision,
    ingest_source_package,
    load_document_state,
    propose_integrated_lexical_changes,
)
from humanhand.application.style_services import (
    build_style_evidence_package,
    load_effective_package,
    record_review_decision,
)
from humanhand.domain.artifact_findings import ArtifactAuditStatus
from humanhand.domain.canonical_document import CanonicalDocument
from humanhand.domain.document_nodes import NodeType
from humanhand.domain.export_contract import ExportFormat, ExportRequest
from humanhand.domain.lexical_review import ReviewDecision, build_review_journal
from humanhand.domain.project import new_project_state
from humanhand.domain.public_document import build_public_document
from humanhand.domain.style_authorship import AuthorshipClass
from humanhand.domain.style_profiles import build_profile
from humanhand.infra.auditors import audit_artifact
from humanhand.infra.exporters import get_exporter
from humanhand.infra.files import file_size, read_bytes, read_head_bytes
from humanhand.infra.importers.pipeline import SandboxedImportInspector
from humanhand.infra.lexicons.lexicon_loader import load_bundled_rules
from humanhand.infra.stores.integrated_project_store import IntegratedProjectStore
from humanhand.infra.stores.style_vault import StyleVault


class _Reader:
    def size_bytes(self, path: str | Path) -> int:
        return file_size(path)

    def read_head(self, path: str | Path, max_bytes: int) -> bytes:
        return read_head_bytes(path, max_bytes)

    def read_bytes(self, path: str | Path) -> bytes:
        return read_bytes(path)


def _import_source(path: Path):  # type: ignore[no-untyped-def]
    policy = build_import_policy(
        lane="source",
        max_bytes=4_000_000,
        max_expanded_bytes=16_000_000,
        max_nodes=50_000,
        timeout_seconds=30.0,
    )
    result = import_source_package(
        path=path,
        policy=policy,
        reader=_Reader(),
        inspector=SandboxedImportInspector(),
    )
    assert result.package is not None
    return result.package


def _complete_style_profile(style_path: Path, vault_path: Path):  # type: ignore[no-untyped-def]
    policy = build_import_policy(
        lane="style",
        max_bytes=4_000_000,
        max_expanded_bytes=16_000_000,
        max_nodes=50_000,
        timeout_seconds=30.0,
    )
    raw = style_path.read_bytes()
    imported = import_style_package(
        path=style_path,
        policy=policy,
        reader=_Reader(),
        inspector=SandboxedImportInspector(),
        raw_override=raw,
    )
    assert imported.inspection.document is not None
    vault = StyleVault(vault_path)
    package = build_style_evidence_package(
        inspection=imported.inspection,
        raw=raw,
        vault=vault,
        profile_label="human-sample",
        parser_version="golden-test",
    )
    for span in package.authorship.unresolved_spans:
        record_review_decision(
            package=package,
            span_id=span.span_id,
            authorship_class=AuthorshipClass.AUTHENTIC_USER_PROSE,
            vault=vault,
            decided_by="golden-test-human",
        )
    effective = load_effective_package(package_id=package.package_id, vault=vault)
    profile = build_profile(profile_id="human-sample", packages=(effective,))
    assert profile.status == "complete"
    return profile


def _public_sections(document: CanonicalDocument) -> tuple[str, ...]:
    sections = tuple(
        node.text for node in document.nodes if node.node_type is NodeType.PARAGRAPH and node.text
    )
    return sections or tuple(part for part in document.surface_text.split("\n\n") if part)


@pytest.mark.importers
def test_full_integrated_pre_slm_workflow(tmp_path: Path) -> None:
    source_path = tmp_path / "source.txt"
    source_path.write_text(
        "We utilize the available evidence on August 30, 2026.",
        encoding="utf-8",
        newline="\n",
    )
    # More than 1,000 human-approved words, using mechanics compatible with
    # the source/final output so the style hard-invariant gate is meaningful.
    style_sentence = "We use the available evidence carefully and explain the result directly."
    style_path = tmp_path / "style.txt"
    style_path.write_text(
        " ".join(style_sentence for _ in range(120)),
        encoding="utf-8",
        newline="\n",
    )

    profile = _complete_style_profile(style_path, tmp_path / "style-vault")
    package = _import_source(source_path)
    project_root = tmp_path / "project"
    project = new_project_state(name="Golden Project", root=str(project_root))
    store = IntegratedProjectStore(project_root)
    try:
        ingest = ingest_source_package(
            package=package,
            project=project,
            store=store,
            style_profile_id=profile.profile_id,
        )
        assert ingest.revision_id

        initial = load_document_state(
            project_id=project.project_id,
            document_id=ingest.document_id,
            store=store,
        )
        block_id = next(
            node.node_id for node in initial.document.nodes if node.node_type is NodeType.PARAGRAPH
        )
        capsule = build_integrated_context(
            state=initial,
            block_id=block_id,
            profile=profile,
        )
        assert initial.content.style_profile_id == profile.profile_id
        assert capsule.style_hard_invariants
        assert capsule.style_soft_tendencies

        proposal = propose_integrated_lexical_changes(
            state=initial,
            ruleset=load_bundled_rules(),
        )
        change = next(item for item in proposal.changes if item.source_surface.lower() == "utilize")
        journal = build_review_journal(
            proposal.run_id,
            (ReviewDecision(change.change_id, "accept"),),
        )
        finalized = finalize_reviewed_revision(
            state=initial,
            proposal=proposal,
            journal=journal,
            store=store,
            profile=profile,
        )
        assert finalized.accepted_change_count == 1

        accepted = load_document_state(
            project_id=project.project_id,
            document_id=ingest.document_id,
            store=store,
        )
        assert accepted.revision.revision_id == finalized.revision_id
        assert "utilize" not in accepted.content.accepted_text.lower()
        assert "use the available evidence" in accepted.content.accepted_text.lower()
        assert "August 30, 2026" in accepted.content.accepted_text
    finally:
        store.close()

    public_document = build_public_document(
        title="Golden Project",
        sections=_public_sections(accepted.document),
        claims=(),
    )
    suffixes = {
        ExportFormat.TXT: ".txt",
        ExportFormat.MARKDOWN: ".md",
        ExportFormat.DOCX: ".docx",
        ExportFormat.PDF: ".pdf",
    }
    for export_format, suffix in suffixes.items():
        output = tmp_path / f"final{suffix}"
        result = get_exporter(export_format).export(
            ExportRequest(
                format=export_format,
                document=public_document,
                output_path=str(output),
            )
        )
        report = audit_artifact(result.output_path, expected=public_document)
        assert report.status is ArtifactAuditStatus.PASS
        assert output.is_file()
        assert b"Internal validation" not in output.read_bytes()
