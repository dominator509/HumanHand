"""Bounded parser worker sandbox (ADR-004).

The sandbox runs one short-lived parser subprocess per task with hard
time, memory, output, and input bounds. The worker channel is a single
JSON envelope on stdin and a single JSON result on stdout.
"""

from humanhand.infra.sandbox.parser_protocol import policy_from_dict, verify_worker_environment
from humanhand.infra.sandbox.parser_supervisor import WorkerOutcome, run_worker
from humanhand.infra.sandbox.resource_limits import (
    DEFAULT_MAX_MEMORY_BYTES,
    ResourceLimits,
    from_policy,
    validate,
)
from humanhand.infra.sandbox.worker_messages import (
    PROTOCOL_VERSION,
    ParseRequest,
    ParseResult,
)

__all__ = [
    "DEFAULT_MAX_MEMORY_BYTES",
    "PROTOCOL_VERSION",
    "ParseRequest",
    "ParseResult",
    "ResourceLimits",
    "WorkerOutcome",
    "from_policy",
    "policy_from_dict",
    "run_worker",
    "validate",
    "verify_worker_environment",
]
