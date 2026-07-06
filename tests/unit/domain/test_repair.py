"""Unit tests for repair loop decision logic."""

from humanhand.domain.repair import decide_repair
from humanhand.domain.types import (
    FactAnchor,
    FactDiffReport,
    RepairDecision,
    ScrubReport,
)


class TestDecideRepair:
    def test_accept_clean_perfect(self) -> None:
        diff = FactDiffReport(
            omissions=(),
            additions=(),
            contradictions=(),
            preservation_score=1.0,
            total_source_anchors=5,
            total_candidate_anchors=5,
        )
        scrub = ScrubReport(modifications=0)
        result = decide_repair(diff, scrub, attempt=0)
        assert result == RepairDecision.ACCEPT

    def test_accept_high_preservation_no_drift(self) -> None:
        diff = FactDiffReport(
            preservation_score=0.95,
            total_source_anchors=10,
            total_candidate_anchors=10,
        )
        scrub = ScrubReport(modifications=0)
        result = decide_repair(diff, scrub, attempt=0)
        assert result == RepairDecision.ACCEPT

    def test_repair_low_preservation(self) -> None:
        diff = FactDiffReport(
            omissions=(
                FactAnchor(text="42", category="number", position=0),
                FactAnchor(text="John", category="entity", position=10),
            ),
            preservation_score=0.5,
            total_source_anchors=4,
            total_candidate_anchors=2,
        )
        scrub = ScrubReport(modifications=0)
        result = decide_repair(diff, scrub, attempt=0)
        assert result == RepairDecision.REPAIR

    def test_repair_with_drift(self) -> None:
        diff = FactDiffReport(
            omissions=(FactAnchor(text="42", category="number", position=0),),
            preservation_score=0.75,
            total_source_anchors=4,
            total_candidate_anchors=3,
        )
        scrub = ScrubReport(modifications=0)
        result = decide_repair(diff, scrub, attempt=0)
        assert result == RepairDecision.REPAIR

    def test_fail_max_attempts(self) -> None:
        diff = FactDiffReport(preservation_score=0.5)
        scrub = ScrubReport(modifications=0)
        result = decide_repair(diff, scrub, attempt=3, max_attempts=3)
        assert result == RepairDecision.FAIL

    def test_fail_exceeded_max_attempts(self) -> None:
        diff = FactDiffReport(preservation_score=0.5)
        scrub = ScrubReport(modifications=0)
        result = decide_repair(diff, scrub, attempt=5, max_attempts=3)
        assert result == RepairDecision.FAIL

    def test_fail_excessive_scrub_mods(self) -> None:
        diff = FactDiffReport(preservation_score=1.0)
        scrub = ScrubReport(modifications=15)
        result = decide_repair(diff, scrub, attempt=0)
        assert result == RepairDecision.FAIL

    def test_accept_single_minor_omission(self) -> None:
        diff = FactDiffReport(
            omissions=(FactAnchor(text="minor", category="entity", position=0),),
            preservation_score=0.9,
            total_source_anchors=10,
            total_candidate_anchors=9,
        )
        scrub = ScrubReport(modifications=0)
        result = decide_repair(diff, scrub, attempt=0)
        assert result == RepairDecision.ACCEPT

    def test_custom_threshold(self) -> None:
        diff = FactDiffReport(
            omissions=(
                FactAnchor(text="x", category="number", position=0),
                FactAnchor(text="y", category="entity", position=10),
            ),
            preservation_score=0.7,
            total_source_anchors=5,
            total_candidate_anchors=3,
        )
        scrub = ScrubReport(modifications=0)
        # With threshold 0.75, low preservation + 2 omissions should repair
        result = decide_repair(diff, scrub, attempt=0, preservation_threshold=0.75)
        assert result == RepairDecision.REPAIR

    def test_custom_max_attempts(self) -> None:
        diff = FactDiffReport(preservation_score=0.5)
        scrub = ScrubReport(modifications=0)
        result = decide_repair(diff, scrub, attempt=2, max_attempts=5)
        assert result == RepairDecision.REPAIR

    def test_repair_when_unsupported_addition_present(self) -> None:
        diff = FactDiffReport(
            additions=(FactAnchor(text="$500", category="number", position=5),),
            preservation_score=0.95,
            total_source_anchors=5,
            total_candidate_anchors=6,
        )
        scrub = ScrubReport(modifications=0)
        result = decide_repair(diff, scrub, attempt=0)
        assert result == RepairDecision.REPAIR

    def test_repair_when_contradiction_present(self) -> None:
        diff = FactDiffReport(
            contradictions=(
                (
                    FactAnchor(text="$50", category="number", position=0),
                    FactAnchor(text="$60", category="number", position=0),
                ),
            ),
            preservation_score=0.95,
            total_source_anchors=5,
            total_candidate_anchors=5,
        )
        scrub = ScrubReport(modifications=0)
        result = decide_repair(diff, scrub, attempt=0)
        assert result == RepairDecision.REPAIR
