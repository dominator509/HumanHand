"""Typer CLI application — command definitions and wiring."""

from __future__ import annotations

import contextlib
import json
import os
import sys
import time
from datetime import UTC, datetime
from pathlib import Path
from typing import NoReturn

import typer

from humanhand import __version__
from humanhand.application.ports import Logger
from humanhand.application.services import (
    RewriteQualityError,
    diff_facts_service,
    rewrite,
    scrub_service,
    verify,
)
from humanhand.cli.audit_commands import audit_app
from humanhand.cli.beacon_commands import beacon_app
from humanhand.cli.context_commands import context_app
from humanhand.cli.errors import error_for_exception, get_error_message, message_for_exception
from humanhand.cli.export_commands import export_app
from humanhand.cli.finalization_commands import finalize_app
from humanhand.cli.import_commands import import_app
from humanhand.cli.output import (
    render_diff_facts_result,
    render_health,
    render_rewrite_result,
    render_scrub_result,
    render_verify_result,
)
from humanhand.cli.privacy_commands import privacy_app
from humanhand.cli.project_commands import project_app
from humanhand.cli.scanner_commands import scanner_app
from humanhand.cli.style_commands import style_app
from humanhand.infra.cache import DetectorScoreCache
from humanhand.infra.config import Config, load_config
from humanhand.infra.counters import Counters, emit_counters
from humanhand.infra.detectors import create_detector
from humanhand.infra.detectors.base import DetectorError, ProviderUnavailableError
from humanhand.infra.files import FileIOError, read_text_strict
from humanhand.infra.http import HttpError, validate_endpoint
from humanhand.infra.llm import LlmError, OpenAiLlmClient
from humanhand.infra.logging import redact_value
from humanhand.infra.privacy.null_logger import NullLogger

app = typer.Typer(
    name="humanhand",
    help="Privacy-preserving CLI for rewriting AI-assisted text into human style.",
    no_args_is_help=True,
)

app.add_typer(import_app, name="import")
app.add_typer(style_app, name="style")
app.add_typer(project_app, name="project")
app.add_typer(context_app, name="context")
app.add_typer(privacy_app, name="privacy")
app.add_typer(export_app, name="export")
app.add_typer(audit_app, name="audit")
app.add_typer(finalize_app, name="finalize")
app.add_typer(beacon_app, name="beacon")
app.add_typer(scanner_app, name="scanner")


# ── Exit codes ──────────────────────────────────────────────────

EXIT_OK = 0
EXIT_INPUT_ERROR = 1
EXIT_CONFIG_ERROR = 2
EXIT_IO_ERROR = 3
EXIT_EXTERNAL_ERROR = 4
EXIT_SCHEMA_ERROR = 5
EXIT_INTERNAL_ERROR = 6


# ── Helpers ─────────────────────────────────────────────────────


class _CliLogger:
    """Emit structured JSONL logs to stderr."""

    def __init__(self, counters: Counters | None = None) -> None:
        self._counters = counters

    def _record_counters(
        self,
        event: str,
        *,
        elapsed_ms: object,
        input_length: object,
        output_length: object,
        cache_hit: object,
        retry_reason: object,
        repair_attempts: object,
    ) -> None:
        """Capture command-scoped counters from structured log events."""
        if self._counters is None:
            return

        if isinstance(elapsed_ms, int | float):
            self._counters.set("duration_ms", elapsed_ms)
        if isinstance(input_length, int | float):
            self._counters.set("input_chars", input_length)
        if isinstance(output_length, int | float):
            self._counters.set("output_chars", output_length)
        if isinstance(repair_attempts, int | float):
            self._counters.set("repair_attempts", repair_attempts)

        if event in {"rewrite.end", "rewrite.fail"}:
            self._counters.increment("rewrite_attempts")

        if event == "verify.end":
            if cache_hit is True:
                self._counters.increment("cache_hits")
            elif cache_hit is False:
                self._counters.increment("cache_misses")
                self._counters.increment("detector_calls")

        if retry_reason:
            self._counters.increment("retry_count")

    def log(self, event: str, level: str = "info", **fields: object) -> None:
        elapsed_ms = fields.pop("elapsed_ms", None)
        model = fields.pop("model", None)
        endpoint_host = fields.pop("endpoint_host", None)
        input_length = fields.pop("input_length", None)
        output_length = fields.pop("output_length", None)
        sha256_prefix = fields.pop("sha256_prefix", None)
        cache_hit = fields.pop("cache_hit", None)
        attempt = fields.pop("attempt", None)
        retry_reason = fields.pop("retry_reason", None)
        repair_attempts = fields.get("repair_attempts")

        payload: dict[str, object] = {
            "timestamp": datetime.now(UTC).isoformat().replace("+00:00", "Z"),
            "level": level,
            "event": event,
            "message": str(redact_value(fields.pop("message", event.replace(".", " ")))),
            "elapsed_ms": elapsed_ms,
            "model": model,
            "endpoint_host": endpoint_host,
            "input_length": input_length,
            "output_length": output_length,
            "sha256_prefix": sha256_prefix,
            "cache_hit": cache_hit,
            "attempt": attempt,
            "retry_reason": retry_reason,
        }

        for key, value in sorted(fields.items()):
            safe_value = redact_value(value, key=key)
            if safe_value is None or isinstance(
                safe_value,
                str | int | float | bool | list | dict,
            ):
                payload[key] = safe_value
            else:
                payload[key] = str(safe_value)

        self._record_counters(
            event,
            elapsed_ms=elapsed_ms,
            input_length=input_length,
            output_length=output_length,
            cache_hit=cache_hit,
            retry_reason=retry_reason,
            repair_attempts=repair_attempts,
        )

        print(json.dumps(payload, separators=(",", ":"), sort_keys=True), file=sys.stderr)


def _privacy_aware_logger(
    counters: Counters, privacy_mode: str | None = None
) -> tuple[Logger, bool]:
    """Return the configured logger and whether counter emission is permitted."""
    mode = privacy_mode or os.getenv("HUMANHAND_PRIVACY_MODE") or "private_audited"
    if mode.strip().lower() == "strict_local":
        return NullLogger(), False
    return _CliLogger(counters), True


def _error_json(message: str, code: int) -> NoReturn:
    """Print a JSON error and exit."""
    print(json.dumps({"status": "error", "message": message, "exit_code": code}))
    raise typer.Exit(code)


def _error_text(message: str, code: int) -> NoReturn:
    """Print a one-line error to stderr and exit."""
    print(f"error: {message}", file=sys.stderr)
    raise typer.Exit(code)


def _report_error(
    message: str,
    code: int,
    json_mode: bool,
    *,
    logger: Logger | None = None,
    event: str | None = None,
) -> NoReturn:
    """Dispatch error to JSON or text mode."""
    if logger is not None and event is not None:
        logger.log(event, level="error", message="command failed", exit_code=code)
    if json_mode:
        _error_json(message, code)
    else:
        _error_text(message, code)


def _require_path(path: str | None, name: str, json_mode: bool) -> str:
    """Validate that a required path argument is present."""
    if not path:
        _report_error(f"Missing required argument: {name}", EXIT_INPUT_ERROR, json_mode)
    return path


def _output_matches_input(output_path: str, *input_paths: str) -> bool:
    """Return True when an output path resolves to one of the provided inputs."""
    try:
        resolved_output = Path(output_path).resolve()
    except OSError:
        return False

    for input_path in input_paths:
        if input_path == "-":
            continue
        try:
            if resolved_output == Path(input_path).resolve():
                return True
        except OSError:
            continue

    return False


def _validate_existing_file_path(path: str) -> None:
    """Validate path existence/type without reading file contents."""
    candidate = Path(path)
    if not candidate.exists():
        raise FileIOError(f"File not found: {candidate}")
    if not candidate.is_file():
        raise FileIOError(f"Not a regular file: {candidate}")


def _effective_flag(ctx: typer.Context | None, local_value: bool, key: str) -> bool:
    """Resolve a command flag from local options plus root-level callback state."""
    if local_value:
        return True
    if ctx is None or not isinstance(ctx.obj, dict):
        return False
    return bool(ctx.obj.get(key, False))


# ── Callback ────────────────────────────────────────────────────


def version_callback(value: bool) -> None:
    if value:
        print(f"humanhand {__version__}")
        raise typer.Exit()


@app.callback()
def main(
    ctx: typer.Context,
    version: bool = typer.Option(
        False,
        "--version",
        "-V",
        callback=version_callback,
        is_eager=True,
        help="Show version and exit.",
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
    """Human Hand CLI — rewrite AI-assisted text into human style."""
    inherited_flags = ctx.obj if isinstance(ctx.obj, dict) else {}
    ctx.obj = {
        **inherited_flags,
        "json_mode": json_mode,
        "no_color": no_color,
    }


# ── Commands ────────────────────────────────────────────────────


@app.command(name="health")
def health_cmd(
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
    """Check CLI health without network calls or user text."""
    json_mode = _effective_flag(ctx, json_mode, "json_mode")
    no_color = _effective_flag(ctx, no_color, "no_color")
    counters = Counters()
    logger, emit_metrics = _privacy_aware_logger(counters)
    started_at = time.monotonic()
    completed = False
    try:
        logger.log("health.start", level="info", message="health check started")

        config_valid = True
        config_error: str | None = None
        try:
            config = load_config()
        except Exception as exc:
            config = Config()
            config_valid = False
            config_error = type(exc).__name__

        logger, emit_metrics = _privacy_aware_logger(counters, config.privacy_mode)

        # Check cache dir writability (only meaningful when cache is enabled)
        cache_dir_writable: bool | None = None
        if config.privacy_mode != "strict_local" and config.cache_enabled and config.cache_dir:
            cache_path = Path(config.cache_dir)
            try:
                cache_path.mkdir(parents=True, exist_ok=True)
                test_file = cache_path / ".health_check"
                test_file.touch()
                test_file.unlink()
                cache_dir_writable = True
            except (OSError, PermissionError):
                cache_dir_writable = False

        # Check endpoint URL validity under the same local safety rules
        # enforced by the LLM client, but without making a network call.
        endpoint_url_valid: bool | None = None
        if config.llm_base_url:
            try:
                validate_endpoint(config.llm_base_url, config.allow_insecure)
                endpoint_url_valid = True
            except HttpError:
                endpoint_url_valid = False

        render_health(
            config,
            json_mode=json_mode,
            config_valid=config_valid,
            config_error=config_error,
            no_color=no_color,
            cache_dir_writable=cache_dir_writable,
            endpoint_url_valid=endpoint_url_valid,
        )
        logger.log(
            "health.end",
            level="info",
            message="health check completed",
            config_valid=config_valid,
            elapsed_ms=round((time.monotonic() - started_at) * 1000, 1),
        )
        completed = True
    finally:
        if completed and counters and emit_metrics:
            emit_counters(counters)


@app.command(name="rewrite")
def rewrite_cmd(
    ctx: typer.Context,
    source: str = typer.Option(
        ...,
        "--source",
        help="Path to AI-assisted source text file, or '-' for stdin.",
    ),
    style: str = typer.Option(
        ...,
        "--style",
        help="Path to human writing sample file.",
    ),
    out: str = typer.Option(
        ...,
        "--out",
        help="Path for the rewritten output file.",
    ),
    json_mode: bool = typer.Option(
        False,
        "--json",
        help="Output JSON to stdout only.",
    ),
    print_output: bool = typer.Option(
        False,
        "--print",
        help="Print generated prose to stdout (text mode only).",
    ),
    no_color: bool = typer.Option(
        False,
        "--no-color",
        help="Disable color output.",
    ),
) -> None:
    """Rewrite AI-assisted text to match a human writing style."""
    json_mode = _effective_flag(ctx, json_mode, "json_mode")
    no_color = _effective_flag(ctx, no_color, "no_color")
    counters = Counters()
    logger, emit_metrics = _privacy_aware_logger(counters)
    completed = False
    try:
        if json_mode and print_output:
            _report_error(
                "--print cannot be combined with --json",
                EXIT_INPUT_ERROR,
                json_mode,
                logger=logger,
                event="rewrite.error",
            )

        try:
            config = load_config()
        except Exception as exc:
            _report_error(
                message_for_exception(exc),
                EXIT_CONFIG_ERROR,
                json_mode,
                logger=logger,
                event="rewrite.error",
            )

        logger, emit_metrics = _privacy_aware_logger(counters, config.privacy_mode)
        if config.privacy_mode == "strict_local":
            _report_error(
                "strict_local privacy mode forbids network-backed rewrite",
                EXIT_CONFIG_ERROR,
                json_mode,
                logger=logger,
                event="rewrite.error",
            )

        # Validate cheap path-only errors before live config so they do not
        # get masked by missing endpoint/model configuration.
        try:
            if source != "-":
                _validate_existing_file_path(source)
            _validate_existing_file_path(style)
        except FileIOError as exc:
            _report_error(
                message_for_exception(exc),
                EXIT_IO_ERROR,
                json_mode,
                logger=logger,
                event="rewrite.error",
            )

        if _output_matches_input(out, source, style):
            _report_error(
                message_for_exception(FileIOError("Output path must not match an input path")),
                EXIT_IO_ERROR,
                json_mode,
                logger=logger,
                event="rewrite.error",
            )

        # Fail fast on LLM configuration before reading user text.
        try:
            llm_client = OpenAiLlmClient(config)
        except LlmError as exc:
            error_key = error_for_exception(exc)
            _report_error(
                get_error_message(error_key),
                EXIT_CONFIG_ERROR
                if error_key in {"missing_llm_url", "missing_llm_model"}
                else EXIT_EXTERNAL_ERROR,
                json_mode,
                logger=logger,
                event="rewrite.error",
            )

        try:
            # Read source file
            source_text = sys.stdin.read() if source == "-" else read_text_strict(source)
        except FileIOError as exc:
            _report_error(
                message_for_exception(exc),
                EXIT_IO_ERROR,
                json_mode,
                logger=logger,
                event="rewrite.error",
            )

        # Read style file
        try:
            style_text = read_text_strict(style)
        except FileIOError as exc:
            _report_error(
                message_for_exception(exc),
                EXIT_IO_ERROR,
                json_mode,
                logger=logger,
                event="rewrite.error",
            )

        # Wire up a simple file writer
        from humanhand.infra.files import write_clean_text

        class _CliFileWriter:
            def write(
                self,
                output_path: str,
                text: str,
                input_paths: list[str | Path] | None = None,
            ) -> str:
                return str(write_clean_text(output_path, text, input_paths))

        try:
            result = rewrite(
                source_text=source_text,
                style_text=style_text,
                output_path=out,
                llm_client=llm_client,
                file_writer=_CliFileWriter(),
                logger=logger,
                max_chars=config.max_chars,
                seed=config.seed,
            )
        except ValueError as exc:
            _report_error(
                message_for_exception(exc),
                EXIT_INPUT_ERROR,
                json_mode,
                logger=logger,
                event="rewrite.error",
            )
        except RewriteQualityError as exc:
            _report_error(
                message_for_exception(exc),
                EXIT_SCHEMA_ERROR,
                json_mode,
                logger=logger,
                event="rewrite.error",
            )
        except LlmError as exc:
            _report_error(
                message_for_exception(exc),
                EXIT_EXTERNAL_ERROR,
                json_mode,
                logger=logger,
                event="rewrite.error",
            )

        if print_output:
            # In print mode, stdout should contain only the generated prose.
            try:
                output_text = read_text_strict(out)
                sys.stdout.write(output_text)
            except FileIOError as exc:
                _report_error(
                    message_for_exception(exc),
                    EXIT_IO_ERROR,
                    json_mode,
                    logger=logger,
                    event="rewrite.error",
                )
            completed = True
            return

        render_rewrite_result(result, json_mode=json_mode, no_color=no_color)
        completed = True
    finally:
        if completed and counters and emit_metrics:
            emit_counters(counters)


@app.command(name="verify")
def verify_cmd(
    ctx: typer.Context,
    output: str = typer.Argument(
        ...,
        help="Path to the output file to verify.",
    ),
    provider: str = typer.Option(
        "local",
        "--provider",
        help="Detector provider name (default: local).",
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
    """Check if text is AI-generated using a detector or local heuristic."""
    json_mode = _effective_flag(ctx, json_mode, "json_mode")
    no_color = _effective_flag(ctx, no_color, "no_color")
    counters = Counters()
    logger, emit_metrics = _privacy_aware_logger(counters)
    completed = False
    try:
        try:
            config = load_config()
        except Exception as exc:
            _report_error(
                message_for_exception(exc),
                EXIT_CONFIG_ERROR,
                json_mode,
                logger=logger,
                event="verify.error",
            )

        logger, emit_metrics = _privacy_aware_logger(counters, config.privacy_mode)
        if config.privacy_mode == "strict_local" and provider != "local":
            _report_error(
                "strict_local privacy mode permits only the local detector",
                EXIT_CONFIG_ERROR,
                json_mode,
                logger=logger,
                event="verify.error",
            )

        # Read the output file
        try:
            text = read_text_strict(output)
        except FileIOError as exc:
            _report_error(
                message_for_exception(exc),
                EXIT_IO_ERROR,
                json_mode,
                logger=logger,
                event="verify.error",
            )

        # Create detector
        try:
            detector = create_detector(provider)
        except ValueError as exc:
            _report_error(
                message_for_exception(exc),
                EXIT_CONFIG_ERROR,
                json_mode,
                logger=logger,
                event="verify.error",
            )

        # Create cache if enabled
        cache = None
        cache_enabled = config.cache_enabled and config.privacy_mode != "strict_local"
        if cache_enabled:
            with contextlib.suppress(Exception):
                cache = DetectorScoreCache(config.cache_dir)

        try:
            result = verify(
                text=text,
                detector_client=detector,
                cache=cache,
                logger=logger,
                provider=provider,
                model="heuristic" if provider == "local" else provider,
                cache_enabled=cache_enabled and cache is not None,
            )
        except ProviderUnavailableError as exc:
            _report_error(
                message_for_exception(exc),
                EXIT_EXTERNAL_ERROR,
                json_mode,
                logger=logger,
                event="verify.error",
            )
        except DetectorError as exc:
            _report_error(
                message_for_exception(exc),
                EXIT_EXTERNAL_ERROR,
                json_mode,
                logger=logger,
                event="verify.error",
            )
        finally:
            if cache is not None:
                cache.close()

        render_verify_result(result, json_mode=json_mode, no_color=no_color)
        completed = True
    finally:
        if completed and counters and emit_metrics:
            emit_counters(counters)


@app.command(name="diff-facts")
def diff_facts_cmd(
    ctx: typer.Context,
    ai_source: str = typer.Argument(
        ...,
        help="Path to the original AI-generated source file.",
    ),
    output: str = typer.Argument(
        ...,
        help="Path to the rewritten output file to compare.",
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
    """Compare factual anchors between source and rewritten text."""
    json_mode = _effective_flag(ctx, json_mode, "json_mode")
    no_color = _effective_flag(ctx, no_color, "no_color")
    counters = Counters()
    logger, emit_metrics = _privacy_aware_logger(counters)
    completed = False
    try:
        # Read source
        try:
            source_text = read_text_strict(ai_source)
        except FileIOError as exc:
            _report_error(
                message_for_exception(exc),
                EXIT_IO_ERROR,
                json_mode,
                logger=logger,
                event="diff_facts.error",
            )

        # Read output
        try:
            candidate_text = read_text_strict(output)
        except FileIOError as exc:
            _report_error(
                message_for_exception(exc),
                EXIT_IO_ERROR,
                json_mode,
                logger=logger,
                event="diff_facts.error",
            )

        result = diff_facts_service(
            source_text=source_text,
            candidate_text=candidate_text,
            logger=logger,
        )

        render_diff_facts_result(result, json_mode=json_mode, no_color=no_color)
        completed = True
    finally:
        if completed and counters and emit_metrics:
            emit_counters(counters)


@app.command(name="scrub")
def scrub_cmd(
    ctx: typer.Context,
    file: str = typer.Argument(
        ...,
        help="Path to the file to audit or clean.",
    ),
    out: str | None = typer.Option(
        None,
        "--out",
        help="Output path for cleaned text (if omitted, audit only).",
    ),
    audit: bool = typer.Option(
        False,
        "--audit",
        help="Audit for metadata without modifying.",
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
    """Audit or clean metadata-like markers from a file."""
    json_mode = _effective_flag(ctx, json_mode, "json_mode")
    no_color = _effective_flag(ctx, no_color, "no_color")
    counters = Counters()
    logger, emit_metrics = _privacy_aware_logger(counters)
    completed = False
    try:
        # Read file
        try:
            text = read_text_strict(file)
        except FileIOError as exc:
            _report_error(
                message_for_exception(exc),
                EXIT_IO_ERROR,
                json_mode,
                logger=logger,
                event="scrub.error",
            )

        from humanhand.infra.files import write_clean_text

        class _CliFileWriter:
            def write(
                self,
                output_path: str,
                text: str,
                input_paths: list[str | Path] | None = None,
            ) -> str:
                return str(write_clean_text(output_path, text, input_paths))

        try:
            if audit:
                result = scrub_service(
                    text=text,
                    logger=logger,
                    audit_only=True,
                )
            else:
                if out is None:
                    _report_error(
                        "--out is required when not using --audit",
                        EXIT_INPUT_ERROR,
                        json_mode,
                        logger=logger,
                        event="scrub.error",
                    )
                if _output_matches_input(out, file):
                    _report_error(
                        message_for_exception(
                            FileIOError("Output path must not match an input path")
                        ),
                        EXIT_IO_ERROR,
                        json_mode,
                        logger=logger,
                        event="scrub.error",
                    )
                result = scrub_service(
                    text=text,
                    file_writer=_CliFileWriter(),
                    logger=logger,
                    output_path=out,
                    audit_only=False,
                )
        except ValueError as exc:
            _report_error(
                message_for_exception(exc),
                EXIT_INPUT_ERROR,
                json_mode,
                logger=logger,
                event="scrub.error",
            )
        except FileIOError as exc:
            _report_error(
                message_for_exception(exc),
                EXIT_IO_ERROR,
                json_mode,
                logger=logger,
                event="scrub.error",
            )

        render_scrub_result(result, json_mode=json_mode, no_color=no_color)
        completed = True
    finally:
        if completed and counters and emit_metrics:
            emit_counters(counters)
