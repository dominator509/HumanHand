"""Parser worker entry point: one task on stdin, one result on stdout.

The worker is deliberately small and self-contained. It never imports
network, model, config, or cache code; ``verify_worker_environment``
enforces that inside the subprocess.
"""

from __future__ import annotations

import base64
import json
import sys
import tracemalloc

from pydantic import ValidationError

from humanhand.domain.import_findings import FindingCategory, FindingCode, FindingSeverity
from humanhand.infra.sandbox.parser_protocol import (
    install_network_guard,
    policy_from_dict,
    verify_worker_environment,
)
from humanhand.infra.sandbox.resource_limits import from_policy
from humanhand.infra.sandbox.worker_messages import (
    PROTOCOL_VERSION,
    ParseRequest,
    ParseResult,
    make_finding_payload,
)

_EMPTY_METADATA: dict[str, object] = {"count": 0, "items": []}
_EMPTY_COVERAGE: dict[str, object] = {
    "adapter": "",
    "status": "partial",
    "supported_structures": [],
    "unsupported_structures": [],
}


def _failed_envelope(task_id: str, description: str, evidence: str) -> ParseResult:
    """Build the fail-closed result envelope for protocol-level failures."""
    return ParseResult(
        protocol=PROTOCOL_VERSION,
        task_id=task_id,
        status="failed",
        document=None,
        findings=[
            make_finding_payload(
                FindingCode.WORKER_PROTOCOL_VIOLATION,
                FindingSeverity.ERROR,
                FindingCategory.WORKER,
                description,
                evidence,
            )
        ],
        unicode=None,
        active_content=[],
        metadata=_EMPTY_METADATA,
        coverage=_EMPTY_COVERAGE,
        measurements=None,
    )


def _emit(result: ParseResult) -> None:
    """Write one result line as UTF-8 bytes (never locale-encoded text).

    Canonical text may contain arbitrary code points (BOMs, decomposed
    forms), which Windows console encodings like cp1252 cannot represent.
    """
    sys.stdout.buffer.write(result.model_dump_json().encode("utf-8") + b"\n")
    sys.stdout.buffer.flush()


def _run_parse(request: ParseRequest) -> int:
    tracemalloc.start()
    install_network_guard()
    try:
        # Lazy import keeps the worker's module set minimal until a parser
        # is actually resolved; if the registry is unavailable the worker
        # fails closed with a protocol finding.
        from humanhand.infra.importers import get_importer_by_name
    except ImportError:
        _emit(
            _failed_envelope(request.task_id, "Parser registry unavailable", "importers_registry")
        )
        return 0

    try:
        importer = get_importer_by_name(request.parser_name)
    except ValueError:
        _emit(_failed_envelope(request.task_id, "Unknown parser", f"parser={request.parser_name}"))
        return 0

    # Scan after importer resolution so modules the registry imports are
    # covered by the enforcement check as well.
    forbidden = verify_worker_environment()
    if forbidden:
        _emit(
            _failed_envelope(
                request.task_id,
                "Worker process loaded forbidden modules",
                ",".join(forbidden[:5]),
            )
        )
        return 0

    try:
        raw = base64.b64decode(request.data_b64, validate=True)
    except ValueError:
        _emit(_failed_envelope(request.task_id, "Parser request data is not base64", "base64"))
        return 0

    try:
        policy = policy_from_dict(request.policy)
    except ValueError as exc:
        _emit(_failed_envelope(request.task_id, "Invalid parser policy", str(exc)))
        return 0

    limits = from_policy(policy)
    payloads = importer.parse_payloads(raw, policy)
    peak_bytes = tracemalloc.get_traced_memory()[1]

    findings_payload = payloads["findings"]
    if not isinstance(findings_payload, list):
        raise RuntimeError("parser payload missing findings list")
    if peak_bytes > limits.max_memory_bytes:
        findings_payload.append(
            make_finding_payload(
                FindingCode.LIMIT_MEMORY,
                FindingSeverity.ERROR,
                FindingCategory.RESOURCE_LIMIT,
                f"Worker peak memory {peak_bytes} bytes exceeds limit",
                f"peak={peak_bytes}",
            )
        )
        payloads["status"] = "failed"
        payloads["document"] = None

    measurements = payloads["measurements"]
    if isinstance(measurements, dict):
        measurements["peak_memory_bytes"] = peak_bytes

    document = payloads["document"]
    unicode_payload = payloads["unicode"]
    active_payload = payloads["active_content"]
    if not isinstance(active_payload, list):
        raise RuntimeError("parser payload missing active_content list")
    metadata_payload = payloads["metadata"]
    coverage_payload = payloads["coverage"]
    result = ParseResult(
        protocol=PROTOCOL_VERSION,
        task_id=request.task_id,
        status=str(payloads["status"]),
        document=document if isinstance(document, dict) else None,
        findings=[item for item in findings_payload if isinstance(item, dict)],
        unicode=unicode_payload if isinstance(unicode_payload, dict) else None,
        active_content=[item for item in active_payload if isinstance(item, dict)],
        metadata=metadata_payload if isinstance(metadata_payload, dict) else _EMPTY_METADATA,
        coverage=coverage_payload if isinstance(coverage_payload, dict) else _EMPTY_COVERAGE,
        measurements=measurements if isinstance(measurements, dict) else None,
    )
    _emit(result)
    return 0


def main() -> int:
    """Run one parse task from stdin and write one result to stdout."""
    raw_stdin = sys.stdin.buffer.read()
    try:
        request = ParseRequest.model_validate_json(raw_stdin)
    except ValidationError:
        sys.stdout.buffer.write(
            json.dumps({"protocol": PROTOCOL_VERSION, "error": "invalid_request"}).encode("utf-8")
            + b"\n"
        )
        sys.stdout.buffer.flush()
        return 2
    try:
        return _run_parse(request)
    except Exception as exc:
        _emit(_failed_envelope(request.task_id, "Worker failure", type(exc).__name__))
        return 0


if __name__ == "__main__":
    raise SystemExit(main())
