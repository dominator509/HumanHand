"""`humanhand scanner` sub-app — scanner observatory (EP-018).

The orchestrator registers this module's ``scanner_app`` into
``humanhand.cli.app`` as the "scanner" sub-app at merge time; this module
never registers itself.

Commands run fully offline. ``scanner benchmark`` loads the real
synthetic control corpus (``tests/fixtures/beacon/synthetic-corpus`` in
the development tree; override with ``--corpus``) and runs the
deterministic local scan with NO detector configured, so every run
honestly reports ``label="unknown"`` and ``score=None``: no detector was
consulted, so no score is fabricated. The report is always printed to
stdout; with ``--out <dir>`` it is also persisted as
``<dir>/<run_id>.json``. Without ``--out`` the command refuses to write
anywhere and only prints. ``scanner report <run-id>`` re-reads a
persisted report from ``--dir`` (default ``.humanhand/reports/scanner``).

The run report is structured data (ids, labels, scores only) and is
printed as JSON in both text and JSON mode; no corpus text is ever
included in a report.

``--no-color`` is accepted for CLI-surface compatibility; this module
never emits color codes, so the flag is a documented no-op.
"""

from __future__ import annotations

import json
import sys
from pathlib import Path
from typing import NoReturn

import typer

from humanhand.cli.errors import message_for_exception
from humanhand.infra.beacon.scanners.local_artifact_scanner import (
    SCANNER_NAME,
    ScannerRun,
    run_local_scan,
)
from humanhand.infra.beacon.scanners.synthetic_corpus import (
    CorpusSample,
    load_synthetic_corpus,
)
from humanhand.infra.files import FileIOError, read_text_strict

# Exit-code constants are duplicated here deliberately (app.py owns the
# canonical definitions; importing them would create an import cycle).
EXIT_INPUT_ERROR = 1
EXIT_CONFIG_ERROR = 2
EXIT_IO_ERROR = 3
EXIT_INTERNAL_ERROR = 6

# Resolved against the development tree; a pip-installed wheel has no
# tests/ directory, so --corpus exists for pointing at a real corpus.
DEFAULT_CORPUS_DIR = (
    Path(__file__).resolve().parents[3] / "tests" / "fixtures" / "beacon" / "synthetic-corpus"
)
DEFAULT_REPORT_DIR = ".humanhand/reports/scanner"
REPORT_SCHEMA_VERSION = 1

scanner_app = typer.Typer(
    name="scanner",
    help="Scanner observatory: offline advisory scans over the synthetic control corpus.",
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


def _run_payload(run: ScannerRun) -> dict[str, object]:
    """Render one ScannerRun as a stable report entry (ids and labels only)."""
    return {
        "run_id": run.run_id,
        "scanner_name": run.scanner_name,
        "sample_id": run.sample_id,
        "label": run.label,
        "score": run.score,
    }


def _report_payload(run_id: str, runs: tuple[ScannerRun, ...]) -> dict[str, object]:
    """Build the full run report; content is deterministic for a given corpus."""
    return {
        "schema_version": REPORT_SCHEMA_VERSION,
        "run_id": run_id,
        "scanner_name": SCANNER_NAME,
        "count": len(runs),
        "runs": [_run_payload(run) for run in runs],
    }


def _write_report(out_dir: Path, report: dict[str, object], json_mode: bool) -> Path:
    """Persist the run report as ``<out_dir>/<run_id>.json``.

    Byte-clean UTF-8 with LF newlines (no BOM) and exactly one trailing
    newline, matching the repository's output rules.
    """
    run_id = str(report["run_id"])
    out_path = out_dir / f"{run_id}.json"
    try:
        out_dir.mkdir(parents=True, exist_ok=True)
        out_path.write_text(
            json.dumps(report, sort_keys=True, indent=2) + "\n",
            encoding="utf-8",
            newline="\n",
        )
    except OSError as exc:
        _report_error(f"cannot write scanner report: {exc}", EXIT_IO_ERROR, json_mode)
    return out_path


@scanner_app.command("benchmark")
def scanner_benchmark_cmd(
    ctx: typer.Context,
    out: str | None = typer.Option(
        None,
        "--out",
        help=(
            "Persist the run report into this directory as <run_id>.json. "
            "Without --out nothing is written; the report is only printed."
        ),
    ),
    corpus: str | None = typer.Option(
        None,
        "--corpus",
        help="Synthetic corpus directory (defaults to the repository fixture).",
    ),
    json_mode: bool = typer.Option(
        False,
        "--json",
        help="Output JSON to stdout only.",
    ),
    no_color: bool = typer.Option(
        False,
        "--no-color",
        help="Disable color output (documented no-op; this module never emits color).",
    ),
) -> None:
    """Run the offline advisory scan over the synthetic control corpus.

    No detector is configured on this path: every run reports label
    "unknown" with score None, because no detector was consulted. With
    --out the report is persisted as <out>/<run_id>.json; without --out
    the report is printed but nothing is written anywhere.
    """
    json_mode = _effective_flag(ctx, json_mode, "json_mode")
    corpus_dir = Path(corpus) if corpus is not None else Path(DEFAULT_CORPUS_DIR)
    try:
        samples: tuple[CorpusSample, ...] = load_synthetic_corpus(corpus_dir)
    except FileIOError as exc:
        _report_error(message_for_exception(exc), EXIT_IO_ERROR, json_mode)
    except Exception as exc:
        _report_error(message_for_exception(exc), EXIT_INPUT_ERROR, json_mode)
    try:
        runs = run_local_scan(samples)
    except Exception as exc:
        _report_error(message_for_exception(exc), EXIT_INTERNAL_ERROR, json_mode)
    report = _report_payload(runs[0].run_id, runs)
    if out is not None:
        _write_report(Path(out), report, json_mode)
    _render_json(report)


@scanner_app.command("report")
def scanner_report_cmd(
    ctx: typer.Context,
    run_id: str = typer.Argument(
        ...,
        help="Run id to read (scan-...).",
    ),
    dir_path: str = typer.Option(
        DEFAULT_REPORT_DIR,
        "--dir",
        help="Directory containing persisted run reports (default: .humanhand/reports/scanner).",
    ),
    json_mode: bool = typer.Option(
        False,
        "--json",
        help="Output JSON to stdout only.",
    ),
    no_color: bool = typer.Option(
        False,
        "--no-color",
        help="Disable color output (documented no-op; this module never emits color).",
    ),
) -> None:
    """Re-read a persisted scanner run report and print it."""
    json_mode = _effective_flag(ctx, json_mode, "json_mode")
    report_path = Path(dir_path) / f"{run_id}.json"
    try:
        raw = read_text_strict(report_path)
    except FileIOError as exc:
        _report_error(message_for_exception(exc), EXIT_IO_ERROR, json_mode)
    try:
        report = json.loads(raw)
    except json.JSONDecodeError:
        _report_error(f"scanner report is not valid JSON: {report_path}", EXIT_IO_ERROR, json_mode)
    if not isinstance(report, dict) or report.get("run_id") != run_id:
        _report_error(
            f"scanner report does not match run id: {run_id}",
            EXIT_IO_ERROR,
            json_mode,
        )
    _render_json(report)
