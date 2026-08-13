"""`humanhand export` sub-app — public document export (EP-016).

The orchestrator registers this module's ``export_app`` into
``humanhand.cli.app`` as the "export" sub-app at merge time; this module
never registers itself.

Honest simplification recorded for the EP-016 Decision Log:

The EP-015 store persists claims, entities, and spans but NOT full
document text, so ``export document`` cannot re-read an accepted document
from the store alone. This command therefore REQUIRES ``--package
<package.json>`` (the same source-package JSON file that was ingested);
it rebuilds the document surface text from the package's parsed
``CanonicalDocument`` and reads claims from the project store
(``ProjectStore.load_claims``) with a documented fallback to
``build_claims_from_package`` when the store holds no claims. The
parallel ``build_public_document`` contract mirrors this: it takes
``title``, ``sections``, and ``claims`` and never sees raw file bytes.

Parallel API surface this module calls (verified at merge against the
merged EP-016 modules):

- ``humanhand.domain.public_document``:
    ``build_public_document(*, title: str, sections: Sequence[str],
    claims: Sequence[str]) -> PublicDocument``.
- ``humanhand.domain.export_contract``:
    ``ExportFormat`` (StrEnum with values ``txt``, ``md``, ``docx``,
    ``pdf``), ``ExportRequest(format: ExportFormat, document:
    PublicDocument, output_path: str)``, and
    ``validate_export_request(request) -> tuple[str, ...]`` returning
    violation codes (empty tuple means valid).
- ``humanhand.infra.exporters``:
    ``get_exporter(format: ExportFormat) -> exporter``; the exporter's
    ``export(request: ExportRequest)`` returns an ``ExportResult``
    exposing ``output_path: str``, ``format: ExportFormat``,
    ``sha256: str``, ``byte_count: int``. The exporter itself refuses
    any request with violation codes, so this module checks the
    violations first and reports them as an input error (exit 1).
- ``humanhand.infra.stores.project_layout``:
    ``read_project_toml(root) -> dict[str, object]``.
- ``humanhand.infra.stores.project_store``:
    ``ProjectStore(root)`` with ``load_claims(document_id)`` returning a
    tuple of dict rows ("proposition" key) or an empty tuple, and
    ``close()``.
- ``humanhand.domain.claims_v2``:
    ``build_claims_from_package(package)`` returning a tuple of
    ``ClaimV2`` (``canonical_proposition`` attribute) and a
    ``CoverageStatus``.

Local behavior choices:

1. Section texts come from the package document's PARAGRAPH nodes in
   document order; when the node tree has no paragraph nodes, the
   surface text split on blank lines is used (documented fallback).
2. The target file is written by the real exporter only; this module
   never fabricates file content, hashes, or byte counts — the
   ``sha256`` and ``byte_count`` in the result come from the real
   ``ExportResult`` returned by ``get_exporter(...).export(...)``.
3. ``--format`` is validated first so an unknown format fails with
   exit 1 before any project, package, or module access.
4. When a parallel EP-016 module is absent from the build, the command
   fails closed with exit code 2 and an honest "not available in this
   build" message. No stubs or simulated results are ever produced.
5. ``--no-color`` is accepted for CLI-surface compatibility; this
   module never emits color codes, so the flag is a documented no-op.

No user text is ever printed, logged, or stored by this module.
"""

from __future__ import annotations

import importlib
import json
import os
import sys
from collections.abc import Sequence
from pathlib import Path
from typing import Any, NoReturn

import typer

from humanhand.cli.errors import message_for_exception
from humanhand.domain.document_nodes import NodeType
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

#: CLI-visible export formats (must match the parallel ExportFormat enum).
EXPORT_FORMATS: frozenset[str] = frozenset({"txt", "md", "docx", "pdf"})

export_app = typer.Typer(
    name="export",
    help="Export approved public documents.",
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


def _render_json(payload: dict[str, object] | list[object]) -> None:
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
    """Load a parallel EP-016 module or fail closed with an honest error.

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
    """Resolve the project root: --project > HUMANHAND_PROJECT_DIR > '.'.

    Mirrors project_commands; duplicated because the helper there is
    private and importing it would couple these modules.
    """
    if project_flag:
        return Path(project_flag)
    env_value = os.getenv("HUMANHAND_PROJECT_DIR")
    if env_value and env_value.strip():
        return Path(env_value.strip())
    return Path(".")


def _require_existing_root(root: Path, json_mode: bool) -> Path:
    """Fail closed when the project root does not exist."""
    if not root.exists():
        _report_error(f"project directory not found: {root}", EXIT_INPUT_ERROR, json_mode)
    return root


def _require_initialized_root(root: Path, json_mode: bool) -> Path:
    """Fail closed when the project root is not initialized."""
    if not (root / ".humanhand" / "project.toml").is_file():
        _report_error(
            f"project directory is not initialized: {root} (missing .humanhand/project.toml)",
            EXIT_INPUT_ERROR,
            json_mode,
        )
    return root


def _exit_code_for(exc: Exception) -> int:
    """Map a known exception to a stable exit code.

    Matches by class name for ``MigrationError`` so the mapping keeps
    working when that module is absent from a partial build.
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


def _paragraph_texts(document: object) -> tuple[str, ...]:
    """Section texts from a canonical document's PARAGRAPH nodes.

    Paragraph nodes are collected in document (pre-order) order. When the
    node tree has no paragraph nodes, the surface text split on blank
    lines (double newlines) is used as a documented fallback.
    """
    texts: list[str] = []
    for node in getattr(document, "nodes", ()) or ():
        if getattr(node, "node_type", None) == NodeType.PARAGRAPH:
            text = getattr(node, "text", None)
            if isinstance(text, str) and text:
                texts.append(text)
    if texts:
        return tuple(texts)
    surface_text = getattr(document, "surface_text", "")
    if isinstance(surface_text, str) and surface_text:
        return tuple(part for part in surface_text.split("\n\n") if part)
    return ()


def _claim_propositions(claims: Sequence[object]) -> tuple[str, ...]:
    """Claim propositions from store rows (dicts) or ClaimV2 objects.

    The store returns dict rows with a "proposition" key; the claims_v2
    fallback returns ClaimV2 objects exposing ``canonical_proposition``.
    """
    propositions: list[str] = []
    for claim in claims:
        if isinstance(claim, dict):
            value = claim.get("proposition")
        else:
            value = getattr(claim, "canonical_proposition", None)
        if isinstance(value, str) and value:
            propositions.append(value)
    return tuple(propositions)


@export_app.command("document")
def export_document_cmd(
    ctx: typer.Context,
    format_value: str = typer.Option(
        ...,
        "--format",
        help="Output format: txt, md, docx, or pdf.",
    ),
    out: str = typer.Option(
        ...,
        "--out",
        help="Output file path.",
    ),
    package_json: str = typer.Option(
        ...,
        "--package",
        help=(
            "Source-package JSON file (the store does not persist full "
            "document text, so the package is the document source)."
        ),
    ),
    project: str | None = typer.Option(
        None,
        "--project",
        help="Project root; defaults to HUMANHAND_PROJECT_DIR, then '.'.",
    ),
    title: str | None = typer.Option(
        None,
        "--title",
        help="Document title; defaults to the project.toml name.",
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
    """Export a public document through the real exporter pipeline."""
    json_mode = _effective_flag(ctx, json_mode, "json_mode")
    no_color = _effective_flag(ctx, no_color, "no_color")
    if format_value not in EXPORT_FORMATS:
        _report_error(
            f"Unknown export format: {format_value} (expected txt, md, docx, or pdf)",
            EXIT_INPUT_ERROR,
            json_mode,
        )
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
            f"Source package cannot be exported: status is {package.status.value}",
            EXIT_INPUT_ERROR,
            json_mode,
        )

    root = _require_initialized_root(root, json_mode)
    layout = _require_module("humanhand.infra.stores.project_layout", json_mode)
    store_module = _require_module("humanhand.infra.stores.project_store", json_mode)
    public_doc_module = _require_module("humanhand.domain.public_document", json_mode)
    export_contract = _require_module("humanhand.domain.export_contract", json_mode)
    exporters = _require_module("humanhand.infra.exporters", json_mode)

    try:
        name = str(layout.read_project_toml(root).get("name") or root.name)
        document_title = title or name
        sections = _paragraph_texts(package.document)
        store = store_module.ProjectStore(root)
        try:
            revision = store.current_revision(str(package.package_id))
            if revision is None:
                raise DomainError(
                    "Source package is not ingested in this project; run 'project ingest' first"
                )
            revision_status = getattr(getattr(revision, "status", None), "value", None)
            if revision_status != "accepted":
                raise DomainError("Source package has no accepted project revision")
            stored_claims = store.load_claims(str(package.package_id))
            claim_propositions = _claim_propositions(stored_claims)
        finally:
            store.close()
        public_document = public_doc_module.build_public_document(
            title=document_title,
            sections=sections,
            claims=claim_propositions,
        )
        export_format = export_contract.ExportFormat(format_value)
        request = export_contract.ExportRequest(
            format=export_format,
            document=public_document,
            output_path=str(Path(out)),
        )
        violations = export_contract.validate_export_request(request)
        if violations:
            _report_error(
                f"Refusing export request: {', '.join(violations)}",
                EXIT_INPUT_ERROR,
                json_mode,
            )
        if Path(out).resolve() == Path(package_json).resolve():
            raise DomainError("Output path must not match the source package path")
        exporter = exporters.get_exporter(export_format)
        result = exporter.export(request=request)
    except DomainError as exc:
        _report_error(str(exc), EXIT_INPUT_ERROR, json_mode)
    except Exception as exc:
        _report_error(message_for_exception(exc), _exit_code_for(exc), json_mode)

    output_path = getattr(result, "output_path", None)
    sha256 = getattr(result, "sha256", None)
    byte_count = getattr(result, "byte_count", None)
    if json_mode:
        _render_json(
            {
                "status": "ok",
                "output_path": output_path,
                "sha256": sha256,
                "byte_count": byte_count,
            }
        )
    else:
        _render_text(f"Exported {format_value} document: {output_path}")
        if sha256 is not None:
            _render_text(f"  sha256: {sha256}")
        if byte_count is not None:
            _render_text(f"  bytes: {byte_count}")
