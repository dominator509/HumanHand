"""`humanhand privacy` sub-app — privacy policy, doctor, project validation (EP-016).

The orchestrator registers this module's ``privacy_app`` into
``humanhand.cli.app`` as the "privacy" sub-app at merge time; this module
never registers itself.

Parallel API surface this module calls (verified at merge against the
merged EP-016 modules):

- ``humanhand.domain.privacy``:
    ``load_privacy_policy(mode: str) -> PrivacyPolicy``. The returned
    ``PrivacyPolicy`` is a frozen dataclass exposing at least
    ``mode: str``, ``network_allowed: bool``,
    ``detector_cache_enabled: bool``, and ``log_mode: str`` (the
    documented SPEC-013 contract fields). This module reads those
    attributes via ``getattr`` (the same pattern as EP-015's
    ``_revision_row``) and never invents fields the real policy does not
    expose.

Contract deviations (also recorded for the EP-016 Decision Log):

1. ``privacy show`` prints the policy's real attribute values (mode,
   network_allowed, detector_cache_enabled, log_mode) instead of a full
   ``to_payload()`` dump; the parallel ``PrivacyPolicy`` may add fields
   later without changing this module.
2. ``privacy doctor`` runs only local checks: (a) privacy-mode validity
   (config load fails closed with exit 2 on an unknown mode), (b) a
   mismatch between config cache-enabled and the policy's
   detector_cache_enabled, (c) ``HUMANHAND_PROJECT_DIR`` set without an
   initialized ``.humanhand/project.toml``, and (d) a style vault
   containing ``decisions.jsonl`` while the mode is ``strict_local``
   (raw evidence retained outside strict scope; the reasoning is part
   of the finding message). Findings are advisory: exit 0 is returned
   even when findings exist; exit 2 is reserved for configuration
   errors and missing parallel modules. The doctor never touches the
   network and never inspects user text.
3. ``privacy validate-project`` is a pure filesystem inspection: it
   checks the documented layout (``.humanhand/project.toml`` plus
   ``.humanhand/project.db`` or ``.humanhand/project.db.bak``) and flags
   unexpected top-level entries outside the five layout directories
   (``.humanhand``, ``source``, ``style``, ``working``, ``exports``).
   It never auto-creates or deletes anything, and it exits 0 even when
   findings exist (input errors exit 1).
4. Rendering is local to this module (``json.dumps(sort_keys=True)``
   for --json, plain lines otherwise); the orchestrator owns
   ``cli/output.py`` and may later route these results through its
   renderers.
5. When the parallel EP-016 privacy module is absent from the build,
   commands fail closed with exit code 2 and an honest "not available
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

# Exit-code constants are duplicated here deliberately (app.py owns the
# canonical definitions; importing them would create an import cycle).
EXIT_INPUT_ERROR = 1
EXIT_CONFIG_ERROR = 2
EXIT_IO_ERROR = 3
EXIT_SCHEMA_ERROR = 5
EXIT_INTERNAL_ERROR = 6

privacy_app = typer.Typer(
    name="privacy",
    help="Privacy policy, doctor, and project-layout validation.",
    no_args_is_help=True,
)

#: Documented PrivacyPolicy attribute names read by ``privacy show``.
_POLICY_ATTRIBUTES: tuple[str, ...] = (
    "mode",
    "network_allowed",
    "detector_cache_enabled",
    "log_mode",
)

#: Top-level entries a humanhand project may own (blueprint 9.3).
_LAYOUT_TOP_LEVEL_DIRS: frozenset[str] = frozenset(
    {".humanhand", "source", "style", "working", "exports"}
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


def _exit_code_for(exc: Exception) -> int:
    """Map a known exception to a stable exit code.

    Matches by class name for ``MigrationError`` so the mapping keeps
    working when that module is absent from a partial build.
    """
    if isinstance(exc, OSError):
        return EXIT_IO_ERROR
    if type(exc).__name__ == "MigrationError":
        return EXIT_SCHEMA_ERROR
    return EXIT_INTERNAL_ERROR


def _policy_payload(policy: object, config_mode: str) -> dict[str, object]:
    """Read the real PrivacyPolicy attribute values into a plain mapping.

    Only attributes the real policy exposes are reported; when the policy
    has no ``mode`` attribute, the config's validated mode is used.
    """
    payload: dict[str, object] = {}
    for key in _POLICY_ATTRIBUTES:
        value = getattr(policy, key, None)
        if value is not None:
            payload[key] = value
    if "mode" not in payload:
        payload["mode"] = config_mode
    return payload


def _load_policy(json_mode: bool) -> tuple[Any, Any]:
    """Load the real config and the parallel privacy policy (fail closed)."""
    try:
        from humanhand.infra.config import load_config

        config = load_config()
    except Exception as exc:
        _report_error(message_for_exception(exc), EXIT_CONFIG_ERROR, json_mode)
    _require_module("humanhand.domain.privacy", json_mode)
    try:
        policy_loader = _require_module("humanhand.infra.privacy.policy_loader", json_mode)
        policy = policy_loader.privacy_policy_for_mode(config.privacy_mode)
    except Exception as exc:
        _report_error(message_for_exception(exc), EXIT_CONFIG_ERROR, json_mode)
    return config, policy


@privacy_app.command("show")
def privacy_show_cmd(
    ctx: typer.Context,
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
    """Show the effective privacy policy for the configured mode."""
    json_mode = _effective_flag(ctx, json_mode, "json_mode")
    no_color = _effective_flag(ctx, no_color, "no_color")
    config, policy = _load_policy(json_mode)
    payload = _policy_payload(policy, config.privacy_mode)
    if json_mode:
        _render_json({"status": "ok", **payload})
    else:
        for key in _POLICY_ATTRIBUTES:
            if key in payload:
                _render_text(f"{key}: {payload[key]}")


@privacy_app.command("doctor")
def privacy_doctor_cmd(
    ctx: typer.Context,
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
    """Run local privacy checks; findings are advisory (exit 0 with findings).

    Checks: mode validity (config fails closed on an unknown mode), cache
    configuration vs policy detector-cache expectation, project-dir
    initialization, and strict-local style vault presence. No network and
    no user text is touched.
    """
    json_mode = _effective_flag(ctx, json_mode, "json_mode")
    no_color = _effective_flag(ctx, no_color, "no_color")
    config, policy = _load_policy(json_mode)
    findings: list[dict[str, object]] = []

    policy_cache_enabled = getattr(policy, "detector_cache_enabled", None)
    if policy_cache_enabled is None:
        _report_error(
            "humanhand.domain.privacy contract mismatch: "
            "PrivacyPolicy has no detector_cache_enabled attribute",
            EXIT_CONFIG_ERROR,
            json_mode,
        )
    if bool(config.cache_enabled) is not bool(policy_cache_enabled):
        findings.append(
            {
                "code": "privacy.cache_policy_mismatch",
                "message": "cache configuration contradicts the privacy policy",
                "detail": (
                    f"config cache_enabled={config.cache_enabled}, "
                    f"policy detector_cache_enabled={policy_cache_enabled}"
                ),
            }
        )

    if config.project_dir:
        project_root = Path(config.project_dir)
        if not (project_root / ".humanhand" / "project.toml").is_file():
            findings.append(
                {
                    "code": "privacy.project_dir_uninitialized",
                    "message": "HUMANHAND_PROJECT_DIR is set but not an initialized project",
                    "detail": str(project_root),
                }
            )

    if config.privacy_mode == "strict_local":
        vault_decisions = Path(config.style_vault_dir) / "decisions.jsonl"
        if vault_decisions.is_file():
            findings.append(
                {
                    "code": "privacy.strict_local_style_vault",
                    "message": "style vault evidence exists outside strict-local scope",
                    "detail": str(vault_decisions),
                    "comment": (
                        "strict_local retains no rejected candidates and disables the "
                        "detector cache; a style vault holding raw originals and review "
                        "decisions is raw evidence retained outside strict scope"
                    ),
                }
            )

    if json_mode:
        _render_json({"status": "ok" if not findings else "findings", "findings": findings})
    else:
        if not findings:
            _render_text("privacy doctor: ok")
        else:
            _render_text("privacy doctor: findings")
            for finding in findings:
                _render_text(f"  {finding['code']}: {finding['message']} ({finding['detail']})")


@privacy_app.command("validate-project")
def privacy_validate_project_cmd(
    ctx: typer.Context,
    directory: str = typer.Argument(
        ...,
        help="Project root directory to validate.",
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
    """Validate a project directory layout without modifying anything.

    Checks that ``.humanhand/project.toml`` and ``.humanhand/project.db``
    (or ``project.db.bak``) exist and flags top-level entries outside the
    five layout directories (``.humanhand``, ``source``, ``style``,
    ``working``, ``exports``). Findings are advisory: exit 0 with
    ``status`` "findings"; a missing directory is an input error (exit 1).
    """
    json_mode = _effective_flag(ctx, json_mode, "json_mode")
    no_color = _effective_flag(ctx, no_color, "no_color")
    root = Path(directory)
    if not root.is_dir():
        _report_error(f"project directory not found: {root}", EXIT_INPUT_ERROR, json_mode)
    findings: list[dict[str, object]] = []

    project_toml = root / ".humanhand" / "project.toml"
    if not project_toml.is_file():
        findings.append(
            {
                "code": "privacy.project_missing_project_toml",
                "message": "missing .humanhand/project.toml",
                "detail": str(project_toml),
            }
        )

    database = root / ".humanhand" / "project.db"
    database_bak = root / ".humanhand" / "project.db.bak"
    if not database.is_file() and not database_bak.is_file():
        findings.append(
            {
                "code": "privacy.project_missing_database",
                "message": "missing .humanhand/project.db and .humanhand/project.db.bak",
                "detail": str(database),
            }
        )

    try:
        entries = sorted(root.iterdir(), key=lambda entry: entry.name)
    except OSError as exc:
        _report_error(message_for_exception(exc), EXIT_IO_ERROR, json_mode)
    for entry in entries:
        if entry.name in _LAYOUT_TOP_LEVEL_DIRS:
            continue
        kind = "file" if entry.is_file() else "directory"
        findings.append(
            {
                "code": "privacy.project_unexpected_entry",
                "message": "top-level entry is not owned by humanhand",
                "detail": f"{kind}: {entry.name}",
                "comment": (
                    "humanhand owns only .humanhand, source, style, working, and "
                    "exports at the project root"
                ),
            }
        )

    if json_mode:
        _render_json(
            {
                "status": "ok" if not findings else "findings",
                "root": str(root),
                "findings": findings,
            }
        )
    else:
        _render_text(f"Project validation: {root}")
        if not findings:
            _render_text("  status: ok")
        else:
            _render_text(f"  status: findings ({len(findings)})")
            for finding in findings:
                _render_text(
                    f"  finding: {finding['code']}: {finding['message']} ({finding['detail']})"
                )
