"""Supervisor that runs one bounded parser worker subprocess (ADR-004)."""

from __future__ import annotations

# subprocess is the ADR-004-mandated bounded parser worker boundary. The
# argv list is fixed (interpreter + literal "-m" + an internal module name),
# no shell is involved, input is an envelope on stdin, and the child is
# killed on timeout.
import base64
import dataclasses
import hashlib
import json
import subprocess  # nosec B404
import sys
from dataclasses import dataclass

from pydantic import ValidationError

from humanhand.domain.import_findings import (
    FindingCategory,
    FindingCode,
    FindingSeverity,
    ImportFinding,
)
from humanhand.domain.import_policy import ImportPolicy
from humanhand.infra.sandbox.resource_limits import ResourceLimits, from_policy
from humanhand.infra.sandbox.worker_messages import (
    PROTOCOL_VERSION,
    ParseRequest,
    ParseResult,
)


@dataclass(frozen=True)
class WorkerOutcome:
    """Outcome of one worker run: a parsed result or failure findings."""

    result: ParseResult | None
    findings: tuple[ImportFinding, ...]


def _worker_finding(code: str, description: str, evidence: str = "") -> ImportFinding:
    return ImportFinding(
        code=code,
        severity=FindingSeverity.ERROR,
        category=FindingCategory.WORKER,
        description=description,
        evidence=evidence,
    )


def _resource_finding(code: str, description: str, evidence: str = "") -> ImportFinding:
    return ImportFinding(
        code=code,
        severity=FindingSeverity.ERROR,
        category=FindingCategory.RESOURCE_LIMIT,
        description=description,
        evidence=evidence,
    )


def run_worker(
    *,
    parser_name: str,
    raw: bytes,
    policy: ImportPolicy,
    limits: ResourceLimits | None = None,
    worker_module: str = "humanhand.infra.sandbox.parser_worker",
) -> WorkerOutcome:
    """Run one parser worker subprocess and return its outcome.

    Failures never include raw user text: evidence carries only sizes,
    return codes, and error kinds.
    """
    if limits is None:
        limits = from_policy(policy)

    if len(raw) > policy.max_bytes:
        return WorkerOutcome(
            None,
            (
                _resource_finding(
                    FindingCode.LIMIT_BYTES,
                    f"Input size {len(raw)} bytes exceeds limit {policy.max_bytes}",
                    f"size={len(raw)} limit={policy.max_bytes}",
                ),
            ),
        )

    task_id = hashlib.sha256(raw + parser_name.encode("utf-8")).hexdigest()[:16]
    envelope = ParseRequest(
        protocol=PROTOCOL_VERSION,
        task_id=task_id,
        parser_name=parser_name,
        policy=dataclasses.asdict(policy),
        data_b64=base64.b64encode(raw).decode("ascii"),
    ).model_dump_json()

    try:
        # Fixed argv list, no shell, stdin envelope only, and a hard timeout
        # kill. worker_module is an internal constant; the override parameter
        # is a documented test seam, never user input.
        proc = subprocess.run(  # nosec B603
            [sys.executable, "-m", worker_module],
            input=envelope.encode("utf-8"),
            capture_output=True,
            timeout=limits.max_time_seconds,
        )
    except subprocess.TimeoutExpired:
        return WorkerOutcome(
            None,
            (
                _worker_finding(
                    FindingCode.WORKER_TIMEOUT,
                    f"Worker exceeded {limits.max_time_seconds}s",
                ),
            ),
        )
    except (FileNotFoundError, OSError):
        return WorkerOutcome(
            None,
            (
                _worker_finding(
                    FindingCode.WORKER_SPAWN_FAILED,
                    "Worker process could not be started",
                ),
            ),
        )

    if proc.returncode != 0:
        return WorkerOutcome(
            None,
            (
                _worker_finding(
                    FindingCode.WORKER_NONZERO_EXIT,
                    "Worker exited with a nonzero status",
                    f"returncode={proc.returncode}",
                ),
            ),
        )

    if len(proc.stdout) > limits.max_output_bytes:
        return WorkerOutcome(
            None,
            (
                _resource_finding(
                    FindingCode.LIMIT_OUTPUT,
                    f"Worker output {len(proc.stdout)} bytes exceeds limit "
                    f"{limits.max_output_bytes}",
                    f"stdout={len(proc.stdout)} limit={limits.max_output_bytes}",
                ),
            ),
        )

    try:
        stdout_text = proc.stdout.decode("utf-8")
    except UnicodeDecodeError:
        return WorkerOutcome(
            None,
            (
                _worker_finding(
                    FindingCode.WORKER_PROTOCOL_VIOLATION,
                    "Worker output is not valid UTF-8",
                    "stdout_not_utf8",
                ),
            ),
        )
    if not stdout_text.strip():
        return WorkerOutcome(
            None,
            (
                _worker_finding(
                    FindingCode.WORKER_PROTOCOL_VIOLATION,
                    "Worker produced no output",
                    "stdout_empty",
                ),
            ),
        )
    try:
        json.loads(stdout_text)
    except json.JSONDecodeError:
        return WorkerOutcome(
            None,
            (
                _worker_finding(
                    FindingCode.WORKER_PROTOCOL_VIOLATION,
                    "Worker output is not valid JSON",
                    "stdout_not_json",
                ),
            ),
        )
    try:
        result = ParseResult.model_validate_json(stdout_text)
    except ValidationError:
        return WorkerOutcome(
            None,
            (
                _worker_finding(
                    FindingCode.WORKER_PROTOCOL_VIOLATION,
                    "Worker output does not match the parser protocol",
                    "invalid_parse_result",
                ),
            ),
        )
    if result.task_id != task_id:
        return WorkerOutcome(
            None,
            (
                _worker_finding(
                    FindingCode.WORKER_PROTOCOL_VIOLATION,
                    "Worker result task id does not match the request",
                    "task_id_mismatch",
                ),
            ),
        )
    return WorkerOutcome(result, ())
