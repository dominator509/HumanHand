"""Application use-case orchestration for Human Hand.

Each service function accepts its dependencies as protocol parameters,
keeping the application layer free of concrete infra imports.
"""

from __future__ import annotations

import time
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any

from humanhand.domain.facts import diff_facts, extract_fact_anchors
from humanhand.domain.prompts import build_repair_prompt, build_rewrite_prompt
from humanhand.domain.repair import DEFAULT_MAX_ATTEMPTS, decide_repair
from humanhand.domain.scrub import audit_text
from humanhand.domain.style import extract_style_fingerprint
from humanhand.domain.types import (
    FactDiffReport,
    RepairDecision,
    ScrubReport,
)

# ── Result types ──────────────────────────────────────────────


class RewriteQualityError(Exception):
    """Raised when rewrite output cannot satisfy the fact-preservation contract."""


@dataclass
class RewriteResult:
    """Outcome of a rewrite operation."""

    output_path: str
    input_chars: int
    output_chars: int
    repair_attempts: int = 0
    preservation_score: float = 1.0
    fact_diff: FactDiffReport | None = None
    scrub_report: ScrubReport | None = None
    duration_ms: float = 0.0


@dataclass
class VerifyResult:
    """Outcome of a verify operation."""

    provider: str
    model: str
    score: float | None = None
    label: str | None = None
    cache_hit: bool = False
    duration_ms: float = 0.0


@dataclass
class DiffFactsResult:
    """Outcome of a diff-facts operation."""

    report: FactDiffReport
    source_chars: int = 0
    candidate_chars: int = 0
    duration_ms: float = 0.0


@dataclass
class ScrubResult:
    """Outcome of a scrub operation."""

    report: ScrubReport
    audit_only: bool = False
    output_path: str | None = None
    duration_ms: float = 0.0


@dataclass
class HealthResult:
    """Outcome of a health check."""

    status: str = "ok"
    version: str = ""
    python_version: str = ""
    config_summary: dict[str, Any] = field(default_factory=dict)


# ── Service functions ─────────────────────────────────────────


def rewrite(
    *,
    source_text: str,
    style_text: str,
    output_path: str | Path,
    llm_client: Any,  # LlmClient Protocol
    file_writer: Any,  # FileWriter Protocol
    logger: Any,  # Logger Protocol
    max_chars: int = 200_000,
    max_repair_attempts: int = DEFAULT_MAX_ATTEMPTS,
    seed: int | None = None,
) -> RewriteResult:
    """Orchestrate a full rewrite: fingerprint → prompt → LLM → repair → scrub → write.

    Args:
        source_text: AI-assisted source text.
        style_text: Human writing sample.
        output_path: Where to write the final output.
        llm_client: LLM client implementing LlmClient Protocol.
        file_writer: File writer implementing FileWriter Protocol.
        logger: Logger implementing Logger Protocol.
        max_chars: Maximum allowed input characters.
        max_repair_attempts: Maximum repair loop iterations.
        seed: Optional deterministic seed (reserved for future use).

    Returns:
        RewriteResult with output path, metrics, and quality scores.

    Raises:
        ValueError: If inputs exceed max_chars or are empty.
        RewriteQualityError: If the repair loop cannot preserve facts safely.
    """
    t0 = time.monotonic()
    input_chars = len(source_text) + len(style_text)

    logger.log("rewrite.start", level="info", input_length=input_chars)

    # Validate input sizes
    if len(source_text) > max_chars:
        raise ValueError(f"Source text exceeds maximum characters ({max_chars})")
    if len(style_text) > max_chars:
        raise ValueError(f"Style text exceeds maximum characters ({max_chars})")
    if not source_text.strip():
        raise ValueError("Source text must not be empty")
    if not style_text.strip():
        raise ValueError("Style text must not be empty")

    # Build style fingerprint and extract facts
    fingerprint = extract_style_fingerprint(style_text)
    facts = extract_fact_anchors(source_text)

    # Build initial rewrite prompt
    prompt = build_rewrite_prompt(source_text, style_text, fingerprint, facts)

    # Call LLM
    candidate = llm_client.rewrite(prompt)
    repair_attempts = 0

    # Repair loop
    while True:
        diff_report = diff_facts(source_text, candidate)
        scrub_report = audit_text(candidate)

        decision = decide_repair(
            diff_report,
            scrub_report,
            repair_attempts,
            max_repair_attempts,
        )

        if decision == RepairDecision.ACCEPT:
            break

        if decision == RepairDecision.FAIL:
            duration_ms = (time.monotonic() - t0) * 1000
            logger.log(
                "rewrite.fail",
                level="error",
                repair_attempts=repair_attempts,
                preservation_score=diff_report.preservation_score,
                omissions=len(diff_report.omissions),
                additions=len(diff_report.additions),
                contradictions=len(diff_report.contradictions),
                elapsed_ms=round(duration_ms, 1),
            )
            raise RewriteQualityError(
                f"Fact drift repair failed after {repair_attempts} repair attempt(s)"
            )

        repair_attempts += 1
        repair_prompt = build_repair_prompt(source_text, candidate, diff_report, repair_attempts)
        candidate = llm_client.rewrite(repair_prompt)

    final_diff = diff_report
    # Write through file_writer (which also scrubs)
    written_path = file_writer.write(output_path, candidate, input_paths=[])

    duration_ms = (time.monotonic() - t0) * 1000

    logger.log(
        "rewrite.end",
        level="info",
        output_length=len(candidate),
        repair_attempts=repair_attempts,
        preservation_score=final_diff.preservation_score,
        elapsed_ms=round(duration_ms, 1),
    )

    return RewriteResult(
        output_path=str(written_path),
        input_chars=input_chars,
        output_chars=len(candidate),
        repair_attempts=repair_attempts,
        preservation_score=final_diff.preservation_score,
        fact_diff=final_diff,
        duration_ms=round(duration_ms, 1),
    )


def verify(
    *,
    text: str,
    detector_client: Any,  # DetectorClient Protocol
    cache: Any | None = None,  # DetectorCache Protocol, optional
    logger: Any,  # Logger Protocol
    provider: str = "local",
    model: str = "heuristic",
    cache_enabled: bool = True,
) -> VerifyResult:
    """Verify whether text is AI-generated using a detector or local heuristic.

    Args:
        text: The text to analyze.
        detector_client: Detector client implementing DetectorClient Protocol.
        cache: Optional detector score cache.
        logger: Logger implementing Logger Protocol.
        provider: Detector provider name.
        model: Detector model name.
        cache_enabled: Whether to consult/update the cache.

    Returns:
        VerifyResult with provider, score, label, and cache info.
    """
    t0 = time.monotonic()

    logger.log(
        "verify.start",
        level="info",
        provider=provider,
        model=model,
        input_length=len(text),
    )

    # Check cache if enabled
    if cache_enabled and cache is not None:
        import hashlib

        text_hash = hashlib.sha256(text.encode("utf-8")).hexdigest()
        cached = cache.get(text_hash, provider, model, schema_version=1)
        if cached is not None:
            duration_ms = (time.monotonic() - t0) * 1000
            logger.log(
                "verify.end",
                level="info",
                provider=provider,
                model=model,
                cache_hit=True,
                elapsed_ms=round(duration_ms, 1),
            )
            return VerifyResult(
                provider=provider,
                model=model,
                score=cached.get("score"),
                label=cached.get("label"),
                cache_hit=True,
                duration_ms=round(duration_ms, 1),
            )

    # Call detector
    result = detector_client.detect(text)

    # Store in cache if enabled
    if cache_enabled and cache is not None:
        import hashlib

        text_hash = hashlib.sha256(text.encode("utf-8")).hexdigest()
        cache.put(
            {
                "text_sha256": text_hash,
                "provider": provider,
                "model": model,
                "score": result.get("score"),
                "label": result.get("label"),
                "raw_score_json": result.get("raw_score_json"),
            }
        )

    duration_ms = (time.monotonic() - t0) * 1000

    logger.log(
        "verify.end",
        level="info",
        provider=provider,
        model=model,
        cache_hit=False,
        elapsed_ms=round(duration_ms, 1),
    )

    return VerifyResult(
        provider=provider,
        model=model,
        score=result.get("score"),
        label=result.get("label"),
        cache_hit=False,
        duration_ms=round(duration_ms, 1),
    )


def diff_facts_service(
    *,
    source_text: str,
    candidate_text: str,
    logger: Any,  # Logger Protocol
) -> DiffFactsResult:
    """Compare factual anchors between source and candidate text.

    Args:
        source_text: Original source text.
        candidate_text: Rewritten or AI-generated text to compare.
        logger: Logger implementing Logger Protocol.

    Returns:
        DiffFactsResult with the fact drift report.
    """
    t0 = time.monotonic()

    logger.log("diff_facts.start", level="info")

    report = diff_facts(source_text, candidate_text)

    duration_ms = (time.monotonic() - t0) * 1000

    logger.log(
        "diff_facts.end",
        level="info",
        preservation_score=report.preservation_score,
        omissions=len(report.omissions),
        additions=len(report.additions),
        contradictions=len(report.contradictions),
        elapsed_ms=round(duration_ms, 1),
    )

    return DiffFactsResult(
        report=report,
        source_chars=len(source_text),
        candidate_chars=len(candidate_text),
        duration_ms=round(duration_ms, 1),
    )


def scrub_service(
    *,
    text: str,
    file_writer: Any | None = None,  # FileWriter Protocol, optional
    logger: Any,  # Logger Protocol
    output_path: str | Path | None = None,
    audit_only: bool = False,
) -> ScrubResult:
    """Audit or clean metadata-like markers from text.

    Args:
        text: Text to audit or clean.
        file_writer: File writer for writing cleaned output (None if audit_only).
        logger: Logger implementing Logger Protocol.
        output_path: Where to write cleaned output (required if not audit_only).
        audit_only: If True, only audit without modifying.

    Returns:
        ScrubResult with the scrub/audit report.

    Raises:
        ValueError: If not audit_only and output_path is None.
    """
    t0 = time.monotonic()

    logger.log("scrub.start", level="info", audit_only=audit_only)

    if audit_only:
        report = audit_text(text)
    else:
        if output_path is None:
            raise ValueError("output_path is required when audit_only is False")
        if file_writer is None:
            raise ValueError("file_writer is required when audit_only is False")
        file_writer.write(output_path, text)
        # The file_writer scrubs internally; we audit the original for the report
        report = audit_text(text)

    duration_ms = (time.monotonic() - t0) * 1000

    logger.log(
        "scrub.end",
        level="info",
        findings=len(report.findings),
        audit_only=audit_only,
        elapsed_ms=round(duration_ms, 1),
    )

    return ScrubResult(
        report=report,
        audit_only=audit_only,
        output_path=str(output_path) if output_path else None,
        duration_ms=round(duration_ms, 1),
    )


def health(
    *,
    version: str,
    python_version: str,
    llm_configured: bool = False,
    detector_provider: str = "local",
) -> HealthResult:
    """Check CLI and environment health without network calls.

    Args:
        version: Human Hand version string.
        python_version: Python version string.
        llm_configured: Whether an LLM endpoint is configured.
        detector_provider: Current detector provider name.

    Returns:
        HealthResult with status and config summary.
    """
    return HealthResult(
        status="ok",
        version=version,
        python_version=python_version,
        config_summary={
            "llm_configured": llm_configured,
            "detector_provider": detector_provider,
        },
    )
