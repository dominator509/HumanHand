"""E2E tests for the `humanhand scanner` sub-app (EP-018).

The scanner CLI has no parallel-module dependencies: the synthetic corpus
and the local scanner are implemented in this ExecPlan, so these tests run
in the current build. All commands are offline and deterministic.
"""

from __future__ import annotations

import json
from pathlib import Path

import pytest
import typer
from typer.testing import CliRunner

from humanhand.cli.scanner_commands import scanner_app
from humanhand.infra.beacon.scanners.local_artifact_scanner import run_local_scan
from humanhand.infra.beacon.scanners.synthetic_corpus import load_synthetic_corpus
from humanhand.infra.detectors.local import LocalDetector

pytestmark = pytest.mark.importers

# tests/e2e/test_scanner_cli.py -> parents[1] is the tests/ directory.
CORPUS_DIR = Path(__file__).resolve().parents[1] / "fixtures" / "beacon" / "synthetic-corpus"

# Standalone composed app: tests never touch the orchestrator (app.py).
cli_app = typer.Typer()
cli_app.add_typer(scanner_app, name="scanner")
runner = CliRunner()


def test_benchmark_prints_report_without_writing(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    """Offline benchmark prints the report and writes nothing without --out."""
    monkeypatch.chdir(tmp_path)
    result = runner.invoke(
        cli_app,
        ["scanner", "benchmark", "--corpus", str(CORPUS_DIR), "--json"],
    )
    assert result.exit_code == 0
    report = json.loads(result.stdout)
    assert report["schema_version"] == 1
    assert report["run_id"].startswith("scan-")
    assert report["scanner_name"] == "local"
    assert report["count"] == 5
    assert len(report["runs"]) == 5
    for run in report["runs"]:
        assert run["label"] == "unknown"  # no detector was consulted (honest)
        assert run["score"] is None
    # Corpus text must never leak into stdout.
    assert "Dear Rosa" not in result.stdout
    # Nothing was written anywhere.
    assert list(tmp_path.iterdir()) == []


def test_benchmark_persists_deterministic_report(tmp_path: Path) -> None:
    """Two runs over the same corpus produce the identical run id and report."""
    out_dir = tmp_path / "reports"
    first = runner.invoke(
        cli_app,
        ["scanner", "benchmark", "--corpus", str(CORPUS_DIR), "--out", str(out_dir), "--json"],
    )
    assert first.exit_code == 0
    report1 = json.loads(first.stdout)
    run_id = report1["run_id"]
    second = runner.invoke(
        cli_app,
        ["scanner", "benchmark", "--corpus", str(CORPUS_DIR), "--out", str(out_dir), "--json"],
    )
    assert second.exit_code == 0
    report2 = json.loads(second.stdout)
    assert report2["run_id"] == run_id
    assert report2["runs"] == report1["runs"]
    persisted = out_dir / f"{run_id}.json"
    assert persisted.is_file()
    on_disk = json.loads(persisted.read_text(encoding="utf-8"))
    assert on_disk == report1


def test_report_reads_back_persisted_run(tmp_path: Path) -> None:
    """`scanner report <run-id>` re-reads a persisted report."""
    out_dir = tmp_path / "reports"
    first = runner.invoke(
        cli_app,
        ["scanner", "benchmark", "--corpus", str(CORPUS_DIR), "--out", str(out_dir), "--json"],
    )
    assert first.exit_code == 0
    run_id = json.loads(first.stdout)["run_id"]
    second = runner.invoke(
        cli_app,
        ["scanner", "report", run_id, "--dir", str(out_dir), "--json"],
    )
    assert second.exit_code == 0
    report = json.loads(second.stdout)
    assert report["run_id"] == run_id
    assert report["count"] == 5


def test_report_missing_run_exits_io_error(tmp_path: Path) -> None:
    """Reading a run that was never persisted fails with exit code 3."""
    result = runner.invoke(
        cli_app,
        ["scanner", "report", "scan-deadbeef", "--dir", str(tmp_path / "nope"), "--json"],
    )
    assert result.exit_code == 3
    payload = json.loads(result.stdout)
    assert payload["status"] == "error"
    assert payload["exit_code"] == 3


def test_benchmark_missing_corpus_exits_io_error(tmp_path: Path) -> None:
    """A missing corpus directory fails with exit code 3, never a fake run."""
    result = runner.invoke(
        cli_app,
        ["scanner", "benchmark", "--corpus", str(tmp_path / "missing"), "--json"],
    )
    assert result.exit_code == 3


def test_run_local_scan_with_real_local_detector() -> None:
    """Extra contract check: the real EP-006 LocalDetector wired into run_local_scan.

    Not part of the mandated CLI surface; recorded as an extra test. The
    detector path must produce real labels and numeric scores, never the
    offline "unknown"/None placeholders.
    """
    samples = load_synthetic_corpus(CORPUS_DIR)
    detector = LocalDetector()
    runs = run_local_scan(samples, detector=detector)
    assert len(runs) == 5
    for run in runs:
        assert run.label in {"human", "ai", "unknown"}
        assert isinstance(run.score, float)
