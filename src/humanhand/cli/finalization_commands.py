"""`humanhand finalize` sub-app — deterministic lexical finalization (EP-017).

The orchestrator registers this module's ``finalize_app`` into
``humanhand.cli.app`` as the "finalize" sub-app at merge time; this module
never registers itself.

Parallel API surface this module calls (verified at merge against the
merged EP-017 lexical modules; see ``_require_module`` for the fail-closed
behavior when any of them is absent from a partial build):

- ``humanhand.domain.lexical_types``:
    ``load_bundled_rules() -> Ruleset`` — bundled curated lexical rules.
- ``humanhand.domain.lexical_normalizer``:
    ``propose_changes(*, text, ruleset, protected_spans) -> LexicalProposal``
    — deterministic proposal with stable ``run_id`` and ``ruleset_hash``;
    ``protected_spans`` is a sequence of the store's protected-span dicts
    exactly as returned by ``ProjectStore.load_protected_spans``;
    ``proposal_to_payload(proposal) -> dict`` — payload keys
    ``schema_version``, ``run_id``, ``ruleset_hash``, ``changes`` (ordered
    list; each change carries its id under ``id`` or ``change_id``),
    ``review`` (initial review state), and ``findings``.
- ``humanhand.domain.lexical_review``:
    ``ReviewDecision`` (members ``ACCEPT`` and ``REJECT``),
    ``apply_review(journal, change_id, decision) -> ReviewJournal``
    (returns the updated journal; the CLI persists its payload),
    ``journal_to_payload(journal) -> dict``,
    ``journal_from_payload(payload) -> ReviewJournal``.

Contract deviations (also recorded for the EP-017 Decision Log):

1. ``finalize lexical`` takes ``--text-file <path>`` (a plain UTF-8
   working-document file) instead of a store document id: the EP-015 store
   persists claims/entities/spans/revisions but NOT full document text, so
   no document text exists to look up by id. ``--project <directory>`` is
   used only for glossary/protected-span context: protected spans are
   loaded from the store's FIRST document when one exists, empty when the
   project has no documents (or the project row is absent — reads never
   auto-create a project row). The ``--document <id>`` argument is
   accepted-but-unused, kept for blueprint signature compatibility; the
   help text says so.
2. A missing/unreadable ``--text-file`` exits 1 (input error) per the
   EP-017 task brief, not the EXIT_IO_ERROR=3 convention used by
   ``project ingest`` for package files, and the error message carries the
   real exception text (including the path).
3. Proposals persist at ``<root>/.humanhand/reports/finalize/<run_id>.json``
   and the review journal at ``<root>/.humanhand/reports/finalize/<run_id>.journal.json``
   (``reports_dir`` from the EP-015 layout, ADR-001). JSON documents are
   written with ``sort_keys=True``, UTF-8, LF, no BOM, exactly one
   trailing newline, so equal inputs yield byte-identical files.
   Re-running a lexical run with identical inputs rewrites the identical
   proposal file (idempotent).
4. ``finalize review`` reads the persisted proposal and journal payloads
   only; it does not call the lexical domain, so it works even when the
   parallel lexical modules are absent from a partial build. The "current
   journal" is the journal file when it exists, else the proposal's own
   initial review state.
5. ``finalize accept`` / ``finalize reject`` append one decision entry per
   invocation to the journal file. Applying accepted changes to a document
   is NOT performed by EP-017; it happens in a future plan.
6. Rendering is local to this module (``json.dumps(sort_keys=True)`` for
   --json, plain lines otherwise); the orchestrator owns
   ``cli/output.py`` and may later route these results through its
   renderers.

``--no-color`` is accepted for CLI-surface compatibility; this module
never emits color codes, so the flag is a documented no-op.

No user text is ever printed, logged, or stored by this module.
"""

from __future__ import annotations

import hashlib
import importlib
import json
import os
import sys
from collections.abc import Sequence
from pathlib import Path
from typing import Any, NoReturn, cast

import typer

from humanhand.cli.errors import message_for_exception
from humanhand.domain.document_nodes import SourceLocation
from humanhand.domain.protected_spans import ProtectedSpan, ProtectedSpanSet, SpanKind
from humanhand.infra.files import FileIOError, read_text_strict

# Exit-code constants are duplicated here deliberately (app.py owns the
# canonical definitions; importing them would create an import cycle).
EXIT_INPUT_ERROR = 1
EXIT_CONFIG_ERROR = 2
EXIT_IO_ERROR = 3
EXIT_SCHEMA_ERROR = 5
EXIT_INTERNAL_ERROR = 6

#: Sub-directory of the EP-015 reports_dir holding finalize artifacts.
_FINALIZE_SUBDIR = "finalize"

finalize_app = typer.Typer(
    name="finalize",
    help="Deterministic lexical finalization: propose, review, accept, reject.",
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


def _render_text(line: str) -> None:
    """Emit a plain text line to stdout. No color codes are ever emitted."""
    print(line)


def _require_module(module_name: str, json_mode: bool) -> Any:
    """Load a parallel EP-017 module or fail closed with an honest error.

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
    contain ``.humanhand/project.toml``. This explicit gate runs first and
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

    ``ProjectStoreError`` lives in the merged store modules and is matched
    by class name so this mapping keeps working when that module is absent
    from a partial build.
    """
    if isinstance(exc, FileIOError):
        return EXIT_IO_ERROR
    if type(exc).__name__ == "MigrationError":
        return EXIT_SCHEMA_ERROR
    if isinstance(exc, OSError):
        return EXIT_IO_ERROR
    return EXIT_INTERNAL_ERROR


def _require_plain_id(value: object, label: str, json_mode: bool) -> str:
    """Require a non-empty id without path separators (safe as a filename)."""
    if not isinstance(value, str) or not value:
        _report_error(f"{label} is missing or invalid", EXIT_INPUT_ERROR, json_mode)
    if any(separator in value for separator in ("/", "\\")) or value in {".", ".."}:
        _report_error(
            f"{label} must be a plain id without path separators", EXIT_INPUT_ERROR, json_mode
        )
    return value


def _reports_finalize_dir(layout_obj: Any) -> Path:
    """``<root>/.humanhand/reports/finalize`` from the EP-015 layout."""
    reports_dir = getattr(layout_obj, "reports_dir", None)
    if not isinstance(reports_dir, Path):
        raise TypeError("Project layout has no reports_dir")
    return reports_dir / _FINALIZE_SUBDIR


def _proposal_path(layout_obj: Any, run_id: str) -> Path:
    """Absolute path of the proposal JSON for a run."""
    return _reports_finalize_dir(layout_obj) / f"{run_id}.json"


def _journal_path(layout_obj: Any, run_id: str) -> Path:
    """Absolute path of the review journal JSON for a run."""
    return _reports_finalize_dir(layout_obj) / f"{run_id}.journal.json"


def _write_json_document(path: Path, payload: dict[str, object]) -> None:
    """Write a deterministic JSON document (UTF-8, LF, no BOM, one trailing newline)."""
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(
        json.dumps(payload, sort_keys=True) + "\n",
        encoding="utf-8",
        newline="\n",
    )


def _read_json_document(path: Path) -> dict[str, object]:
    """Read a stored JSON object document, failing closed on corruption."""
    try:
        raw = path.read_text(encoding="utf-8")
    except OSError as exc:
        raise FileIOError(f"Cannot read file: {path}") from exc
    try:
        parsed = json.loads(raw)
    except (TypeError, ValueError) as exc:
        raise ValueError(f"Stored file is not valid JSON: {path.name}") from exc
    if not isinstance(parsed, dict):
        raise ValueError(f"Stored file is not a JSON object: {path.name}")
    return parsed


def _change_ids(payload: dict[str, object]) -> tuple[str, ...]:
    """Ids of the ordered changes in a proposal payload, in payload order.

    Change ids are read tolerantly from the ``id`` key, falling back to
    ``change_id`` (the exact payload key is a parallel-module contract
    detail). Raises ``ValueError`` when the payload has no ordered changes
    list.
    """
    changes = payload.get("changes")
    if not isinstance(changes, list):
        raise ValueError("Proposal payload has no ordered changes list")
    ids: list[str] = []
    for change in changes:
        if not isinstance(change, dict):
            continue
        change_id: object = change.get("id")
        if not isinstance(change_id, str) or not change_id:
            change_id = change.get("change_id")
        if isinstance(change_id, str) and change_id:
            ids.append(change_id)
    return tuple(ids)


def _journal_entry_count(payload: dict[str, object]) -> int | None:
    """Number of entries in a journal payload, ``None`` when not a list."""
    entries = payload.get("entries")
    if isinstance(entries, list):
        return len(entries)
    return None


def _initial_journal_payload(payload: dict[str, object]) -> dict[str, object]:
    """Initial review state: the proposal's ``review`` payload, else ``{}``."""
    review = payload.get("review")
    if isinstance(review, dict):
        return review
    return {}


def _append_journal_entry(
    payload: dict[str, object], *, run_id: str, change_id: str, decision: str
) -> dict[str, object]:
    """Validate and append one deterministic review-history entry."""
    entries_raw = payload.get("entries", [])
    if not isinstance(entries_raw, list):
        raise ValueError("Review journal entries must be a list")
    entries: list[dict[str, object]] = []
    for index, entry in enumerate(entries_raw):
        if not isinstance(entry, dict):
            raise ValueError("Review journal entries must be objects")
        if entry.get("sequence") != index + 1:
            raise ValueError("Review journal sequence is invalid")
        if not isinstance(entry.get("change_id"), str) or entry.get("decision") not in {
            "accept",
            "reject",
        }:
            raise ValueError("Review journal entry is invalid")
        entries.append(dict(entry))
    stored_run_id = payload.get("proposal_run_id")
    if stored_run_id is not None and stored_run_id != run_id:
        raise ValueError("Review journal belongs to a different proposal run")
    if "journal_id" in payload:
        expected_id = _journal_id_for(run_id, entries)
        if payload.get("journal_id") != expected_id:
            raise ValueError("Review journal id does not match its contents")
    entries.append(
        {
            "sequence": len(entries) + 1,
            "change_id": change_id,
            "decision": decision,
        }
    )
    return {
        "schema": "lexical-review-history",
        "schema_version": 1,
        "proposal_run_id": run_id,
        "entries": entries,
        "journal_id": _journal_id_for(run_id, entries),
    }


def _journal_id_for(run_id: str, entries: list[dict[str, object]]) -> str:
    core = {
        "schema": "lexical-review-history",
        "schema_version": 1,
        "proposal_run_id": run_id,
        "entries": entries,
    }
    digest = hashlib.sha256(json.dumps(core, sort_keys=True).encode("utf-8")).hexdigest()
    return f"journal-{digest[:24]}"


def _first_document_protected_spans(
    root: Path, layout: Any, store_module: Any, project_domain: Any
) -> ProtectedSpanSet:
    """Protected spans of the store's first document, or ``()`` when none exist.

    Best-effort glossary/protected-span context per the EP-017 contract. A
    missing project row reads as an empty project (reads never auto-create
    a project row), matching the EP-015 CLI convention. The returned dicts
    are exactly what ``ProjectStore.load_protected_spans`` returns.
    """
    name = str(layout.read_project_toml(root).get("name") or root.name)
    state = project_domain.new_project_state(name=name, root=str(root))
    store = store_module.ProjectStore(root)
    try:
        try:
            loaded = store.load_project(str(state.project_id))
        except Exception as exc:
            if type(exc).__name__ != "ProjectStoreError":
                raise
            loaded = None
        if loaded is None or not loaded.document_ids:
            return ProtectedSpanSet(spans=())
        rows = store.load_protected_spans(str(loaded.document_ids[0]))
        spans = tuple(
            ProtectedSpan(
                span_id=str(row["span_id"]),
                kind=SpanKind(str(row["kind"])),
                source_location=SourceLocation(
                    start_offset=cast(int, row["start_offset"]),
                    end_offset=cast(int, row["end_offset"]),
                ),
                text=str(row["text"]),
            )
            for row in rows
        )
        return ProtectedSpanSet(spans=spans)
    finally:
        store.close()


@finalize_app.command("lexical")
def finalize_lexical_cmd(
    ctx: typer.Context,
    text_file: str = typer.Option(
        ...,
        "--text-file",
        help="Plain UTF-8 working-document file to propose changes for.",
    ),
    project: str | None = typer.Option(
        None,
        "--project",
        help="Project root; defaults to HUMANHAND_PROJECT_DIR, then the current directory.",
    ),
    document: str | None = typer.Option(
        None,
        "--document",
        help="Accepted-but-unused: kept for blueprint signature compatibility. "
        "The EP-015 store does not persist document text, so --text-file is "
        "the real input (deviation 1 in the module docstring).",
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
    """Propose deterministic lexical changes for a working document file.

    Reads the text file, loads the bundled curated ruleset, loads
    protected spans from the store's first document when available, and
    asks the lexical normalizer for a deterministic proposal. Writes the
    proposal to the project reports layout and, with --json, prints the
    proposal payload (schema_version, run_id, ruleset_hash, ordered
    changes, review state, findings). No generated prose is ever printed.
    """
    json_mode = _effective_flag(ctx, json_mode, "json_mode")
    root = _resolve_project_root(project)
    root = _require_existing_root(root, json_mode)
    root = _require_initialized_root(root, json_mode)
    try:
        text = read_text_strict(text_file)
    except FileIOError as exc:
        _report_error(str(exc), EXIT_INPUT_ERROR, json_mode)
    layout = _require_module("humanhand.infra.stores.project_layout", json_mode)
    lexicon_loader = _require_module("humanhand.infra.lexicons", json_mode)
    context_module = _require_module("humanhand.domain.lexical_context", json_mode)
    normalizer = _require_module("humanhand.domain.lexical_normalizer", json_mode)
    store_module = _require_module("humanhand.infra.stores.project_store", json_mode)
    project_domain = _require_module("humanhand.domain.project", json_mode)
    try:
        spans = _first_document_protected_spans(root, layout, store_module, project_domain)
        ruleset = lexicon_loader.load_bundled_rules()
        contexts = context_module.build_contexts(text, spans)
        proposal = normalizer.propose_changes(
            text=text,
            ruleset=ruleset,
            contexts=contexts,
            user_preferences={},
            project_glossary=(),
            register_rules=(),
            domain_glossary=(),
            safe_threshold=0.8,
            protected_spans=spans,
        )
        payload: dict[str, object] = normalizer.proposal_to_payload(proposal)
        payload["review"] = {"entries": []}
        run_id = normalizer.compute_run_id(
            {key: value for key, value in payload.items() if key not in {"run_id", "proposal_id"}}
        )
        payload["run_id"] = run_id
        payload["proposal_id"] = run_id
    except Exception as exc:
        _report_error(message_for_exception(exc), _exit_code_for(exc), json_mode)
    run_id = _require_plain_id(payload.get("run_id"), "proposal run_id", json_mode)
    layout_obj = layout.layout_for(root)
    proposal_path = _proposal_path(layout_obj, run_id)
    try:
        _write_json_document(proposal_path, payload)
    except OSError as exc:
        _report_error(message_for_exception(exc), EXIT_IO_ERROR, json_mode)
    changes = payload.get("changes")
    count = len(changes) if isinstance(changes, list) else 0
    if json_mode:
        _render_json(payload)
    else:
        _render_text(f"Finalize proposal {run_id}: {count} changes written to {proposal_path}")


@finalize_app.command("review")
def finalize_review_cmd(
    ctx: typer.Context,
    run_id: str = typer.Option(
        ...,
        "--run",
        help="Finalize run id to review.",
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
    """Print a stored proposal and its current review journal.

    Reads the persisted proposal payload and, when it exists, the journal
    file; without a journal file the proposal's own initial review state is
    shown. This command reads persisted files only and does not call the
    lexical domain.
    """
    json_mode = _effective_flag(ctx, json_mode, "json_mode")
    root = _resolve_project_root(project)
    root = _require_existing_root(root, json_mode)
    root = _require_initialized_root(root, json_mode)
    _require_plain_id(run_id, "run id", json_mode)
    layout = _require_module("humanhand.infra.stores.project_layout", json_mode)
    layout_obj = layout.layout_for(root)
    proposal_path = _proposal_path(layout_obj, run_id)
    if not proposal_path.is_file():
        _report_error(f"Run not found: {run_id}", EXIT_INPUT_ERROR, json_mode)
    try:
        payload = _read_json_document(proposal_path)
        journal_path = _journal_path(layout_obj, run_id)
        if journal_path.is_file():
            journal_payload = _read_json_document(journal_path)
        else:
            journal_payload = _initial_journal_payload(payload)
    except FileIOError as exc:
        _report_error(str(exc), EXIT_IO_ERROR, json_mode)
    except ValueError as exc:
        _report_error(str(exc), EXIT_INPUT_ERROR, json_mode)
    changes = payload.get("changes")
    count = len(changes) if isinstance(changes, list) else 0
    if json_mode:
        _render_json(
            {
                "status": "ok",
                "run_id": run_id,
                "proposal": payload,
                "journal": journal_payload,
            }
        )
    else:
        _render_text(f"Run {run_id}: proposal with {count} changes")
        entry_count = _journal_entry_count(journal_payload)
        if entry_count is None:
            _render_text("Journal entries: unknown")
        else:
            _render_text(f"Journal entries: {entry_count}")


def _record_decision(
    ctx: typer.Context,
    run_id: str,
    change_id: str,
    decision: str,
    project: str | None,
    json_mode: bool,
) -> None:
    """Shared accept/reject body: append a decision entry to the journal.

    The journal file is created from the proposal's initial review state on
    first use and then appended per invocation. Accepted changes are NOT
    applied to any document by EP-017; application happens in a future
    plan. The requested change id is validated against the proposal's
    ordered changes before any domain call.
    """
    json_mode = _effective_flag(ctx, json_mode, "json_mode")
    root = _resolve_project_root(project)
    root = _require_existing_root(root, json_mode)
    root = _require_initialized_root(root, json_mode)
    _require_plain_id(run_id, "run id", json_mode)
    _require_plain_id(change_id, "change id", json_mode)
    layout = _require_module("humanhand.infra.stores.project_layout", json_mode)
    review_module = _require_module("humanhand.domain.lexical_review", json_mode)
    layout_obj = layout.layout_for(root)
    proposal_path = _proposal_path(layout_obj, run_id)
    if not proposal_path.is_file():
        _report_error(f"Run not found: {run_id}", EXIT_INPUT_ERROR, json_mode)
    try:
        payload = _read_json_document(proposal_path)
    except FileIOError as exc:
        _report_error(str(exc), EXIT_IO_ERROR, json_mode)
    except ValueError as exc:
        _report_error(str(exc), EXIT_INPUT_ERROR, json_mode)
    try:
        known = _change_ids(payload)
    except ValueError as exc:
        _report_error(str(exc), EXIT_INPUT_ERROR, json_mode)
    if change_id not in known:
        _report_error(f"Unknown change id: {change_id}", EXIT_INPUT_ERROR, json_mode)
    journal_path = _journal_path(layout_obj, run_id)
    try:
        if journal_path.is_file():
            journal_payload = _read_json_document(journal_path)
        else:
            journal_payload = _initial_journal_payload(payload)
        journal_payload_out = _append_journal_entry(
            journal_payload,
            run_id=run_id,
            change_id=change_id,
            decision=decision,
        )
        latest: dict[str, str] = {}
        entries = journal_payload_out["entries"]
        if not isinstance(entries, list):
            raise ValueError("Invalid review journal entries")
        for entry in entries:
            if not isinstance(entry, dict):
                raise ValueError("Invalid review journal entry")
            latest[str(entry["change_id"])] = str(entry["decision"])
        decisions = tuple(
            review_module.ReviewDecision(item_id, item_decision)
            for item_id, item_decision in latest.items()
        )
        domain_journal = review_module.build_review_journal(run_id, decisions)
        normalizer = _require_module("humanhand.domain.lexical_normalizer", json_mode)
        proposal = normalizer.proposal_from_payload(payload)
        review_module.apply_review(proposal, domain_journal)
        _write_json_document(journal_path, journal_payload_out)
    except FileIOError as exc:
        _report_error(str(exc), EXIT_IO_ERROR, json_mode)
    except ValueError as exc:
        _report_error(str(exc), EXIT_INPUT_ERROR, json_mode)
    except Exception as exc:
        _report_error(message_for_exception(exc), _exit_code_for(exc), json_mode)
    if json_mode:
        _render_json(
            {
                "status": "ok",
                "run_id": run_id,
                "change_id": change_id,
                "decision": decision,
                "journal": journal_payload_out,
            }
        )
    else:
        _render_text(f"{decision.capitalize()}d change {change_id} in run {run_id}")


@finalize_app.command("accept")
def finalize_accept_cmd(
    ctx: typer.Context,
    run_id: str = typer.Option(
        ...,
        "--run",
        help="Finalize run id.",
    ),
    change_id: str = typer.Option(
        ...,
        "--change",
        help="Change id to accept.",
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
    """Record an ACCEPT decision for one proposed change in a run's journal."""
    _record_decision(ctx, run_id, change_id, "accept", project, json_mode)


@finalize_app.command("reject")
def finalize_reject_cmd(
    ctx: typer.Context,
    run_id: str = typer.Option(
        ...,
        "--run",
        help="Finalize run id.",
    ),
    change_id: str = typer.Option(
        ...,
        "--change",
        help="Change id to reject.",
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
    """Record a REJECT decision for one proposed change in a run's journal."""
    _record_decision(ctx, run_id, change_id, "reject", project, json_mode)
