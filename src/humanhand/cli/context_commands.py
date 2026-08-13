"""`humanhand context` sub-app — deterministic context capsules (EP-015).

The orchestrator registers this module's ``context_app`` into
``humanhand.cli.app`` as the "context" sub-app at merge time; this module
never registers itself.

Parallel API surface this module calls (verified at merge against the
merged EP-015 modules):

- ``humanhand.infra.stores.project_store``:
    ``ProjectStore(root)`` and ``ProjectStoreError``; the surface used
    here: ``load_project(project_id)`` (``document_ids``),
    ``current_revision(document_id)``, ``close()``.
- ``humanhand.domain.project``:
    ``new_project_state(*, name, root) -> ProjectState``.
- ``humanhand.domain.claims_v2``:
    ``build_claims_from_package(package) -> (claims, coverage_status)``.
- ``humanhand.domain.entities``:
    ``build_entities_from_package(package) -> EntityRegistry``.
- ``humanhand.domain.context_capsule``:
    ``build_context_capsule(*, document, revision, block_id,
    project_state, claims, protected_spans, citations, entities, profile,
    policy) -> ContextCapsule``;
    ``capsule_to_json(capsule) -> str``;
    ``capsule_from_json(text) -> ContextCapsule`` (integrity-verified);
    ``validate_capsule(capsule, policy) -> tuple[str, ...]`` (violations
    are plain strings).
- ``humanhand.domain.context_policy``: ``ContextPolicy()`` default policy.

Contract deviations (also recorded for the EP-015 Decision Log):

1. ``context preview`` requires a ``--document <package.json>``
   source-package JSON file: the EP-015 store tables persist
   claims/entities/spans/revisions but not full canonical documents, so
   the block node, document, claims, and entities are taken from the
   file. The package id must match an ingested project document, and its
   stored current revision supplies the capsule revision. ``project_state``
   is derived deterministically from ``project.toml`` name and root.
2. ``context preview`` requires an initialized project directory
   (``.humanhand/project.toml``) even though the capsule is built from
   the file: the capsule's ``project_id``/``document_id``/``revision_id``
   are project-scoped ids, so the project must exist first.
3. The capsule JSON is printed in both text and JSON mode: a context
   capsule is inherently a JSON document.
4. Rendering is local to this module; the orchestrator owns
   ``cli/output.py`` and may later route these results through its
   renderers.
5. When a parallel EP-015 module is absent from the build, commands fail
   closed with exit code 2 and an honest "not available in this build"
   message. No stubs or simulated results are ever produced.

``--no-color`` is accepted for CLI-surface compatibility; this module
never emits color codes, so the flag is a documented no-op.

No user text is ever printed, logged, or stored by this module.
"""

from __future__ import annotations

import importlib
import json
import sys
from collections.abc import Sequence
from pathlib import Path
from typing import Any, NoReturn

import typer

from humanhand.cli.errors import message_for_exception
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

context_app = typer.Typer(
    name="context",
    help="Context capsules: deterministic, inspectable, no model.",
    no_args_is_help=True,
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


def _render_capsule(capsule_json: str) -> None:
    """Print a capsule JSON document verbatim (both text and JSON mode)."""
    print(capsule_json)


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


def _violation_to_payload(violation: object) -> dict[str, object]:
    """Render one policy violation as a stable payload entry.

    ``validate_capsule`` reports violations as plain strings; each is
    surfaced verbatim under ``detail``.
    """
    return {"detail": str(violation)}


def _project_state_for_root(root: Path, layout: Any, project_domain: Any) -> Any:
    """Derive the deterministic project state for an initialized root.

    The project id is a pure digest of ``(name, root)``; the name comes
    from ``project.toml`` (falling back to the directory name).
    """
    toml = layout.read_project_toml(root)
    name = str(toml.get("name") or root.name)
    return project_domain.new_project_state(name=name, root=str(root))


@context_app.command("preview")
def context_preview_cmd(
    ctx: typer.Context,
    project: str = typer.Option(
        ...,
        "--project",
        help="Project root (required).",
    ),
    block: str = typer.Option(
        ...,
        "--block",
        help="Block id (node id) inside the canonical document.",
    ),
    document: str = typer.Option(
        ...,
        "--document",
        help="Source-package JSON file whose canonical document provides the block "
        "(deviation: the store does not persist full canonical documents in EP-015).",
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
    """Build and print a deterministic context capsule for one block.

    The source package id must identify an ingested project document, and
    that document's stored current revision is used. The ``--document``
    file supplies the canonical document, the block node, and the
    claims/entities built from it. The capsule is
    printed as JSON in both text and JSON mode: a context capsule is
    inherently a JSON document.
    """
    json_mode = _effective_flag(ctx, json_mode, "json_mode")
    root = Path(project).resolve()
    root = _require_existing_root(root, json_mode)
    try:
        package_text = read_text_strict(document)
    except FileIOError as exc:
        _report_error(message_for_exception(exc), EXIT_IO_ERROR, json_mode)
    try:
        package = source_package_from_json(package_text)
    except Exception as exc:
        _report_error(message_for_exception(exc), EXIT_INPUT_ERROR, json_mode)
    if not any(node.node_id == block for node in package.document.nodes):
        _report_error(f"Block not found in document: {block}", EXIT_INPUT_ERROR, json_mode)
    root = _require_initialized_root(root, json_mode)
    layout = _require_module("humanhand.infra.stores.project_layout", json_mode)
    store_module = _require_module("humanhand.infra.stores.project_store", json_mode)
    project_domain = _require_module("humanhand.domain.project", json_mode)
    claims_module = _require_module("humanhand.domain.claims_v2", json_mode)
    entities_module = _require_module("humanhand.domain.entities", json_mode)
    capsule_module = _require_module("humanhand.domain.context_capsule", json_mode)
    policy_module = _require_module("humanhand.domain.context_policy", json_mode)
    try:
        project_state = _project_state_for_root(root, layout, project_domain)
        store = store_module.ProjectStore(root)
        try:
            try:
                loaded_state = store.load_project(project_state.project_id)
            except Exception as exc:
                if type(exc).__name__ != "ProjectStoreError":
                    raise
                loaded_state = None
            document_id = str(package.package_id)
            document_ids = loaded_state.document_ids if loaded_state is not None else ()
            if document_id not in document_ids:
                raise DomainError(
                    "Source package is not ingested in this project; run 'project ingest' first"
                )
            revision = store.current_revision(document_id)
            if revision is None:
                raise DomainError(f"Stored revision is missing for document: {document_id}")
            claims, _coverage_status = claims_module.build_claims_from_package(package)
            entities = entities_module.build_entities_from_package(package)
            capsule = capsule_module.build_context_capsule(
                document=package.document,
                revision=revision,
                block_id=block,
                project_state=project_state,
                claims=claims,
                protected_spans=tuple(package.evidence.protected_spans.spans),
                citations=package.evidence.citations,
                entities=entities.entities,
                profile=None,
                policy=policy_module.ContextPolicy(),
            )
        finally:
            store.close()
    except DomainError as exc:
        _report_error(str(exc), EXIT_INPUT_ERROR, json_mode)
    except Exception as exc:
        _report_error(message_for_exception(exc), _exit_code_for(exc), json_mode)
    _render_capsule(capsule_module.capsule_to_json(capsule))


@context_app.command("validate")
def context_validate_cmd(
    ctx: typer.Context,
    capsule_file: str = typer.Argument(
        ...,
        help="Path to a context capsule JSON file.",
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
    """Validate a context capsule file: JSON shape, integrity, and policy.

    The file must parse as JSON; ``capsule_from_json`` then verifies the
    capsule integrity (the capsule_id digest anchor), and
    ``validate_capsule`` runs the default ``ContextPolicy``. Violations
    exit 1 with status "invalid".
    """
    json_mode = _effective_flag(ctx, json_mode, "json_mode")
    try:
        text = read_text_strict(capsule_file)
    except FileIOError as exc:
        _report_error(message_for_exception(exc), EXIT_IO_ERROR, json_mode)
    try:
        json.loads(text)
    except json.JSONDecodeError as exc:
        _report_error(f"Invalid capsule JSON: {exc.msg}", EXIT_INPUT_ERROR, json_mode)
    capsule_module = _require_module("humanhand.domain.context_capsule", json_mode)
    policy_module = _require_module("humanhand.domain.context_policy", json_mode)
    try:
        capsule = capsule_module.capsule_from_json(text)
        policy = policy_module.ContextPolicy()
        violations = [
            _violation_to_payload(violation)
            for violation in capsule_module.validate_capsule(capsule, policy)
        ]
    except Exception as exc:
        _report_error(message_for_exception(exc), _exit_code_for(exc), json_mode)
    if violations:
        if json_mode:
            _render_json({"status": "invalid", "violations": violations})
        else:
            for violation in violations:
                _render_text(f"violation: {violation.get('detail')}")
        raise typer.Exit(EXIT_INPUT_ERROR)
    if json_mode:
        _render_json({"status": "ok", "violations": []})
    else:
        _render_text("Context capsule valid")
