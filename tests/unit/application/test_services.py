"""Unit tests for application services with fake port implementations."""

from __future__ import annotations

import hashlib
from pathlib import Path
from typing import Any

import pytest

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
from humanhand.domain.types import (
    FactDiffReport,
    PromptContract,
    ScrubReport,
)

# ── Fake port implementations ──────────────────────────────────


class FakeLlmClient:
    """Fake LLM client that echoes with style transformation markers."""

    def __init__(self, responses: list[str] | None = None) -> None:
        self._responses = responses or []
        self._call_count = 0
        self.calls: list[PromptContract] = []

    def rewrite(self, prompt_contract: PromptContract) -> str:
        self.calls.append(prompt_contract)
        if self._call_count < len(self._responses):
            result = self._responses[self._call_count]
        else:
            # Default: return a rewritten version that preserves source facts
            result = (
                "The Eiffel Tower stands at 330 meters tall. "
                "It was completed in the year 1889 and attracts approximately "
                "7 million visitors each year."
            )
        self._call_count += 1
        return result


class FakeDetectorClient:
    """Fake detector that returns configurable scores."""

    def __init__(self, score: float = 0.05, label: str = "human") -> None:
        self._score = score
        self._label = label
        self.detect_calls: list[str] = []

    def detect(self, text: str) -> dict[str, Any]:
        self.detect_calls.append(text)
        return {
            "provider": "fake",
            "model": "fake-v1",
            "score": self._score,
            "label": self._label,
            "raw_score_json": None,
        }


class FakeFileWriter:
    """Fake file writer that records calls."""

    def __init__(self) -> None:
        self.writes: list[tuple[Path, str]] = []

    def write(
        self,
        output_path: str | Path,
        text: str,
        input_paths: list[str | Path] | None = None,
    ) -> Path:
        self.writes.append((Path(output_path), text))
        return Path(output_path)


class FakeLogger:
    """Fake logger that records events."""

    def __init__(self) -> None:
        self.events: list[dict[str, Any]] = []

    def log(self, event: str, level: str = "info", **fields: Any) -> None:
        self.events.append({"event": event, "level": level, **fields})


class FakeCache:
    """Fake detector cache."""

    def __init__(self) -> None:
        self._store: dict[str, dict[str, Any]] = {}
        self.gets: list[tuple[str, str, str, int]] = []
        self.puts: list[dict[str, Any]] = []

    def get(
        self, text_hash: str, provider: str, model: str, schema_version: int
    ) -> dict[str, Any] | None:
        self.gets.append((text_hash, provider, model, schema_version))
        key = f"{text_hash}:{provider}:{model}:{schema_version}"
        return self._store.get(key)

    def put(self, record: dict[str, Any]) -> None:
        self.puts.append(record)
        sv = record.get("schema_version", 1)
        key = f"{record['text_sha256']}:{record['provider']}:{record['model']}:{sv}"
        self._store[key] = record

    def close(self) -> None:
        pass


# ── Test fixtures ──────────────────────────────────────────────


SOURCE_TEXT = (
    "The Eiffel Tower is 330 meters tall. "
    "It was completed in 1889 and receives 7 million visitors annually."
)

STYLE_TEXT = (
    "I went to the store yesterday. The prices were quite reasonable. "
    "I bought some bread and cheese for dinner."
)


# ── Rewrite tests ──────────────────────────────────────────────


class TestRewrite:
    def test_successful_rewrite(self) -> None:
        llm = FakeLlmClient()
        writer = FakeFileWriter()
        logger = FakeLogger()

        result = rewrite(
            source_text=SOURCE_TEXT,
            style_text=STYLE_TEXT,
            output_path="output.txt",
            llm_client=llm,
            file_writer=writer,
            logger=logger,
        )

        assert isinstance(result, RewriteResult)
        assert result.output_path == "output.txt"
        assert result.input_chars > 0
        assert result.output_chars > 0
        assert result.repair_attempts == 0
        assert result.preservation_score >= 0.0
        assert len(writer.writes) == 1
        assert len(llm.calls) == 1
        # Check logger events
        assert any(e["event"] == "rewrite.start" for e in logger.events)
        assert any(e["event"] == "rewrite.end" for e in logger.events)

    def test_empty_source_raises(self) -> None:
        llm = FakeLlmClient()
        writer = FakeFileWriter()
        logger = FakeLogger()

        with pytest.raises(ValueError, match="Source text must not be empty"):
            rewrite(
                source_text="",
                style_text=STYLE_TEXT,
                output_path="output.txt",
                llm_client=llm,
                file_writer=writer,
                logger=logger,
            )

    def test_empty_style_raises(self) -> None:
        llm = FakeLlmClient()
        writer = FakeFileWriter()
        logger = FakeLogger()

        with pytest.raises(ValueError, match="Style text must not be empty"):
            rewrite(
                source_text=SOURCE_TEXT,
                style_text="",
                output_path="output.txt",
                llm_client=llm,
                file_writer=writer,
                logger=logger,
            )

    def test_whitespace_source_raises(self) -> None:
        llm = FakeLlmClient()
        writer = FakeFileWriter()
        logger = FakeLogger()

        with pytest.raises(ValueError, match="Source text must not be empty"):
            rewrite(
                source_text="   \n  ",
                style_text=STYLE_TEXT,
                output_path="output.txt",
                llm_client=llm,
                file_writer=writer,
                logger=logger,
            )

    def test_source_exceeds_max_chars(self) -> None:
        llm = FakeLlmClient()
        writer = FakeFileWriter()
        logger = FakeLogger()

        with pytest.raises(ValueError, match="exceeds maximum"):
            rewrite(
                source_text="x" * 600,
                style_text=STYLE_TEXT,
                output_path="output.txt",
                llm_client=llm,
                file_writer=writer,
                logger=logger,
                max_chars=500,
            )

    def test_style_exceeds_max_chars(self) -> None:
        llm = FakeLlmClient()
        writer = FakeFileWriter()
        logger = FakeLogger()

        with pytest.raises(ValueError, match="exceeds maximum"):
            rewrite(
                source_text=SOURCE_TEXT,
                style_text="x" * 600,
                output_path="output.txt",
                llm_client=llm,
                file_writer=writer,
                logger=logger,
                max_chars=500,
            )

    def test_repair_loop_triggers_on_fact_loss(self) -> None:
        """When LLM drops facts, a repair attempt should be made."""
        # First response drops key facts; second restores them
        llm = FakeLlmClient(
            responses=[
                "The tower is tall. It was built long ago.",
                SOURCE_TEXT,  # Second attempt restores facts
            ]
        )
        writer = FakeFileWriter()
        logger = FakeLogger()

        result = rewrite(
            source_text=SOURCE_TEXT,
            style_text=STYLE_TEXT,
            output_path="output.txt",
            llm_client=llm,
            file_writer=writer,
            logger=logger,
            max_repair_attempts=3,
        )

        # At least one LLM call was made
        assert len(llm.calls) >= 1
        assert result.output_chars > 0

    def test_rewrite_raises_when_repair_budget_is_exhausted(self) -> None:
        llm = FakeLlmClient(
            responses=[
                "The tower is tall. It was built long ago.",
                "The tower is tall. It was built long ago.",
            ]
        )
        writer = FakeFileWriter()
        logger = FakeLogger()

        with pytest.raises(RewriteQualityError, match="Fact drift repair failed"):
            rewrite(
                source_text=SOURCE_TEXT,
                style_text=STYLE_TEXT,
                output_path="output.txt",
                llm_client=llm,
                file_writer=writer,
                logger=logger,
                max_repair_attempts=1,
            )

        assert len(llm.calls) == 2
        assert len(writer.writes) == 0
        assert any(e["event"] == "rewrite.fail" for e in logger.events)
        assert not any(e["event"] == "rewrite.end" for e in logger.events)


# ── Verify tests ───────────────────────────────────────────────


class TestVerify:
    def test_verify_with_detector(self) -> None:
        detector = FakeDetectorClient(score=0.15, label="human")
        logger = FakeLogger()

        result = verify(
            text=SOURCE_TEXT,
            detector_client=detector,
            logger=logger,
            provider="fake",
            model="fake-v1",
            cache_enabled=False,
        )

        assert isinstance(result, VerifyResult)
        assert result.provider == "fake"
        assert result.model == "fake-v1"
        assert result.score == 0.15
        assert result.label == "human"
        assert result.cache_hit is False
        assert len(detector.detect_calls) == 1

    def test_verify_cache_hit(self) -> None:
        detector = FakeDetectorClient()
        cache = FakeCache()
        logger = FakeLogger()

        text_hash = hashlib.sha256(SOURCE_TEXT.encode("utf-8")).hexdigest()
        cache.put(
            {
                "text_sha256": text_hash,
                "provider": "fake",
                "model": "fake-v1",
                "score": 0.92,
                "label": "ai",
            }
        )

        result = verify(
            text=SOURCE_TEXT,
            detector_client=detector,
            cache=cache,
            logger=logger,
            provider="fake",
            model="fake-v1",
            cache_enabled=True,
        )

        assert result.cache_hit is True
        assert result.score == 0.92
        assert result.label == "ai"
        # Detector should NOT have been called
        assert len(detector.detect_calls) == 0

    def test_verify_cache_miss_calls_detector(self) -> None:
        detector = FakeDetectorClient(score=0.05, label="human")
        cache = FakeCache()
        logger = FakeLogger()

        result = verify(
            text=SOURCE_TEXT,
            detector_client=detector,
            cache=cache,
            logger=logger,
            provider="fake",
            model="fake-v1",
            cache_enabled=True,
        )

        assert result.cache_hit is False
        assert result.score == 0.05
        assert len(detector.detect_calls) == 1
        # Should have stored in cache
        assert len(cache.puts) == 1

    def test_verify_cache_disabled(self) -> None:
        detector = FakeDetectorClient()
        cache = FakeCache()
        logger = FakeLogger()

        result = verify(
            text=SOURCE_TEXT,
            detector_client=detector,
            cache=cache,
            logger=logger,
            cache_enabled=False,
        )

        assert result.cache_hit is False
        assert len(cache.gets) == 0
        assert len(cache.puts) == 0


# ── Diff Facts tests ───────────────────────────────────────────


class TestDiffFactsService:
    def test_diff_facts_identical_text(self) -> None:
        logger = FakeLogger()

        result = diff_facts_service(
            source_text=SOURCE_TEXT,
            candidate_text=SOURCE_TEXT,
            logger=logger,
        )

        assert isinstance(result, DiffFactsResult)
        assert result.report.preservation_score >= 0.9
        assert result.source_chars == len(SOURCE_TEXT)
        assert result.candidate_chars == len(SOURCE_TEXT)

    def test_diff_facts_different_text(self) -> None:
        logger = FakeLogger()

        result = diff_facts_service(
            source_text=SOURCE_TEXT,
            candidate_text="Completely different text about cats and dogs.",
            logger=logger,
        )

        assert isinstance(result, DiffFactsResult)
        # Facts from SOURCE_TEXT (330, 1889, 7 million) should be missing
        assert len(result.report.omissions) > 0 or result.report.preservation_score < 1.0

    def test_diff_facts_logs_events(self) -> None:
        logger = FakeLogger()

        diff_facts_service(
            source_text=SOURCE_TEXT,
            candidate_text=SOURCE_TEXT,
            logger=logger,
        )

        assert any(e["event"] == "diff_facts.start" for e in logger.events)
        assert any(e["event"] == "diff_facts.end" for e in logger.events)


# ── Scrub tests ────────────────────────────────────────────────


class TestScrubService:
    def test_scrub_audit_only(self) -> None:
        logger = FakeLogger()

        result = scrub_service(
            text=SOURCE_TEXT,
            logger=logger,
            audit_only=True,
        )

        assert isinstance(result, ScrubResult)
        assert result.audit_only is True
        assert result.output_path is None

    def test_scrub_with_write(self) -> None:
        writer = FakeFileWriter()
        logger = FakeLogger()

        result = scrub_service(
            text=SOURCE_TEXT,
            file_writer=writer,
            logger=logger,
            output_path="cleaned.txt",
            audit_only=False,
        )

        assert result.audit_only is False
        assert result.output_path == "cleaned.txt"
        assert len(writer.writes) == 1

    def test_scrub_write_requires_output_path(self) -> None:
        logger = FakeLogger()

        with pytest.raises(ValueError, match="output_path is required"):
            scrub_service(
                text=SOURCE_TEXT,
                logger=logger,
                audit_only=False,
            )

    def test_scrub_write_requires_file_writer(self) -> None:
        logger = FakeLogger()

        with pytest.raises(ValueError, match="file_writer is required"):
            scrub_service(
                text=SOURCE_TEXT,
                logger=logger,
                output_path="out.txt",
                audit_only=False,
            )

    def test_scrub_detects_bom_in_audit(self) -> None:
        logger = FakeLogger()
        text_with_bom = "﻿" + SOURCE_TEXT

        result = scrub_service(
            text=text_with_bom,
            logger=logger,
            audit_only=True,
        )

        assert any(f.category == "bom" for f in result.report.findings)


# ── Health tests ───────────────────────────────────────────────


class TestHealth:
    def test_health_ok(self) -> None:
        result = health(
            version="0.1.0",
            python_version="3.11.5",
        )

        assert isinstance(result, HealthResult)
        assert result.status == "ok"
        assert result.version == "0.1.0"
        assert result.python_version == "3.11.5"

    def test_health_reports_config(self) -> None:
        result = health(
            version="0.1.0",
            python_version="3.11.5",
            llm_configured=True,
            detector_provider="gptzero",
        )

        assert result.config_summary["llm_configured"] is True
        assert result.config_summary["detector_provider"] == "gptzero"


# ── Result type tests ──────────────────────────────────────────


class TestResultTypes:
    def test_rewrite_result_defaults(self) -> None:
        r = RewriteResult(output_path="out.txt", input_chars=100, output_chars=80)
        assert r.repair_attempts == 0
        assert r.preservation_score == 1.0
        assert r.fact_diff is None

    def test_verify_result_defaults(self) -> None:
        r = VerifyResult(provider="local", model="heuristic")
        assert r.score is None
        assert r.label is None
        assert r.cache_hit is False

    def test_diff_facts_result(self) -> None:
        report = FactDiffReport(preservation_score=0.95)
        r = DiffFactsResult(report=report, source_chars=100, candidate_chars=95)
        assert r.report.preservation_score == 0.95

    def test_scrub_result(self) -> None:
        report = ScrubReport()
        r = ScrubResult(report=report, audit_only=True)
        assert r.audit_only is True

    def test_health_result_defaults(self) -> None:
        r = HealthResult()
        assert r.status == "ok"
        assert r.config_summary == {}
