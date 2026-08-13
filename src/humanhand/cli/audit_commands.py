"""`humanhand audit` sub-app — independent artifact and unicode audits (EP-016).

The orchestrator registers this module's ``audit_app`` into
``humanhand.cli.app`` as the "audit" sub-app at merge time; this module
never registers itself.

Parallel API surface this module calls (verified at merge against the
merged EP-016 modules):

- ``humanhand.infra.auditors``:
    ``audit_artifact(path: str | Path, *, expected: PublicDocument |
    None = None) -> ArtifactAuditReport``.
- ``humanhand.infra.auditors.unicode_auditor``:
    ``UnicodeAuditor().audit_file(path: str | Path, *, expected:
    PublicDocument | None) -> report``.

Both reports are ``humanhand.domain.artifact_findings.ArtifactAuditReport``
objects exposing ``format``, ``status`` (an ``ArtifactAuditStatus``
StrEnum with the value "pass" or "fail"), and
``to_payload() -> dict[str, object]``. The payload is the report's own
JSON object (SPEC-013 result shape: schema, schema_version, format,
status "pass"/"fail", findings). This module prints that payload
verbatim, never invents fields, and derives its own exit code from the
report's real ``status`` ("pass" -> 0, anything else -> 1).

Contract deviations (also recorded for the EP-016 Decision Log):

1. Exit codes: 0 on PASS, 1 on FAIL, with the JSON report still on
   stdout in --json mode (the report itself carries the pass/fail
   status). Input errors (missing or non-file paths) exit 3.
2. ``--expected`` is intentionally not exposed: the unicode audit runs
   with ``expected=None``, so the report reflects the real
   standalone-guard check of the target file.
3. Rendering is local to this module (``json.dumps(sort_keys=True)``
   for --json, plain lines otherwise); the orchestrator owns
   ``cli/output.py`` and may later route these results through its
   renderers.
4. When a parallel EP-016 audit module is absent from the build, the
   command fails closed with exit code 2 and an honest "not available
   in this build" message. No stubs or simulated results are ever
   produced.

``--no-color`` is accepted for CLI-surface compatibility; this module
never emits color codes, so the flag is a documented no-op.

No user text is ever printed, logged, or stored by this module.
"""

from __future__ import annotations

import importlib
import json
import sys
from pathlib import Path
from typing import Any, NoReturn

import typer

from humanhand.cli.errors import message_for_exception
from humanhand.domain.types import DomainError
from humanhand.infra.files import FileIOError

# Exit-code constants are duplicated here deliberately (app.py owns the
# canonical definitions; importing them would create an import cycle).
EXIT_INPUT_ERROR = 1
EXIT_CONFIG_ERROR = 2
EXIT_IO_ERROR = 3
EXIT_SCHEMA_ERROR = 5
EXIT_INTERNAL_ERROR = 6

audit_app = typer.Typer(
    name="audit",
    help="Independent artifact and unicode audits.",
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


def _render_json(payload: dict[str, object]) -> None:
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
    if type(exc).__name__ == "AuditorError":
        return EXIT_IO_ERROR
    if isinstance(exc, OSError):
        return EXIT_IO_ERROR
    return EXIT_INTERNAL_ERROR


def _require_audit_target(path: str, json_mode: bool) -> Path:
    """Fail closed unless the audit target is an existing regular file."""
    candidate = Path(path)
    if not candidate.exists():
        _report_error(f"File not found: {candidate}", EXIT_IO_ERROR, json_mode)
    if not candidate.is_file():
        _report_error(f"Not a regular file: {candidate}", EXIT_IO_ERROR, json_mode)
    return candidate


def _emit_audit_result(payload: dict[str, object], json_mode: bool) -> None:
    """Print the real report payload and exit 0 (pass) or 1 (fail).

    The exit code is derived from the report's own ``status`` field in
    its payload ("pass" -> 0; anything else, including an unexpected
    shape, -> 1). The report has no boolean ``passed`` attribute; the
    payload status is the real contract signal.
    """
    passed = str(payload.get("status", "fail")).lower() == "pass"
    if json_mode:
        _render_json(payload)
    else:
        for key, value in payload.items():
            _render_text(f"{key}: {value}")
    if not passed:
        raise typer.Exit(EXIT_INPUT_ERROR)


@audit_app.command("artifact")
def audit_artifact_cmd(
    ctx: typer.Context,
    path: str = typer.Argument(
        ...,
        help="Path to the artifact to audit.",
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
    """Audit a public artifact independently (exit 0 pass, exit 1 fail)."""
    json_mode = _effective_flag(ctx, json_mode, "json_mode")
    no_color = _effective_flag(ctx, no_color, "no_color")
    _require_audit_target(path, json_mode)
    auditors = _require_module("humanhand.infra.auditors", json_mode)
    try:
        report = auditors.audit_artifact(path)
        payload = report.to_payload()
    except Exception as exc:
        _report_error(message_for_exception(exc), _exit_code_for(exc), json_mode)
    if not isinstance(payload, dict):
        _report_error(
            "audit report payload is not a JSON object",
            EXIT_INTERNAL_ERROR,
            json_mode,
        )
    _emit_audit_result(payload, json_mode)


@audit_app.command("unicode")
def audit_unicode_cmd(
    ctx: typer.Context,
    path: str = typer.Argument(
        ...,
        help="Path to the file to audit for unicode issues.",
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
    """Audit a file for unicode issues (exit 0 pass, exit 1 fail)."""
    json_mode = _effective_flag(ctx, json_mode, "json_mode")
    no_color = _effective_flag(ctx, no_color, "no_color")
    _require_audit_target(path, json_mode)
    unicode_auditor_module = _require_module("humanhand.infra.auditors.unicode_auditor", json_mode)
    try:
        auditor = unicode_auditor_module.UnicodeAuditor()
        report = auditor.audit_file(path, expected=None)
        payload = report.to_payload()
    except Exception as exc:
        _report_error(message_for_exception(exc), _exit_code_for(exc), json_mode)
    if not isinstance(payload, dict):
        _report_error(
            "audit report payload is not a JSON object",
            EXIT_INTERNAL_ERROR,
            json_mode,
        )
    _emit_audit_result(payload, json_mode)
