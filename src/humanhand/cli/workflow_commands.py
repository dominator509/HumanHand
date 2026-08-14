"""`humanhand workflow` — integrated deterministic pre-SLM pipeline (EP-019).

This command family is the production path. Legacy commands remain available
for compatibility, while workflow commands operate only on persisted accepted
revisions and one resolved privacy runtime.
"""

from __future__ import annotations

import json
import sys
from pathlib import Path
from typing import NoReturn

import typer

from humanhand.application.import_services import build_import_policy, import_source_package
from humanhand.application.integrated_workflow import (
    build_integrated_context,
    finalize_reviewed_revision,
    ingest_source_package,
    load_document_state,
    propose_integrated_lexical_changes,
)
from humanhand.application.style_services import packages_for_label
from humanhand.domain.artifact_findings import ArtifactAuditStatus
from humanhand.domain.canonical_document import CanonicalDocument
from humanhand.domain.context_capsule import capsule_to_payload
from humanhand.domain.document_nodes import NodeType
from humanhand.domain.document_serialization import dumps_stable
from humanhand.domain.export_contract import ExportFormat, ExportRequest
from humanhand.domain.import_findings import ImportStatus
from humanhand.domain.lexical_normalizer import proposal_from_payload, proposal_to_payload
from humanhand.domain.lexical_review import (
    ReviewDecision,
    build_review_journal,
    review_from_payload,
    review_to_payload,
)
from humanhand.domain.project import ProjectState, new_project_state
from humanhand.domain.public_document import build_public_document
from humanhand.domain.style_profiles import StyleEvidenceProfile, build_profile
from humanhand.domain.types import DomainError
from humanhand.infra.auditors import audit_artifact
from humanhand.infra.config import Config, load_config
from humanhand.infra.exporters import get_exporter
from humanhand.infra.files import FileIOError, file_size, read_bytes, read_head_bytes
from humanhand.infra.importers.pipeline import SandboxedImportInspector
from humanhand.infra.lexicons.lexicon_loader import load_bundled_rules
from humanhand.infra.privacy.runtime import (
    PrivacyRuntime,
    PrivacyRuntimeError,
    build_privacy_runtime,
    open_project_store,
    open_style_vault,
)
from humanhand.infra.stores.integrated_project_store import IntegratedProjectStore
from humanhand.infra.stores.project_layout import (
    ProjectLayout,
    init_layout,
    layout_for,
    read_project_toml,
)
from humanhand.infra.stores.project_store import ProjectStoreError

EXIT_INPUT_ERROR = 1
EXIT_CONFIG_ERROR = 2
EXIT_IO_ERROR = 3

_WORKFLOW_REPORTS = "workflow"

workflow_app = typer.Typer(
    name="workflow",
    help="Integrated accepted-revision workflow: ingest, style, context, finalize, export.",
    no_args_is_help=True,
)


class _Reader:
    def size_bytes(self, path: str | Path) -> int:
        return file_size(path)

    def read_head(self, path: str | Path, max_bytes: int) -> bytes:
        return read_head_bytes(path, max_bytes)

    def read_bytes(self, path: str | Path) -> bytes:
        return read_bytes(path)


def _error(message: str, code: int, json_mode: bool) -> NoReturn:
    if json_mode:
        payload = {"status": "error", "message": message, "exit_code": code}
        print(json.dumps(payload, sort_keys=True))
    else:
        print(f"error: {message}", file=sys.stderr)
    raise typer.Exit(code)


def _json(payload: dict[str, object]) -> None:
    print(json.dumps(payload, sort_keys=True, ensure_ascii=False))


def _load_runtime(json_mode: bool) -> tuple[Config, PrivacyRuntime]:
    try:
        config = load_config()
        return config, build_privacy_runtime(config)
    except (ValueError, PrivacyRuntimeError) as exc:
        _error(str(exc), EXIT_CONFIG_ERROR, json_mode)


def _project_root(value: str) -> Path:
    return Path(value).expanduser().resolve()


def _project_name(root: Path) -> str:
    data = read_project_toml(root)
    return str(data.get("name") or root.name)


def _project_state(root: Path) -> ProjectState:
    return new_project_state(name=_project_name(root), root=str(root))


def _require_layout(root: Path, json_mode: bool) -> ProjectLayout:
    if not (root / ".humanhand" / "project.toml").is_file():
        _error(
            f"project is not initialized: {root}; run workflow ingest or project init",
            EXIT_INPUT_ERROR,
            json_mode,
        )
    return layout_for(root)


def _open_store(root: Path, runtime: PrivacyRuntime) -> IntegratedProjectStore:
    return open_project_store(root, runtime)


def _profile(
    *,
    profile_id: str,
    config: Config,
    runtime: PrivacyRuntime,
    require_complete: bool = True,
) -> StyleEvidenceProfile:
    vault = open_style_vault(config.style_vault_dir, runtime)
    packages = packages_for_label(vault.list_packages(), vault, profile_id)
    profile = build_profile(profile_id=profile_id, packages=packages)
    if require_complete and profile.status != "complete":
        raise DomainError(f"Style profile {profile_id!r} is not complete: {profile.status}")
    return profile


def _bound_profile(
    *,
    store: IntegratedProjectStore,
    project: ProjectState,
    config: Config,
    runtime: PrivacyRuntime,
) -> StyleEvidenceProfile | None:
    label = store.project_style_profile(project.project_id)
    if not label:
        return None
    return _profile(profile_id=label, config=config, runtime=runtime)


def _workflow_dir(layout: ProjectLayout) -> Path:
    path = layout.reports_dir / _WORKFLOW_REPORTS
    path.mkdir(parents=True, exist_ok=True)
    return path


def _write_payload(path: Path, payload: dict[str, object]) -> None:
    path.write_text(dumps_stable(payload), encoding="utf-8", newline="\n")


def _read_payload(path: Path) -> dict[str, object]:
    try:
        value = json.loads(path.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError) as exc:
        raise DomainError(f"Cannot read workflow record: {path.name}") from exc
    if not isinstance(value, dict):
        raise DomainError(f"Workflow record is not a JSON object: {path.name}")
    return value


def _proposal_path(layout: ProjectLayout, run_id: str) -> Path:
    return _workflow_dir(layout) / f"{run_id}.proposal.json"


def _review_path(layout: ProjectLayout, run_id: str) -> Path:
    return _workflow_dir(layout) / f"{run_id}.review.json"


@workflow_app.command("ingest")
def ingest_cmd(
    source: str = typer.Argument(
        ...,
        help="Source document in any supported clean-room format.",
    ),
    project: str = typer.Option(..., "--project", help="Project directory."),
    name: str | None = typer.Option(
        None,
        "--name",
        help="Name used when initializing a new project.",
    ),
    style_profile: str | None = typer.Option(
        None,
        "--style-profile",
        help="Complete style profile to bind.",
    ),
    json_mode: bool = typer.Option(False, "--json"),
) -> None:
    """Clean-import a source and persist its initial accepted revision."""
    config, runtime = _load_runtime(json_mode)
    root = _project_root(project)
    try:
        if not (root / ".humanhand" / "project.toml").is_file():
            init_layout(root, name=name or root.name or "humanhand-project")
        _require_layout(root, json_mode)
        policy = build_import_policy(
            lane="source",
            max_bytes=config.import_max_bytes,
            max_expanded_bytes=config.import_max_expanded_bytes,
            max_nodes=config.import_max_nodes,
            timeout_seconds=config.import_timeout_seconds,
        )
        imported = import_source_package(
            path=source,
            policy=policy,
            reader=_Reader(),
            inspector=SandboxedImportInspector(),
        )
        if imported.package is None or imported.inspection.status not in {
            ImportStatus.OK,
            ImportStatus.FINDINGS,
        }:
            raise DomainError(
                f"Source import is not eligible for ingest: {imported.inspection.status.value}"
            )
        state = _project_state(root)
        if style_profile is not None:
            _profile(
                profile_id=style_profile,
                config=config,
                runtime=runtime,
            )
        store = _open_store(root, runtime)
        try:
            result = ingest_source_package(
                package=imported.package,
                project=state,
                store=store,
                style_profile_id=style_profile or "",
            )
        finally:
            store.close()
    except FileIOError as exc:
        _error(str(exc), EXIT_IO_ERROR, json_mode)
    except (DomainError, ProjectStoreError) as exc:
        _error(str(exc), EXIT_INPUT_ERROR, json_mode)
    except OSError as exc:
        _error(str(exc), EXIT_IO_ERROR, json_mode)
    _json(
        {
            "status": "ok",
            "project_id": result.project_id,
            "document_id": result.document_id,
            "revision_id": result.revision_id,
            "style_profile": style_profile or "",
            "claims": result.claim_count,
            "entities": result.entity_count,
            "protected_spans": result.protected_span_count,
            "relationships": result.relationship_count,
            "encrypted_retention": runtime.encrypted_retention,
        }
    )


@workflow_app.command("bind-style")
def bind_style_cmd(
    profile_id: str = typer.Argument(
        ...,
        help="Reviewed complete Style Fidelity profile.",
    ),
    project: str = typer.Option(..., "--project"),
    json_mode: bool = typer.Option(False, "--json"),
) -> None:
    """Bind one complete reviewed style profile to a project."""
    config, runtime = _load_runtime(json_mode)
    root = _project_root(project)
    _require_layout(root, json_mode)
    try:
        profile = _profile(profile_id=profile_id, config=config, runtime=runtime)
        state = _project_state(root)
        store = _open_store(root, runtime)
        try:
            store.bind_style_profile(state.project_id, profile.profile_id)
        finally:
            store.close()
    except (DomainError, ProjectStoreError) as exc:
        _error(str(exc), EXIT_INPUT_ERROR, json_mode)
    _json(
        {
            "status": "ok",
            "project_id": state.project_id,
            "style_profile": profile.profile_id,
        }
    )


@workflow_app.command("context")
def context_cmd(
    project: str = typer.Option(..., "--project"),
    document_id: str = typer.Option(..., "--document"),
    block_id: str = typer.Option(..., "--block"),
    include_content: bool = typer.Option(
        False,
        "--include-content",
        help="Print the content-bearing capsule.",
    ),
    json_mode: bool = typer.Option(False, "--json"),
) -> None:
    """Build context from the accepted revision and bound style profile."""
    config, runtime = _load_runtime(json_mode)
    root = _project_root(project)
    _require_layout(root, json_mode)
    state = _project_state(root)
    try:
        store = _open_store(root, runtime)
        try:
            loaded = load_document_state(
                project_id=state.project_id,
                document_id=document_id,
                store=store,
            )
            profile = _bound_profile(
                store=store,
                project=state,
                config=config,
                runtime=runtime,
            )
            capsule = build_integrated_context(
                state=loaded,
                block_id=block_id,
                profile=profile,
            )
        finally:
            store.close()
    except (DomainError, ProjectStoreError) as exc:
        _error(str(exc), EXIT_INPUT_ERROR, json_mode)
    if include_content:
        _json(capsule_to_payload(capsule))
    else:
        _json(
            {
                "status": "ok",
                "capsule_id": capsule.capsule_id,
                "document_id": capsule.document_id,
                "revision_id": capsule.revision_id,
                "block_id": capsule.block_id,
                "claims": len(capsule.required_claims),
                "protected_spans": len(capsule.protected_spans),
                "style_invariants": len(capsule.style_hard_invariants),
                "style_tendencies": len(capsule.style_soft_tendencies),
                "content_included": False,
            }
        )


@workflow_app.command("propose")
def propose_cmd(
    project: str = typer.Option(..., "--project"),
    document_id: str = typer.Option(..., "--document"),
    json_mode: bool = typer.Option(False, "--json"),
) -> None:
    """Create a deterministic lexical proposal for the accepted revision."""
    _config, runtime = _load_runtime(json_mode)
    root = _project_root(project)
    layout = _require_layout(root, json_mode)
    state = _project_state(root)
    try:
        store = _open_store(root, runtime)
        try:
            loaded = load_document_state(
                project_id=state.project_id,
                document_id=document_id,
                store=store,
            )
            proposal = propose_integrated_lexical_changes(
                state=loaded,
                ruleset=load_bundled_rules(),
            )
        finally:
            store.close()
        payload = proposal_to_payload(proposal)
        path = _proposal_path(layout, proposal.run_id)
        _write_payload(path, payload)
    except (DomainError, ProjectStoreError) as exc:
        _error(str(exc), EXIT_INPUT_ERROR, json_mode)
    except OSError as exc:
        _error(str(exc), EXIT_IO_ERROR, json_mode)
    _json(
        {
            "status": "ok",
            "run_id": proposal.run_id,
            "document_id": document_id,
            "revision_id": loaded.revision.revision_id,
            "changes": len(proposal.changes),
            "findings": len(proposal.findings),
            "proposal_path": str(path),
        }
    )


@workflow_app.command("decide")
def decide_cmd(
    run_id: str = typer.Option(..., "--run"),
    change_id: str = typer.Option(..., "--change"),
    decision: str = typer.Option(..., "--decision", help="accept or reject"),
    project: str = typer.Option(..., "--project"),
    json_mode: bool = typer.Option(False, "--json"),
) -> None:
    """Record the current human decision for one lexical change."""
    if decision not in {"accept", "reject"}:
        _error("--decision must be accept or reject", EXIT_INPUT_ERROR, json_mode)
    root = _project_root(project)
    layout = _require_layout(root, json_mode)
    try:
        proposal = proposal_from_payload(_read_payload(_proposal_path(layout, run_id)))
        if change_id not in {change.change_id for change in proposal.changes}:
            raise DomainError(f"Unknown change id: {change_id}")
        path = _review_path(layout, run_id)
        effective: dict[str, str] = {}
        if path.is_file():
            prior = review_from_payload(_read_payload(path))
            effective.update({item.change_id: item.decision for item in prior.decisions})
        effective[change_id] = decision
        ordered = tuple(
            ReviewDecision(change.change_id, effective[change.change_id])
            for change in proposal.changes
            if change.change_id in effective
        )
        journal = build_review_journal(run_id, ordered)
        _write_payload(path, review_to_payload(journal))
    except DomainError as exc:
        _error(str(exc), EXIT_INPUT_ERROR, json_mode)
    except OSError as exc:
        _error(str(exc), EXIT_IO_ERROR, json_mode)
    _json(
        {
            "status": "ok",
            "run_id": run_id,
            "change_id": change_id,
            "decision": decision,
            "journal_id": journal.journal_id,
        }
    )


@workflow_app.command("apply")
def apply_cmd(
    run_id: str = typer.Option(..., "--run"),
    project: str = typer.Option(..., "--project"),
    document_id: str = typer.Option(..., "--document"),
    json_mode: bool = typer.Option(False, "--json"),
) -> None:
    """Apply approved changes and commit a validated accepted revision."""
    config, runtime = _load_runtime(json_mode)
    root = _project_root(project)
    layout = _require_layout(root, json_mode)
    state = _project_state(root)
    try:
        proposal = proposal_from_payload(_read_payload(_proposal_path(layout, run_id)))
        journal = review_from_payload(_read_payload(_review_path(layout, run_id)))
        store = _open_store(root, runtime)
        try:
            loaded = load_document_state(
                project_id=state.project_id,
                document_id=document_id,
                store=store,
            )
            profile = _bound_profile(
                store=store,
                project=state,
                config=config,
                runtime=runtime,
            )
            result = finalize_reviewed_revision(
                state=loaded,
                proposal=proposal,
                journal=journal,
                store=store,
                profile=profile,
            )
        finally:
            store.close()
    except (DomainError, ProjectStoreError) as exc:
        _error(str(exc), EXIT_INPUT_ERROR, json_mode)
    _json(
        {
            "status": "ok",
            "document_id": result.document_id,
            "revision_id": result.revision_id,
            "accepted_changes": result.accepted_change_count,
            "accepted_text_sha256": result.accepted_text_sha256,
            "style_checked": result.style_report is not None,
        }
    )


def _sections(document: CanonicalDocument) -> tuple[str, ...]:
    values = tuple(
        node.text for node in document.nodes if node.node_type is NodeType.PARAGRAPH and node.text
    )
    if values:
        return values
    return tuple(part for part in document.surface_text.split("\n\n") if part)


@workflow_app.command("export")
def export_cmd(
    project: str = typer.Option(..., "--project"),
    document_id: str = typer.Option(..., "--document"),
    format_value: str = typer.Option(..., "--format", help="txt, md, docx, or pdf"),
    out: str = typer.Option(..., "--out"),
    title: str | None = typer.Option(None, "--title"),
    json_mode: bool = typer.Option(False, "--json"),
) -> None:
    """Export and independently audit the latest accepted revision."""
    _config, runtime = _load_runtime(json_mode)
    root = _project_root(project)
    _require_layout(root, json_mode)
    state = _project_state(root)
    try:
        fmt = ExportFormat(format_value)
        store = _open_store(root, runtime)
        try:
            loaded = load_document_state(
                project_id=state.project_id,
                document_id=document_id,
                store=store,
            )
        finally:
            store.close()
        public_document = build_public_document(
            title=title or state.name,
            sections=_sections(loaded.document),
            claims=(),
        )
        request = ExportRequest(format=fmt, document=public_document, output_path=out)
        result = get_exporter(fmt).export(request)
        audit = audit_artifact(result.output_path, expected=public_document)
        if audit.status is not ArtifactAuditStatus.PASS:
            raise DomainError(
                "Exported artifact failed independent audit: "
                + ",".join(finding.code for finding in audit.findings)
            )
    except ValueError:
        _error(f"Unknown export format: {format_value}", EXIT_INPUT_ERROR, json_mode)
    except (DomainError, ProjectStoreError) as exc:
        _error(str(exc), EXIT_INPUT_ERROR, json_mode)
    except OSError as exc:
        _error(str(exc), EXIT_IO_ERROR, json_mode)
    _json(
        {
            "status": "ok",
            "document_id": document_id,
            "revision_id": loaded.revision.revision_id,
            "output_path": result.output_path,
            "format": fmt.value,
            "sha256": result.sha256,
            "byte_count": result.byte_count,
            "audit": audit.to_payload(),
            "internal_claims_included": False,
        }
    )


@workflow_app.command("status")
def status_cmd(
    project: str = typer.Option(..., "--project"),
    json_mode: bool = typer.Option(False, "--json"),
) -> None:
    """Show production-workflow readiness for one local project."""
    _config, runtime = _load_runtime(json_mode)
    root = _project_root(project)
    _require_layout(root, json_mode)
    state = _project_state(root)
    try:
        store = _open_store(root, runtime)
        try:
            loaded_project = store.load_project(state.project_id)
            documents: list[dict[str, object]] = []
            for document_id in loaded_project.document_ids:
                revision = store.latest_accepted_revision(document_id)
                content = store.load_revision_content(document_id)
                documents.append(
                    {
                        "document_id": document_id,
                        "accepted_revision": revision.revision_id if revision else None,
                        "content_persisted": content is not None,
                        "finalization_run_id": (content.finalization_run_id if content else ""),
                    }
                )
            style_profile = store.project_style_profile(state.project_id)
        finally:
            store.close()
    except ProjectStoreError as exc:
        _error(str(exc), EXIT_INPUT_ERROR, json_mode)
    _json(
        {
            "status": "ok",
            "project_id": state.project_id,
            "privacy_mode": runtime.policy.mode.value,
            "encrypted_retention": runtime.encrypted_retention,
            "style_profile": style_profile,
            "documents": documents,
        }
    )
