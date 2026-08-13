"""`humanhand style` sub-app — Style Fidelity Vault review and profiles."""

from __future__ import annotations

import json
import sys
from pathlib import Path
from typing import NoReturn

import typer

from humanhand.cli.errors import message_for_exception
from humanhand.domain.style_artifacts import StyleEvidencePackage
from humanhand.domain.style_authorship import AuthorshipClass
from humanhand.infra.files import FileIOError, file_size, read_bytes, read_head_bytes
from humanhand.infra.importers.pipeline import SandboxedImportInspector
from humanhand.infra.stores.style_vault import StyleVault

EXIT_INPUT_ERROR = 1
EXIT_CONFIG_ERROR = 2
EXIT_IO_ERROR = 3

style_app = typer.Typer(
    name="style",
    help="Style Fidelity Vault: review authorship, build profiles, compare.",
    no_args_is_help=True,
)


def _effective_flag(ctx: typer.Context | None, local_value: bool, key: str) -> bool:
    if local_value:
        return True
    if ctx is None or not isinstance(ctx.obj, dict):
        return False
    return bool(ctx.obj.get(key, False))


def _report_error(message: str, code: int, json_mode: bool) -> NoReturn:
    if json_mode:
        print(
            json.dumps({"status": "error", "message": message, "exit_code": code}, sort_keys=True)
        )
    else:
        print(f"error: {message}", file=sys.stderr)
    raise typer.Exit(code)


def _load_vault(json_mode: bool) -> StyleVault:
    try:
        from humanhand.infra.config import load_config

        config = load_config()
    except Exception as exc:
        _report_error(message_for_exception(exc), EXIT_CONFIG_ERROR, json_mode)
    try:
        return StyleVault(config.style_vault_dir)
    except OSError as exc:
        _report_error(message_for_exception(exc), EXIT_IO_ERROR, json_mode)


@style_app.command("review")
def style_review_cmd(
    ctx: typer.Context,
    import_id: str = typer.Argument(
        ...,
        help="Style package id (sty-...) to review.",
    ),
    approve: str = typer.Option(
        None,
        "--approve",
        help="Authorship class to assign (see --help classes).",
    ),
    span: str = typer.Option(
        None,
        "--span",
        help="Span id to decide; when omitted, --approve applies to all unresolved spans.",
    ),
    exclude: bool = typer.Option(
        False,
        "--exclude",
        help="With --span, exclude that span from the voice profile instead of classifying it.",
    ),
    reason: str = typer.Option(
        None,
        "--reason",
        help="Recorded reason for an exclusion (with --exclude).",
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
    """Review authorship spans of a stored style package.

    Without --approve, prints the review state. With --approve <class>,
    records an explicit decision for the given span (or all unresolved
    spans) into the append-only decision log. Decisions are never
    inferred automatically.
    """
    json_mode = _effective_flag(ctx, json_mode, "json_mode")
    no_color = _effective_flag(ctx, no_color, "no_color")
    vault = _load_vault(json_mode)

    from humanhand.application.style_services import (
        load_effective_package,
        record_review_decision,
    )
    from humanhand.cli.output import render_style_review

    try:
        package = load_effective_package(package_id=import_id, vault=vault)
    except Exception as exc:
        _report_error(message_for_exception(exc), EXIT_INPUT_ERROR, json_mode)

    if approve is not None or exclude:
        if exclude and span is None:
            _report_error("--exclude requires --span", EXIT_INPUT_ERROR, json_mode)
        if exclude and approve is None:
            _report_error(
                "--exclude requires --approve (use --approve exclude)", EXIT_INPUT_ERROR, json_mode
            )
        try:
            authorship_class = AuthorshipClass(approve or "exclude")
        except ValueError:
            _report_error(f"Unknown authorship class: {approve}", EXIT_INPUT_ERROR, json_mode)
        if authorship_class is AuthorshipClass.UNKNOWN:
            _report_error(
                "Unknown authorship cannot be recorded as a resolved decision",
                EXIT_INPUT_ERROR,
                json_mode,
            )
        if span is not None and exclude:
            authorship_class = AuthorshipClass.EXCLUDE
        target_ids = (
            [span]
            if span is not None
            else [item.span_id for item in package.authorship.unresolved_spans]
        )
        if not target_ids:
            _report_error("No unresolved spans to decide", EXIT_INPUT_ERROR, json_mode)
        for span_id in target_ids:
            try:
                result = record_review_decision(
                    package=package,
                    span_id=span_id,
                    authorship_class=authorship_class,
                    vault=vault,
                    reason=reason,
                )
            except KeyError:
                _report_error(f"Unknown span id: {span_id}", EXIT_INPUT_ERROR, json_mode)
            except Exception as exc:
                _report_error(message_for_exception(exc), EXIT_INPUT_ERROR, json_mode)
            package = result.package
        render_style_review(package, json_mode=json_mode, no_color=no_color)
        return

    render_style_review(package, json_mode=json_mode, no_color=no_color)


def _profile_packages(
    vault: StyleVault, profile_id: str, json_mode: bool
) -> tuple[StyleEvidencePackage, ...]:
    from humanhand.application.style_services import packages_for_label

    try:
        return packages_for_label(vault.list_packages(), vault, profile_id)
    except Exception as exc:
        _report_error(message_for_exception(exc), EXIT_INPUT_ERROR, json_mode)


@style_app.command("profile")
def style_profile_cmd(
    ctx: typer.Context,
    profile_id: str = typer.Argument(
        ...,
        help="Profile label used at import time (import style --profile).",
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
    """Build the deterministic style evidence profile for a label."""
    json_mode = _effective_flag(ctx, json_mode, "json_mode")
    no_color = _effective_flag(ctx, no_color, "no_color")
    vault = _load_vault(json_mode)
    packages = _profile_packages(vault, profile_id, json_mode)

    from humanhand.cli.output import render_style_profile
    from humanhand.domain.style_profiles import build_profile

    try:
        profile = build_profile(profile_id=profile_id, packages=packages)
    except Exception as exc:
        _report_error(message_for_exception(exc), EXIT_INPUT_ERROR, json_mode)
    render_style_profile(profile, json_mode=json_mode, no_color=no_color)


@style_app.command("coverage")
def style_coverage_cmd(
    ctx: typer.Context,
    profile_id: str = typer.Argument(
        ...,
        help="Profile label to report coverage for.",
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
    """Report evidence coverage for a profile label."""
    json_mode = _effective_flag(ctx, json_mode, "json_mode")
    no_color = _effective_flag(ctx, no_color, "no_color")
    vault = _load_vault(json_mode)
    packages = _profile_packages(vault, profile_id, json_mode)

    from humanhand.cli.output import render_style_coverage
    from humanhand.domain.style_profiles import build_profile

    try:
        profile = build_profile(profile_id=profile_id, packages=packages)
    except Exception as exc:
        _report_error(message_for_exception(exc), EXIT_INPUT_ERROR, json_mode)
    render_style_coverage(profile.coverage, json_mode=json_mode, no_color=no_color)


@style_app.command("invariants")
def style_invariants_cmd(
    ctx: typer.Context,
    profile_id: str = typer.Argument(
        ...,
        help="Profile label to list invariants for.",
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
    """List the hard invariants and soft tendencies of a profile."""
    json_mode = _effective_flag(ctx, json_mode, "json_mode")
    no_color = _effective_flag(ctx, no_color, "no_color")
    vault = _load_vault(json_mode)
    packages = _profile_packages(vault, profile_id, json_mode)

    from humanhand.cli.output import render_style_invariants
    from humanhand.domain.style_profiles import build_profile

    try:
        profile = build_profile(profile_id=profile_id, packages=packages)
    except Exception as exc:
        _report_error(message_for_exception(exc), EXIT_INPUT_ERROR, json_mode)
    render_style_invariants(profile, json_mode=json_mode, no_color=no_color)


@style_app.command("compare")
def style_compare_cmd(
    ctx: typer.Context,
    profile_id: str = typer.Argument(
        ...,
        help="Profile label to compare against.",
    ),
    document: str = typer.Argument(
        ...,
        help="Path to the document to compare (any supported format).",
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
    """Compare a document against a profile without concluding authorship."""
    json_mode = _effective_flag(ctx, json_mode, "json_mode")
    no_color = _effective_flag(ctx, no_color, "no_color")
    vault = _load_vault(json_mode)
    packages = _profile_packages(vault, profile_id, json_mode)

    from humanhand.cli.output import render_style_comparison
    from humanhand.domain.style_profiles import build_profile

    try:
        profile = build_profile(profile_id=profile_id, packages=packages)
    except Exception as exc:
        _report_error(message_for_exception(exc), EXIT_INPUT_ERROR, json_mode)

    from humanhand.domain.import_findings import ImportStatus
    from humanhand.domain.import_policy import ImportPolicy

    policy = ImportPolicy(lane="style")
    try:
        from humanhand.application.import_services import inspect_import

        class _Reader:
            def size_bytes(self, path: str | Path) -> int:
                return file_size(path)

            def read_head(self, path: str | Path, max_bytes: int) -> bytes:
                return read_head_bytes(path, max_bytes)

            def read_bytes(self, path: str | Path) -> bytes:
                return read_bytes(path)

        result = inspect_import(
            path=document,
            policy=policy,
            reader=_Reader(),
            inspector=SandboxedImportInspector(),
        )
    except FileIOError as exc:
        _report_error(message_for_exception(exc), EXIT_IO_ERROR, json_mode)
    except Exception as exc:
        _report_error(message_for_exception(exc), EXIT_INPUT_ERROR, json_mode)

    from humanhand.domain.style_compare import compare_profile

    if result.inspection.status not in {ImportStatus.OK, ImportStatus.FINDINGS}:
        _report_error(
            f"Document import requires review: {result.inspection.status.value}",
            EXIT_INPUT_ERROR,
            json_mode,
        )
    if result.inspection.document is None:
        _report_error(
            f"Document import failed: {result.inspection.status.value}",
            EXIT_INPUT_ERROR,
            json_mode,
        )
    report = compare_profile(profile, result.inspection.document)
    render_style_comparison(report, json_mode=json_mode, no_color=no_color)
