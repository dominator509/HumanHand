"""`humanhand import` sub-app — clean-room import inspection (EP-012)."""

from __future__ import annotations

import json
import sys
import time
from pathlib import Path
from typing import NoReturn

import typer

from humanhand.application.import_services import (
    build_import_policy,
    import_source_package,
    import_style_package,
    inspect_import,
)
from humanhand.cli.errors import message_for_exception
from humanhand.cli.output import (
    render_import_inspection,
    render_source_import_result,
    render_style_import_result,
)
from humanhand.domain.import_policy import LANES, ImportPolicy
from humanhand.domain.types import DomainError
from humanhand.infra.config import Config
from humanhand.infra.files import FileIOError, file_size, read_bytes, read_head_bytes
from humanhand.infra.importers.pipeline import SandboxedImportInspector

# Exit codes and the JSONL logger live in app.py; importing them at module
# top would create an import cycle (app.py registers this sub-app), so the
# logger is resolved lazily inside the command, by which point app.py is
# fully loaded. The exit-code constants are duplicated here deliberately.
EXIT_INPUT_ERROR = 1
EXIT_CONFIG_ERROR = 2
EXIT_IO_ERROR = 3

import_app = typer.Typer(
    name="import",
    help="Clean-room import: inspect, and source/style lane packages.",
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


class _CliImportReader:
    """Wire the import file-reader port to infra file helpers."""

    def size_bytes(self, path: str | Path) -> int:
        return file_size(path)

    def read_head(self, path: str | Path, max_bytes: int) -> bytes:
        return read_head_bytes(path, max_bytes)

    def read_bytes(self, path: str | Path) -> bytes:
        return read_bytes(path)


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


@import_app.command("inspect")
def inspect_cmd(
    ctx: typer.Context,
    path: str = typer.Argument(
        ...,
        help="Path to the file to inspect (TXT, Markdown, DOCX, PDF, HTML, RTF, ODT).",
    ),
    lane: str = typer.Option(
        "source",
        "--lane",
        help="Import lane: source or style.",
    ),
    content: bool = typer.Option(
        False,
        "--content",
        help="Include canonical document content in JSON output.",
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
    """Inspect a file without parsing it in this process and without network access.

    All content parsing happens inside a bounded parser worker (ADR-004).
    Unsafe content fails closed with findings instead of being executed.
    """
    json_mode = _effective_flag(ctx, json_mode, "json_mode")
    no_color = _effective_flag(ctx, no_color, "no_color")

    # Lazy import to avoid the app.py <-> import_commands cycle at load time.
    from humanhand.cli.app import _CliLogger

    logger = _CliLogger()
    started_at = time.monotonic()

    if lane not in LANES:
        logger.log("import.error", level="error", message="invalid lane", lane=lane)
        _report_error(f"Invalid lane: {lane}", EXIT_INPUT_ERROR, json_mode)

    try:
        from humanhand.infra.config import load_config

        config = load_config()
    except Exception as exc:
        logger.log("import.error", level="error", message="config load failed")
        _report_error(message_for_exception(exc), EXIT_CONFIG_ERROR, json_mode)

    try:
        policy = build_import_policy(
            lane=lane,
            max_bytes=config.import_max_bytes,
            max_expanded_bytes=config.import_max_expanded_bytes,
            max_nodes=config.import_max_nodes,
            timeout_seconds=config.import_timeout_seconds,
        )
    except Exception as exc:
        logger.log("import.error", level="error", message="policy build failed")
        _report_error(message_for_exception(exc), EXIT_INPUT_ERROR, json_mode)

    logger.log("import.start", level="info", message="import inspection started", lane=lane)
    try:
        result = inspect_import(
            path=path,
            policy=policy,
            reader=_CliImportReader(),
            inspector=SandboxedImportInspector(),
        )
    except FileIOError as exc:
        logger.log("import.error", level="error", message="file read failed")
        _report_error(message_for_exception(exc), EXIT_IO_ERROR, json_mode)

    inspection = result.inspection
    render_import_inspection(
        inspection,
        json_mode=json_mode,
        no_color=no_color,
        include_content=content,
    )
    logger.log(
        "import.end",
        level="info",
        message="import inspection completed",
        lane=lane,
        status=inspection.status.value,
        finding_count=len(inspection.findings),
        elapsed_ms=round((time.monotonic() - started_at) * 1000, 1),
    )


def _lane_policy(config: Config, lane: str) -> ImportPolicy:
    """Build a validated lane policy from resolved configuration values."""
    return build_import_policy(
        lane=lane,
        max_bytes=config.import_max_bytes,
        max_expanded_bytes=config.import_max_expanded_bytes,
        max_nodes=config.import_max_nodes,
        timeout_seconds=config.import_timeout_seconds,
    )


@import_app.command("source")
def import_source_cmd(
    ctx: typer.Context,
    path: str = typer.Argument(
        ...,
        help="Path to the AI/source document to import (any supported format).",
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
    """Import a source document and build a source package with fact evidence.

    Source facts (quotations, citations, protected spans) stay in the
    source lane and never cross into style evidence (ADR-002). All content
    parsing happens inside the bounded parser worker.
    """
    json_mode = _effective_flag(ctx, json_mode, "json_mode")
    no_color = _effective_flag(ctx, no_color, "no_color")

    from humanhand.cli.app import _CliLogger

    logger = _CliLogger()
    started_at = time.monotonic()

    try:
        from humanhand.infra.config import load_config

        config = load_config()
    except Exception as exc:
        logger.log("import.source.error", level="error", message="config load failed")
        _report_error(message_for_exception(exc), EXIT_CONFIG_ERROR, json_mode)

    try:
        policy = _lane_policy(config, "source")
    except Exception as exc:
        logger.log("import.source.error", level="error", message="policy build failed")
        _report_error(message_for_exception(exc), EXIT_INPUT_ERROR, json_mode)

    logger.log("import.source.start", level="info", message="source import started")
    try:
        result = import_source_package(
            path=path,
            policy=policy,
            reader=_CliImportReader(),
            inspector=SandboxedImportInspector(),
        )
    except FileIOError as exc:
        logger.log("import.source.error", level="error", message="file read failed")
        _report_error(message_for_exception(exc), EXIT_IO_ERROR, json_mode)
    except DomainError as exc:
        logger.log("import.source.error", level="error", message="source import failed")
        _report_error(message_for_exception(exc), EXIT_INPUT_ERROR, json_mode)

    render_source_import_result(result, json_mode=json_mode, no_color=no_color)
    logger.log(
        "import.source.end",
        level="info",
        message="source import completed",
        status=result.inspection.status.value,
        package_id=result.package.package_id if result.package is not None else None,
        elapsed_ms=round((time.monotonic() - started_at) * 1000, 1),
    )


@import_app.command("style")
def import_style_cmd(
    ctx: typer.Context,
    path: str = typer.Argument(
        ...,
        help="Path to the human style sample document to import (any supported format).",
    ),
    profile: str = typer.Option(
        "default",
        "--profile",
        help="Profile label for the Style Fidelity Vault.",
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
    """Import a human style sample and build a style package with no fact evidence.

    Style packages structurally cannot carry quotations, citations, or
    protected spans; style-sample facts never enter the project fact graph
    (ADR-002). All content parsing happens inside the bounded parser worker.
    """
    json_mode = _effective_flag(ctx, json_mode, "json_mode")
    no_color = _effective_flag(ctx, no_color, "no_color")

    from humanhand.cli.app import _CliLogger

    logger = _CliLogger()
    started_at = time.monotonic()

    try:
        from humanhand.infra.config import load_config

        config = load_config()
    except Exception as exc:
        logger.log("import.style.error", level="error", message="config load failed")
        _report_error(message_for_exception(exc), EXIT_CONFIG_ERROR, json_mode)

    try:
        policy = _lane_policy(config, "style")
    except Exception as exc:
        logger.log("import.style.error", level="error", message="policy build failed")
        _report_error(message_for_exception(exc), EXIT_INPUT_ERROR, json_mode)

    logger.log("import.style.start", level="info", message="style import started")
    try:
        raw = _CliImportReader().read_bytes(path)
        result = import_style_package(
            path=path,
            policy=policy,
            reader=_CliImportReader(),
            inspector=SandboxedImportInspector(),
            raw_override=raw,
        )
    except FileIOError as exc:
        logger.log("import.style.error", level="error", message="file read failed")
        _report_error(message_for_exception(exc), EXIT_IO_ERROR, json_mode)
    except DomainError as exc:
        logger.log("import.style.error", level="error", message="style import failed")
        _report_error(message_for_exception(exc), EXIT_INPUT_ERROR, json_mode)

    # Persist style evidence into the Style Fidelity Vault (EP-014). The
    # vault package id is <style-package-id>@<profile-label> so the same
    # sample can belong to several profiles without id collisions.
    vault_package_id: str | None = None
    if result.package is not None:
        from humanhand.application.style_services import build_style_evidence_package
        from humanhand.infra.stores.style_vault import StyleVault, StyleVaultError

        try:
            document = result.inspection.document
            if document is None:
                _report_error(
                    "Style package has no canonical document",
                    EXIT_INPUT_ERROR,
                    json_mode,
                )
            vault = StyleVault(config.style_vault_dir)
            evidence_package = build_style_evidence_package(
                inspection=result.inspection,
                raw=raw,
                vault=vault,
                profile_label=profile,
                parser_version=f"{document.parser_name}-{document.parser_version}",
                package_id=f"{result.package.package_id}@{profile}",
            )
            vault_package_id = evidence_package.package_id
        except (DomainError, OSError, StyleVaultError) as exc:
            logger.log("import.style.error", level="error", message="vault persist failed")
            _report_error(message_for_exception(exc), EXIT_IO_ERROR, json_mode)

    render_style_import_result(
        result, json_mode=json_mode, no_color=no_color, vault_package_id=vault_package_id
    )
    logger.log(
        "import.style.end",
        level="info",
        message="style import completed",
        status=result.inspection.status.value,
        package_id=result.package.package_id if result.package is not None else None,
        vault_package_id=vault_package_id,
        elapsed_ms=round((time.monotonic() - started_at) * 1000, 1),
    )
