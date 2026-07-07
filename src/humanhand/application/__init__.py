"""Application-layer protocol and service exports."""

from humanhand.application.ports import (
    DetectorCache,
    DetectorClient,
    FileReader,
    FileWriter,
    LlmClient,
    Logger,
)
from humanhand.application.services import (
    DiffFactsResult,
    HealthResult,
    RewriteQualityError,
    RewriteResult,
    ScrubResult,
    VerifyResult,
    diff_facts_service,
    health,
    rewrite,
    scrub_service,
    verify,
)

__all__ = [
    # Ports
    "DetectorCache",
    "DetectorClient",
    "FileReader",
    "FileWriter",
    "LlmClient",
    "Logger",
    # Result types
    "DiffFactsResult",
    "HealthResult",
    "RewriteQualityError",
    "RewriteResult",
    "ScrubResult",
    "VerifyResult",
    # Services
    "diff_facts_service",
    "health",
    "rewrite",
    "scrub_service",
    "verify",
]
