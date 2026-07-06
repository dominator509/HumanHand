"""Repair loop decision logic — determine whether to accept, repair, or fail."""

from __future__ import annotations

from humanhand.domain.types import (
    FactDiffReport,
    RepairDecision,
    ScrubReport,
)

# Default thresholds
DEFAULT_PRESERVATION_THRESHOLD = 0.85
DEFAULT_MAX_ATTEMPTS = 3
DEFAULT_MAX_SCRUB_MODS_BEFORE_FAIL = 10


def decide_repair(
    diff: FactDiffReport,
    scrub_report: ScrubReport,
    attempt: int,
    max_attempts: int = DEFAULT_MAX_ATTEMPTS,
    preservation_threshold: float = DEFAULT_PRESERVATION_THRESHOLD,
) -> RepairDecision:
    """Decide the next repair-loop state.

    Args:
        diff: Fact drift report comparing source and candidate.
        scrub_report: Metadata scrub report for the candidate.
        attempt: Current attempt number (1-indexed, 0 means initial).
        max_attempts: Maximum repair attempts before failing.
        preservation_threshold: Minimum preservation score to accept.

    Returns:
        RepairDecision.ACCEPT, REPAIR, or FAIL.
    """
    # Fail if we've exceeded max attempts
    if attempt >= max_attempts:
        return RepairDecision.FAIL

    # Fail if too many scrub modifications suggest corrupted output
    if scrub_report.modifications > DEFAULT_MAX_SCRUB_MODS_BEFORE_FAIL:
        return RepairDecision.FAIL

    # Accept if facts are well-preserved and scrub is clean
    if diff.preservation_score >= preservation_threshold and not diff.has_drift:
        return RepairDecision.ACCEPT

    # Accept if preservation is high enough and the only remaining issue is a minor omission
    if (
        diff.preservation_score >= preservation_threshold
        and len(diff.omissions) <= 1
        and not diff.additions
        and not diff.contradictions
    ):
        return RepairDecision.ACCEPT

    # Otherwise, request repair
    return RepairDecision.REPAIR
