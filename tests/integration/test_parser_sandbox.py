"""Integration tests for the bounded parser worker sandbox (real subprocesses)."""

from __future__ import annotations

import json
import subprocess
import sys

import pytest

from humanhand.domain.import_findings import FindingCode
from humanhand.domain.import_policy import ImportPolicy
from humanhand.infra.sandbox.parser_supervisor import run_worker


@pytest.mark.importers
class TestParserSandbox:
    def test_timeout_enforced(self) -> None:
        policy = ImportPolicy(lane="source", timeout_seconds=0.001)
        outcome = run_worker(parser_name="text", raw=b"hello world", policy=policy)
        assert outcome.result is None
        assert any(f.code == FindingCode.WORKER_TIMEOUT for f in outcome.findings)

    def test_spawn_failure_module_not_found(self) -> None:
        # `python -m missing.module` deterministically exits 1, which the
        # supervisor surfaces as a nonzero exit (never an OSError).
        outcome = run_worker(
            parser_name="text",
            raw=b"x",
            policy=ImportPolicy(),
            worker_module="humanhand.infra.sandbox.does_not_exist_module",
        )
        assert outcome.result is None
        codes = {f.code for f in outcome.findings}
        assert FindingCode.WORKER_NONZERO_EXIT in codes

    def test_spawn_failure_os_error(self, monkeypatch: pytest.MonkeyPatch) -> None:
        # Mock at the subprocess boundary: an OSError while spawning must
        # become WORKER_SPAWN_FAILED, not a crash.
        import humanhand.infra.sandbox.parser_supervisor as supervisor_module

        def _explode(*_args: object, **_kwargs: object) -> object:
            raise OSError("spawn refused")

        monkeypatch.setattr(subprocess, "run", _explode)
        outcome = supervisor_module.run_worker(parser_name="text", raw=b"x", policy=ImportPolicy())
        assert outcome.result is None
        codes = {f.code for f in outcome.findings}
        assert FindingCode.WORKER_SPAWN_FAILED in codes

    def test_protocol_violation_on_garbage_stdout(self) -> None:
        # A worker module that emits non-JSON output must surface a
        # protocol violation, never a crash. The fake module lives in
        # tests/integration/support and is a test seam via worker_module.
        outcome = run_worker(
            parser_name="text",
            raw=b"x",
            policy=ImportPolicy(),
            worker_module="tests.integration.support.garbage_worker",
        )
        assert outcome.result is None
        codes = {f.code for f in outcome.findings}
        assert FindingCode.WORKER_PROTOCOL_VIOLATION in codes

    def test_protocol_violation_on_mismatched_task_id(
        self, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        payload: dict[str, object] = {
            "protocol": "parser-worker-1",
            "task_id": "wrong-task",
            "status": "failed",
            "document": None,
            "findings": [],
            "unicode": None,
            "active_content": [],
            "metadata": {"count": 0, "items": []},
            "coverage": {
                "adapter": "",
                "status": "partial",
                "supported_structures": [],
                "unsupported_structures": [],
            },
            "measurements": None,
        }

        def fake_run(*_args: object, **_kwargs: object) -> subprocess.CompletedProcess[bytes]:
            return subprocess.CompletedProcess(
                args=[],
                returncode=0,
                stdout=json.dumps(payload).encode("utf-8"),
                stderr=b"",
            )

        monkeypatch.setattr(subprocess, "run", fake_run)
        outcome = run_worker(parser_name="text", raw=b"x", policy=ImportPolicy())
        assert outcome.result is None
        assert any(
            finding.code == FindingCode.WORKER_PROTOCOL_VIOLATION
            and finding.evidence == "task_id_mismatch"
            for finding in outcome.findings
        )

    def test_invalid_envelope_direct_worker(self) -> None:
        proc = subprocess.run(
            [sys.executable, "-m", "humanhand.infra.sandbox.parser_worker"],
            input=b"",
            capture_output=True,
        )
        assert proc.returncode == 2
        payload = json.loads(proc.stdout.decode("utf-8"))
        assert payload["error"] == "invalid_request"

    def test_real_worker_round_trip(self) -> None:
        # With the importers registry in place this exercises the real
        # happy path: the supervisor spawns the worker, the worker resolves
        # the text importer, and a canonical document comes back.
        outcome = run_worker(parser_name="text", raw=b"hello world\n", policy=ImportPolicy())
        assert outcome.result is not None
        assert outcome.result.status == "ok"
        assert outcome.findings == ()
        document = outcome.result.document
        assert document is not None
        assert document["schema"] == "canonical-document"
        nodes = document["nodes"]
        assert isinstance(nodes, list)
        first_node = nodes[0]
        assert isinstance(first_node, dict)
        assert first_node["type"] == "document"

    def test_unknown_parser_fails_closed(self) -> None:
        outcome = run_worker(parser_name="no-such-parser", raw=b"hello", policy=ImportPolicy())
        assert outcome.result is not None
        assert outcome.result.status == "failed"
        codes = {item.get("code") for item in outcome.result.findings}
        assert FindingCode.WORKER_PROTOCOL_VIOLATION in codes

    def test_oversize_input_short_circuits_before_spawn(self) -> None:
        policy = ImportPolicy(max_bytes=10)
        outcome = run_worker(parser_name="text", raw=b"x" * 100, policy=policy)
        assert outcome.result is None
        assert any(f.code == FindingCode.LIMIT_BYTES for f in outcome.findings)
