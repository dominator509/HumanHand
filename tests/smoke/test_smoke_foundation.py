"""Fast smoke tests for foundation baseline with timing assertions.

Overall smoke suite (all tests in tests/smoke/) is expected to complete
under 30 seconds when run with mocked dependencies (no live network).

Per-command timing thresholds:
  100ms   target for local development (first-byte-to-stdout)
  500ms   generous allowance for CI / loaded runners
Both measured via time.perf_counter() around CliRunner.invoke().
"""

import json
import time

from typer.testing import CliRunner

import humanhand
from humanhand.cli.app import app

runner = CliRunner()

# ── Timing thresholds ────────────────────────────────────────────
# 100 ms  = target for responsive CLI on local hardware
# 500 ms  = generous CI allowance (VM cold-start / shared runners)
_TIMING_THRESHOLD = 0.5  # seconds


class TestSmokeFoundation:
    def test_help_fast(self) -> None:
        t0 = time.perf_counter()
        result = runner.invoke(app, ["--help"])
        elapsed = time.perf_counter() - t0
        assert result.exit_code == 0
        assert elapsed < _TIMING_THRESHOLD, (
            f"--help took {elapsed * 1000:.1f} ms (threshold {_TIMING_THRESHOLD * 1000:.0f} ms)"
        )

    def test_version_fast(self) -> None:
        t0 = time.perf_counter()
        result = runner.invoke(app, ["--version"])
        elapsed = time.perf_counter() - t0
        assert result.exit_code == 0
        assert humanhand.__version__ in result.stdout
        assert elapsed < _TIMING_THRESHOLD, (
            f"--version took {elapsed * 1000:.1f} ms (threshold {_TIMING_THRESHOLD * 1000:.0f} ms)"
        )

    def test_health_json_fast(self) -> None:
        t0 = time.perf_counter()
        result = runner.invoke(app, ["health", "--json"])
        elapsed = time.perf_counter() - t0
        assert result.exit_code == 0
        data = json.loads(result.stdout)
        assert data["status"] == "ok"
        assert elapsed < _TIMING_THRESHOLD, (
            f"health --json took {elapsed * 1000:.1f} ms "
            f"(threshold {_TIMING_THRESHOLD * 1000:.0f} ms)"
        )
