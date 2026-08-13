"""`humanhand project` sub-app — local project brain (EP-015).

The orchestrator registers this module's ``project_app`` into
``humanhand.cli.app`` as the "project" sub-app at merge time; this module
never registers itself.

Parallel API surface this module calls (verified at merge against the
merged EP-015 modules):

- ``humanhand.infra.stores.project_layout``:
    ``init_layout(root, *, name) -> ProjectLayout`` (idempotent, never
    deletes), ``layout_for(root) -> ProjectLayout``,
    ``read_project_toml(root) -> dict[str, str]`` (keys ``name`` and
    ``schema_version``; ``{}`` when missing).
    ``ProjectLayout`` attributes: ``root``, ``humanhand_dir``,
    ``project_toml``, ``database``, ``blobs_dir``, ``reports_dir``,
    ``exports_dir``, ``source_dir``, ``style_dir``, ``working_dir``.
- ``humanhand.infra.stores.project_store``:
    ``ProjectStore(root)`` and ``ProjectStoreError``; instance surface:
    ``create_project(state)``, ``load_project(project_id)``,
    ``add_document(document_id, project_id, *, purpose)``,
    ``save_revision(revision)``, ``current_revision(document_id)``,
    ``list_revisions(document_id)``, ``save_claims(document_id, claims)``,
    ``save_entities(document_id, entities)``,
    ``save_protected_spans(document_id, spans)``,
    ``record_approval(*, target_kind, target_id, decision, decided_by)``,
    ``close()``.
- ``humanhand.domain.project``:
    ``new_project_state(*, name, root) -> ProjectState`` (deterministic
    ``project_id``; ``root`` is a path string).
- ``humanhand.domain.claims_v2``:
    ``build_claims_from_package(package) -> (claims, coverage_status)``.
- ``humanhand.domain.entities``:
    ``build_entities_from_package(package) -> EntityRegistry``.
- ``humanhand.domain.relationships``:
    ``build_relationships(package, registry) -> RelationshipSet``.
- ``humanhand.domain.revisions``:
    ``create_initial_revision(*, document_id, structure_signature,
    accepted_text_sha256) -> DocumentRevision``.
- ``humanhand.domain.structure_signature``:
    ``compute_structure_signature(document) -> StructureSignature``.
- ``humanhand.infra.stores.migration_runner``: ``MigrationError``.
- ``humanhand.infra.project.obsidian_projection`` (optional; the command
    fails closed with exit 1 when it is absent from the build):
    ``project_to_obsidian(*, vault, package, project_state, claims,
    revision) -> ObsidianProjectionResult``.

Contract deviations (also recorded for the EP-015 Decision Log):

1. ``project ingest`` takes a source-package JSON *file* argument instead
   of a stored import id: the EP-015 store tables persist
   claims/entities/spans/revisions but not raw import inspections, so no
   inspection exists to look up by id. The orchestrator may extend import
   persistence later and switch this command back to an id argument.
2. ``project ingest`` derives the project id deterministically with
   ``new_project_state`` (name from ``project.toml``, falling back to the
   directory name) and creates the project row when it does not exist
   yet; re-ingesting an already-ingested package id fails closed (exit 1)
   instead of overwriting anything.
3. ``project ingest`` records ``accepted_text_sha256`` as the sha256 hex
   digest of the canonical document's surface text (the accepted text of
   the initial revision); this is this module's documented convention.
4. ``project status`` and ``project revisions`` enumerate documents
   through ``load_project``: the v1 schema has no ``document_ids`` column,
   so document order is rebuilt from the documents table (ordered by
   document id). A missing project row reads as an empty project (the CLI
   never auto-creates a project row on read).
5. ``project export-obsidian`` requires a ``--document <package.json>``
   source-package file: the real projection writes from a source package,
   and the EP-015 store does not persist full canonical documents. The
   projection's plaintext warning is surfaced on stderr (text mode) or in
   the JSON result.
6. Rendering is local to this module (``json.dumps(sort_keys=True)`` for
   --json, plain lines otherwise); the orchestrator owns
   ``cli/output.py`` and may later route these results through its
   renderers.
7. When a parallel EP-015 module is absent from the build, commands fail
   closed with exit code 2 and an honest "not available in this build"
   message. No stubs or simulated results are ever produced.

``--no-color`` is accepted for CLI-surface compatibility; this module
never emits color codes, so the flag is a documented no-op.

No user text is ever printed, logged, or stored by this module.
"""

from __future__ import annotations

import hashlib
import importlib
import importlib.util
import json
import os
import sys
from collections.abc import Sequence
from pathlib import Path
from typing import Any, NoReturn

import typer

from humanhand.cli.errors import message_for_exception
from humanhand.domain.import_findings import ImportStatus
from humanhand.domain.source_package import source_package_from_json
from humanhand.domain.types import DomainError
from humanhand.infra.files import FileIOError, read_text_strict

# Exit-code constants are duplicated here deliberately (app.py owns the
# canonical definitions; importing them would create an import cycle).
EXIT_INPUT_ERROR = 1
EXIT_CONFIG_ERROR = 2
EXIT_IO_ERROR = 3
EXIT_SCHEMA_ERROR = 5
EXIT_INTERNAL_ERROR = 6

project_app = typer.Typer(
    name="project",
    help="Local project brain: init, status, ingest, revisions, export.",
    no_args_is_help=True,
)

# Real ProjectLayout path attributes, in report order (see the docstring).
_LAYOUT_PATH_ATTRIBUTES: tuple[str, ...] = (
    "humanhand_dir",
    "project_toml",
    "database",
    "blobs_dir",
    "reports_dir",
    "exports_dir",
    "source_dir",
    "style_dir",
    "working_dir",
)


def _effective_flag(ctx: typer.Context | None, local_value: bool, key: str) -> bool:
    """Resolve a flag from local options plus root callback state.

    Mirrors ``_effective_flag`` in app.py; duplicated to avoid an import
    cycle between app.py and this module.
    """
    if local_value:
        return True
    if ctx is None or not isinstance(ctx.obj, dict):
        return False
    return bool(ctx.obj.get(key, False))


def _report_error(message: str, code: int, json_mode: bool) -> NoReturn:
    """Emit a one-line error and exit with a stable code."""
    if json_mode:
        print(
            json.dumps(
                {"status": "error", "message": message, "exit_code": code},
                sort_keys=True,
            )
        )
    else:
        print(f"error: {message}", file=sys.stderr)
    raise typer.Exit(code)


def _render_json(payload: dict[str, object] | Sequence[object]) -> None:
    """Emit a JSON result to stdout.

    Rendering is intentionally local to this module: the orchestrator owns
    ``cli/output.py`` and may later route these results through its
    renderers; this helper keeps the command self-contained until then.
    """
    print(json.dumps(payload, sort_keys=True))


def _render_text(line: str) -> None:
    """Emit a plain text line to stdout. No color codes are ever emitted."""
    print(line)


def _require_module(module_name: str, json_mode: bool) -> Any:
    """Load a parallel EP-015 module or fail closed with an honest error.

    The missing name is reported (including transitive module failures);
    no stub is ever created in place of the real module.
    """
    try:
        return importlib.import_module(module_name)
    except ModuleNotFoundError as exc:
        missing = exc.name or module_name
        _report_error(
            f"{module_name} is not available in this build (missing module: {missing})",
            EXIT_CONFIG_ERROR,
            json_mode,
        )


def _resolve_project_root(project_flag: str | None) -> Path:
    """Resolve the project root.

    Resolution order: ``--project``, then the ``HUMANHAND_PROJECT_DIR``
    environment variable, then ``.``.
    """
    if project_flag:
        return Path(project_flag)
    env_value = os.getenv("HUMANHAND_PROJECT_DIR")
    if env_value and env_value.strip():
        return Path(env_value.strip())
    return Path(".")


def _require_existing_root(root: Path, json_mode: bool) -> Path:
    """Fail closed when the resolved project directory does not exist."""
    if not root.is_dir():
        _report_error(f"project directory not found: {root}", EXIT_INPUT_ERROR, json_mode)
    return root


def _require_initialized_root(root: Path, json_mode: bool) -> Path:
    """Fail closed when the directory is not an initialized project layout.

    Checks the documented layout (blueprint 9.3): the directory must
    contain ``.humanhand/project.toml``. The store auto-initializes a
    layout when the file is missing, so this explicit gate runs first and
    keeps CLI commands from creating projects implicitly.
    """
    if not (root / ".humanhand" / "project.toml").is_file():
        _report_error(
            f"project directory is not initialized: {root} (missing .humanhand/project.toml)",
            EXIT_INPUT_ERROR,
            json_mode,
        )
    return root


def _exit_code_for(exc: Exception) -> int:
    """Map a known exception to a stable exit code.

    ``MigrationError`` and ``ProjectStoreError`` live in the merged store
    modules and are matched by class name so this mapping keeps working
    when those modules are absent from a partial build.
    """
    if isinstance(exc, FileIOError):
        return EXIT_IO_ERROR
    if isinstance(exc, DomainError):
        return EXIT_INPUT_ERROR
    if type(exc).__name__ == "MigrationError":
        return EXIT_SCHEMA_ERROR
    if isinstance(exc, OSError):
        return EXIT_IO_ERROR
    return EXIT_INTERNAL_ERROR


def _layout_paths(layout_obj: object) -> dict[str, str]:
    """Read the real ProjectLayout path attributes into a flat mapping."""
    paths: dict[str, str] = {}
    for attribute in _LAYOUT_PATH_ATTRIBUTES:
        value = getattr(layout_obj, attribute, None)
        if value is not None:
            paths[attribute] = str(value)
    return paths


def _revision_row(revision: object) -> dict[str, object]:
    """Extract the real DocumentRevision fields via getattr."""
    return {
        "document_id": getattr(revision, "document_id", None),
        "revision_id": getattr(revision, "revision_id", None),
        "token": getattr(revision, "token", None),
        "status": getattr(revision, "status", None),
    }


def _document_ids(store: Any, project_id: str) -> tuple[str, ...]:
    """Document ids of the project, or ``()`` when the project row is absent.

    The v1 schema has no ``document_ids`` column; ``load_project`` rebuilds
    document order from the documents table (ordered by document id). A
    missing project row raises ``ProjectStoreError`` and is treated as an
    empty project: reads never auto-create a project row.
    """
    try:
        state = store.load_project(project_id)
    except Exception as exc:
        if type(exc).__name__ != "ProjectStoreError":
            raise
        return ()
    return tuple(str(document_id) for document_id in state.document_ids)


def _ensure_project_row(store: Any, project_id: str, state: Any) -> None:
    """Create the project row when it does not exist yet (idempotent)."""
    try:
        store.load_project(project_id)
    except Exception as exc:
        if type(exc).__name__ != "ProjectStoreError":
            raise
        store.create_project(state)


def _project_name_from_toml(root: Path, layout: Any) -> str:
    """Project display name: ``project.toml`` name, else the directory name."""
    toml = layout.read_project_toml(root)
    return str(toml.get("name") or root.name)


@project_app.command("init")
def project_init_cmd(
    ctx: typer.Context,
    directory: str = typer.Argument(
        ...,
        help="Directory to initialize as the project root.",
    ),
    name: str = typer.Option(
        ...,
        "--name",
        help="Project display name.",
    ),
    json_mode: bool = typer.Option(
        False,
        "--json",
        help="Output JSON to stdout only.",
    ),
    no_color: bool = typer.Option(
        False,
        "--no-color",
        help="Disable color output.",
    ),
) -> None:
    """Initialize a user-selected project directory.

    ``init_layout`` is idempotent and never deletes existing content; an
    existing layout is left untouched. ``project_id`` is the deterministic
    digest from ``new_project_state`` over ``(name, root)``.
    """
    json_mode = _effective_flag(ctx, json_mode, "json_mode")
    layout = _require_module("humanhand.infra.stores.project_layout", json_mode)
    project_domain = _require_module("humanhand.domain.project", json_mode)
    try:
        layout_obj = layout.init_layout(directory, name=name)
        root = Path(layout_obj.root)
        stored_name = _project_name_from_toml(root, layout)
        state = project_domain.new_project_state(name=stored_name, root=str(root))
        project_id = str(state.project_id)
    except DomainError as exc:
        _report_error(str(exc), EXIT_INPUT_ERROR, json_mode)
    except Exception as exc:
        _report_error(message_for_exception(exc), _exit_code_for(exc), json_mode)
    if json_mode:
        _render_json({"status": "ok", "root": str(root), "project_id": project_id})
    else:
        _render_text(f"Project initialized: {root}")


@project_app.command("status")
def project_status_cmd(
    ctx: typer.Context,
    project: str | None = typer.Option(
        None,
        "--project",
        help="Project root; defaults to HUMANHAND_PROJECT_DIR, then the current directory.",
    ),
    json_mode: bool = typer.Option(
        False,
        "--json",
        help="Output JSON to stdout only.",
    ),
    no_color: bool = typer.Option(
        False,
        "--no-color",
        help="Disable color output.",
    ),
) -> None:
    """Show the project layout, schema version, and revision count.

    Project-directory resolution order: ``--project``, then the
    ``HUMANHAND_PROJECT_DIR`` environment variable, then ``.``. Documents
    are enumerated through the project store (see the module docstring).
    """
    json_mode = _effective_flag(ctx, json_mode, "json_mode")
    root = _resolve_project_root(project)
    root = _require_existing_root(root, json_mode)
    root = _require_initialized_root(root, json_mode)
    layout = _require_module("humanhand.infra.stores.project_layout", json_mode)
    store_module = _require_module("humanhand.infra.stores.project_store", json_mode)
    project_domain = _require_module("humanhand.domain.project", json_mode)
    try:
        toml = layout.read_project_toml(root)
        name = str(toml.get("name") or root.name)
        state = project_domain.new_project_state(name=name, root=str(root))
        layout_obj = layout.layout_for(root)
        store = store_module.ProjectStore(root)
        try:
            schema_version = str(store.schema_version)
            revision_count = 0
            for document_id in _document_ids(store, state.project_id):
                revision_count += len(store.list_revisions(str(document_id)))
        finally:
            store.close()
    except Exception as exc:
        _report_error(message_for_exception(exc), _exit_code_for(exc), json_mode)
    paths = _layout_paths(layout_obj)
    if json_mode:
        _render_json(
            {
                "status": "ok",
                "root": str(root),
                "name": name,
                "schema_version": schema_version,
                "revisions": revision_count,
                "layout": paths,
            }
        )
    else:
        _render_text(f"Project: {root}")
        _render_text(f"  name: {name}")
        _render_text(f"  schema_version: {schema_version}")
        _render_text(f"  revisions: {revision_count}")
        for label, path_value in paths.items():
            _render_text(f"  {label}: {path_value}")


@project_app.command("revisions")
def project_revisions_cmd(
    ctx: typer.Context,
    project: str | None = typer.Option(
        None,
        "--project",
        help="Project root; defaults to HUMANHAND_PROJECT_DIR, then the current directory.",
    ),
    json_mode: bool = typer.Option(
        False,
        "--json",
        help="Output JSON to stdout only.",
    ),
    no_color: bool = typer.Option(
        False,
        "--no-color",
        help="Disable color output.",
    ),
) -> None:
    """List all stored document revisions (ids, tokens, statuses)."""
    json_mode = _effective_flag(ctx, json_mode, "json_mode")
    root = _resolve_project_root(project)
    root = _require_existing_root(root, json_mode)
    root = _require_initialized_root(root, json_mode)
    layout = _require_module("humanhand.infra.stores.project_layout", json_mode)
    store_module = _require_module("humanhand.infra.stores.project_store", json_mode)
    project_domain = _require_module("humanhand.domain.project", json_mode)
    try:
        name = _project_name_from_toml(root, layout)
        state = project_domain.new_project_state(name=name, root=str(root))
        store = store_module.ProjectStore(root)
        try:
            revisions: list[object] = []
            for document_id in _document_ids(store, state.project_id):
                revisions.extend(store.list_revisions(str(document_id)))
        finally:
            store.close()
    except Exception as exc:
        _report_error(message_for_exception(exc), _exit_code_for(exc), json_mode)
    rows = [_revision_row(revision) for revision in revisions]
    if json_mode:
        _render_json(rows)
    else:
        for row in rows:
            _render_text(
                f"{row['document_id']} revision {row['revision_id']} "
                f"token {row['token']} status {row['status']}"
            )


@project_app.command("ingest")
def project_ingest_cmd(
    ctx: typer.Context,
    package_json: str = typer.Argument(
        ...,
        help="Path to a source-package JSON file (deviation: a file, not a stored import id).",
    ),
    project: str | None = typer.Option(
        None,
        "--project",
        help="Project root; defaults to HUMANHAND_PROJECT_DIR, then the current directory.",
    ),
    json_mode: bool = typer.Option(
        False,
        "--json",
        help="Output JSON to stdout only.",
    ),
    no_color: bool = typer.Option(
        False,
        "--no-color",
        help="Disable color output.",
    ),
) -> None:
    """Ingest a source package file into the project store.

    Parses the package with the real ``source_package_from_json``, stores
    its protected spans/claims/entities, creates the initial document and
    revision, and records an approval record (kind "ingest", decided by
    "cli"). The document id is the source package id (deterministic per
    canonical document). Re-ingesting the same package id fails closed
    with exit 1; nothing is ever overwritten.
    """
    json_mode = _effective_flag(ctx, json_mode, "json_mode")
    root = _resolve_project_root(project)
    root = _require_existing_root(root, json_mode)
    try:
        package_text = read_text_strict(package_json)
    except FileIOError as exc:
        _report_error(message_for_exception(exc), EXIT_IO_ERROR, json_mode)
    try:
        package = source_package_from_json(package_text)
    except Exception as exc:
        _report_error(message_for_exception(exc), EXIT_INPUT_ERROR, json_mode)
    if package.status not in {ImportStatus.OK, ImportStatus.FINDINGS}:
        _report_error(
            f"Source package cannot be ingested: status is {package.status.value}",
            EXIT_INPUT_ERROR,
            json_mode,
        )
    root = _require_initialized_root(root, json_mode)
    layout = _require_module("humanhand.infra.stores.project_layout", json_mode)
    store_module = _require_module("humanhand.infra.stores.project_store", json_mode)
    project_domain = _require_module("humanhand.domain.project", json_mode)
    claims_module = _require_module("humanhand.domain.claims_v2", json_mode)
    entities_module = _require_module("humanhand.domain.entities", json_mode)
    relationships_module = _require_module("humanhand.domain.relationships", json_mode)
    revisions_domain = _require_module("humanhand.domain.revisions", json_mode)
    signature_module = _require_module("humanhand.domain.structure_signature", json_mode)
    try:
        name = _project_name_from_toml(root, layout)
        state = project_domain.new_project_state(name=name, root=str(root))
        store = store_module.ProjectStore(root)
        try:
            document_id = str(package.package_id)
            claims, _coverage_status = claims_module.build_claims_from_package(package)
            entities = entities_module.build_entities_from_package(package)
            relationships = relationships_module.build_relationships(package, entities)
            spans = tuple(package.evidence.protected_spans.spans)
            signature = signature_module.compute_structure_signature(package.document)
            accepted_sha256 = hashlib.sha256(
                package.document.surface_text.encode("utf-8")
            ).hexdigest()
            revision = revisions_domain.create_initial_revision(
                document_id=document_id,
                structure_signature=signature,
                accepted_text_sha256=accepted_sha256,
            )
            with store.atomic():
                _ensure_project_row(store, state.project_id, state)
                if store.current_revision(document_id) is not None:
                    raise DomainError(f"Document already ingested: {document_id}")
                store.add_document(document_id, state.project_id, purpose="")
                store.save_claims(document_id, claims)
                store.save_entities(document_id, entities.entities)
                store.save_protected_spans(document_id, spans)
                store.save_relationships(document_id, relationships.relationships)
                store.save_revision(revision)
                store.record_approval(
                    target_kind="ingest",
                    target_id=f"{document_id}:{revision.revision_id}",
                    decision="accepted",
                    decided_by="cli",
                )
        finally:
            store.close()
    except DomainError as exc:
        _report_error(str(exc), EXIT_INPUT_ERROR, json_mode)
    except Exception as exc:
        _report_error(message_for_exception(exc), _exit_code_for(exc), json_mode)
    counts = {
        "claims": len(claims),
        "entities": len(entities.entities),
        "protected_spans": len(spans),
        "relationships": len(relationships.relationships),
    }
    if json_mode:
        _render_json(
            {
                "status": "ok",
                "root": str(root),
                "project_id": state.project_id,
                "document_id": document_id,
                "revision_id": revision.revision_id,
                "approval": "ingest",
                **counts,
            }
        )
    else:
        _render_text(
            f"Ingested {document_id}: revision {revision.revision_id} "
            f"(claims {counts['claims']}, entities {counts['entities']}, "
            f"protected spans {counts['protected_spans']})"
        )


@project_app.command("export-obsidian")
def project_export_obsidian_cmd(
    ctx: typer.Context,
    vault: str = typer.Argument(
        ...,
        help="User-selected Obsidian vault directory.",
    ),
    document: str = typer.Option(
        ...,
        "--document",
        help="Source-package JSON file to project (deviation: the store does not "
        "persist full canonical documents in EP-015).",
    ),
    project: str | None = typer.Option(
        None,
        "--project",
        help="Project root; defaults to HUMANHAND_PROJECT_DIR, then the current directory.",
    ),
    json_mode: bool = typer.Option(
        False,
        "--json",
        help="Output JSON to stdout only.",
    ),
    no_color: bool = typer.Option(
        False,
        "--no-color",
        help="Disable color output.",
    ),
) -> None:
    """Project a source package into a user-selected Obsidian vault.

    Explicit and user-triggered only; the projection is not authoritative,
    never auto-syncs, never overwrites an existing file with different
    content, and omits internal ids. The plaintext warning is surfaced on
    stderr (text mode) or in the JSON result. Fails closed (exit 1) when
    the projection module is not part of the build.
    """
    json_mode = _effective_flag(ctx, json_mode, "json_mode")
    if importlib.util.find_spec("humanhand.infra.project.obsidian_projection") is None:
        _report_error(
            "obsidian projection unavailable: "
            "humanhand.infra.project.obsidian_projection is not part of this build",
            EXIT_INPUT_ERROR,
            json_mode,
        )
    root = _resolve_project_root(project)
    root = _require_existing_root(root, json_mode)
    root = _require_initialized_root(root, json_mode)
    try:
        package_text = read_text_strict(document)
    except FileIOError as exc:
        _report_error(message_for_exception(exc), EXIT_IO_ERROR, json_mode)
    try:
        package = source_package_from_json(package_text)
    except Exception as exc:
        _report_error(message_for_exception(exc), EXIT_INPUT_ERROR, json_mode)
    layout = _require_module("humanhand.infra.stores.project_layout", json_mode)
    store_module = _require_module("humanhand.infra.stores.project_store", json_mode)
    project_domain = _require_module("humanhand.domain.project", json_mode)
    claims_module = _require_module("humanhand.domain.claims_v2", json_mode)
    projection = _require_module("humanhand.infra.project.obsidian_projection", json_mode)
    try:
        name = _project_name_from_toml(root, layout)
        state = project_domain.new_project_state(name=name, root=str(root))
        claims, _coverage_status = claims_module.build_claims_from_package(package)
        store = store_module.ProjectStore(root)
        try:
            revision = store.current_revision(str(package.package_id))
            if revision is None:
                raise DomainError(
                    "Source package is not ingested in this project; run 'project ingest' first"
                )
        finally:
            store.close()
        result = projection.project_to_obsidian(
            vault=Path(vault),
            package=package,
            project_state=state,
            claims=claims,
            revision=revision,
        )
        produced = [str(path) for path in result.written_files]
    except Exception as exc:
        _report_error(message_for_exception(exc), _exit_code_for(exc), json_mode)
    if json_mode:
        _render_json(
            {
                "status": "ok",
                "vault": str(Path(vault)),
                "files": produced,
                "warning": result.warning,
            }
        )
    else:
        print(result.warning, file=sys.stderr)
        _render_text(f"Projected to vault: {vault}")
        for path_value in produced:
            _render_text(f"  {path_value}")
