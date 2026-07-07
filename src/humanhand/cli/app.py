"""Typer CLI application — command definitions and wiring."""

from __future__ import annotations

import contextlib
import json
import sys
from datetime import UTC, datetime
from pathlib import Path

import typer

from humanhand import __version__
from humanhand.application.services import (
    RewriteQualityError,
    diff_facts_service,
    rewrite,
    scrub_service,
    verify,
)
from humanhand.cli.output import (
    render_diff_facts_result,
    render_health,
    render_rewrite_result,
    render_scrub_result,
    render_verify_result,
)
from humanhand.infra.cache import DetectorScoreCache
from humanhand.infra.config import Config, load_config
from humanhand.infra.detectors import create_detector
from humanhand.infra.detectors.base import DetectorError, ProviderUnavailableError
from humanhand.infra.files import FileIOError, read_text_strict
from humanhand.infra.llm import LlmError, OpenAiLlmClient

app = typer.Typer(
    name="humanhand",
    help="Privacy-preserving CLI for rewriting AI-assisted text into human style.",
    no_args_is_help=True,
)


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

    def log(self, event: str, level: str = "info", **fields: object) -> None:
        payload: dict[str, object] = {
            "timestamp": datetime.now(UTC).isoformat().replace("+00:00", "Z"),
            "level": level,
            "event": event,
            "message": str(fields.pop("message", event.replace(".", " "))),
            "elapsed_ms": fields.pop("elapsed_ms", None),
            "model": fields.pop("model", None),
            "endpoint_host": fields.pop("endpoint_host", None),
            "input_length": fields.pop("input_length", None),
            "output_length": fields.pop("output_length", None),
            "sha256_prefix": fields.pop("sha256_prefix", None),
            "cache_hit": fields.pop("cache_hit", None),
            "attempt": fields.pop("attempt", None),
            "retry_reason": fields.pop("retry_reason", None),
        }

        for key, value in sorted(fields.items()):
            if value is None or isinstance(value, str | int | float | bool):
                payload[key] = value

        print(json.dumps(payload, separators=(",", ":"), sort_keys=True), file=sys.stderr)


def _error_json(message: str, code: int) -> None:
    """Print a JSON error and exit."""
    print(json.dumps({"status": "error", "message": message, "exit_code": code}))
    raise typer.Exit(code)


def _error_text(message: str, code: int) -> None:
    """Print a one-line error to stderr and exit."""
    print(f"error: {message}", file=sys.stderr)
    raise typer.Exit(code)


def _report_error(
    message: str,
    code: int,
    json_mode: bool,
    *,
    logger: _CliLogger | None = None,
    event: str | None = None,
) -> None:
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
    return path  # type: ignore[return-value]


# ── Callback ────────────────────────────────────────────────────


def version_callback(value: bool) -> None:
    if value:
        print(f"humanhand {__version__}")
        raise typer.Exit()


@app.callback()
def main(
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


# ── Commands ────────────────────────────────────────────────────


@app.command(name="health")
def health_cmd(
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
    logger = _CliLogger()
    logger.log("health.start", level="info", message="health check started")

    config_valid = True
    config_error: str | None = None
    try:
        config = load_config()
    except Exception as exc:
        config = Config()
        config_valid = False
        config_error = type(exc).__name__

    render_health(
        config,
        json_mode=json_mode,
        config_valid=config_valid,
        config_error=config_error,
        no_color=no_color,
    )
    logger.log(
        "health.end",
        level="info",
        message="health check completed",
        config_valid=config_valid,
    )


@app.command(name="rewrite")
def rewrite_cmd(
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
        help="Print generated prose to stdout.",
    ),
    no_color: bool = typer.Option(
        False,
        "--no-color",
        help="Disable color output.",
    ),
) -> None:
    """Rewrite AI-assisted text to match a human writing style."""
    logger = _CliLogger()
    try:
        config = load_config()
    except Exception as exc:
        _report_error(
            f"Config error: {exc}",
            EXIT_CONFIG_ERROR,
            json_mode,
            logger=logger,
            event="rewrite.error",
        )

    # Read source file
    if source == "-":
        source_text = sys.stdin.read()
    else:
        try:
            source_text = read_text_strict(source)
        except FileIOError as exc:
            _report_error(
                str(exc),
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
            str(exc),
            EXIT_IO_ERROR,
            json_mode,
            logger=logger,
            event="rewrite.error",
        )

    # Create LLM client
    try:
        llm_client = OpenAiLlmClient(config)
    except LlmError as exc:
        _report_error(
            f"LLM client error: {exc}",
            EXIT_EXTERNAL_ERROR,
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
            str(exc),
            EXIT_INPUT_ERROR,
            json_mode,
            logger=logger,
            event="rewrite.error",
        )
    except RewriteQualityError as exc:
        _report_error(
            str(exc),
            EXIT_SCHEMA_ERROR,
            json_mode,
            logger=logger,
            event="rewrite.error",
        )
    except LlmError as exc:
        _report_error(
            str(exc),
            EXIT_EXTERNAL_ERROR,
            json_mode,
            logger=logger,
            event="rewrite.error",
        )

    if print_output:
        # Read back and print the generated prose
        try:
            output_text = read_text_strict(out)
            print(output_text)
        except FileIOError as exc:
            _report_error(
                str(exc),
                EXIT_IO_ERROR,
                json_mode,
                logger=logger,
                event="rewrite.error",
            )

    render_rewrite_result(result, json_mode=json_mode, no_color=no_color)


@app.command(name="verify")
def verify_cmd(
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
    logger = _CliLogger()
    try:
        config = load_config()
    except Exception as exc:
        _report_error(
            f"Config error: {exc}",
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
            str(exc),
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
            str(exc),
            EXIT_CONFIG_ERROR,
            json_mode,
            logger=logger,
            event="verify.error",
        )

    # Create cache if enabled
    cache = None
    if config.cache_enabled:
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
            cache_enabled=config.cache_enabled and cache is not None,
        )
    except ProviderUnavailableError as exc:
        _report_error(
            str(exc),
            EXIT_EXTERNAL_ERROR,
            json_mode,
            logger=logger,
            event="verify.error",
        )
    except DetectorError as exc:
        _report_error(
            str(exc),
            EXIT_EXTERNAL_ERROR,
            json_mode,
            logger=logger,
            event="verify.error",
        )
    finally:
        if cache is not None:
            cache.close()

    render_verify_result(result, json_mode=json_mode, no_color=no_color)


@app.command(name="diff-facts")
def diff_facts_cmd(
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
    logger = _CliLogger()
    # Read source
    try:
        source_text = read_text_strict(ai_source)
    except FileIOError as exc:
        _report_error(
            str(exc),
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
            str(exc),
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


@app.command(name="scrub")
def scrub_cmd(
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
    logger = _CliLogger()
    # Read file
    try:
        text = read_text_strict(file)
    except FileIOError as exc:
        _report_error(
            str(exc),
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
            result = scrub_service(
                text=text,
                file_writer=_CliFileWriter(),
                logger=logger,
                output_path=out,
                audit_only=False,
            )
    except ValueError as exc:
        _report_error(
            str(exc),
            EXIT_INPUT_ERROR,
            json_mode,
            logger=logger,
            event="scrub.error",
        )

    render_scrub_result(result, json_mode=json_mode, no_color=no_color)
