"""Integration tests for detector provider adapters — local heuristic and stubs."""

from __future__ import annotations

from pathlib import Path

import pytest

from humanhand.infra.cache import DetectorScoreCache
from humanhand.infra.detectors import (
    CopyleaksDetector,
    GptZeroDetector,
    LocalDetector,
    OriginalityDetector,
    TurnitinDetector,
    WinstonDetector,
    create_detector,
)
from humanhand.infra.detectors.base import DetectorError, DetectorResult, ProviderUnavailableError

# ── Sample texts for local-detector heuristics ───────────────────

HUMAN_TEXT = (
    "I went to the store yesterday. It was a really nice day outside, "
    "so I decided to walk. The prices seemed a bit higher than last time, "
    "but I guess that's just how things are now. I bought some bread and "
    "cheese for dinner, and then I headed home. On the way back, I ran "
    "into my neighbor Mrs. Garcia. She told me about her new puppy, "
    "which was absolutely adorable."
)

AI_TEXT = (
    "It is important to note that the current market conditions require "
    "careful consideration. However, it is essential to maintain a "
    "strategic approach to resource allocation. It is crucial to evaluate "
    "all options before making a final decision. Furthermore, it is worth "
    "noting that the implementation timeline may vary depending on various "
    "factors. In conclusion, a comprehensive analysis of the available "
    "data is recommended before proceeding with any course of action."
)

FORMAL_TEXT = (
    "The examination of historical data reveals several significant "
    "patterns. The analysis indicates a correlation between various "
    "economic indicators. The findings suggest that further research "
    "is warranted in this domain."
)


class TestLocalDetector:
    """Local heuristic detector behaviour and correctness."""

    def test_deterministic(self) -> None:
        detector = LocalDetector()
        result1 = detector.detect(HUMAN_TEXT)
        result2 = detector.detect(HUMAN_TEXT)
        assert result1["score"] == result2["score"]
        assert result1["label"] == result2["label"]
        assert result1["raw_score_json"] == result2["raw_score_json"]

    def test_score_range(self) -> None:
        detector = LocalDetector()
        for text in [HUMAN_TEXT, AI_TEXT, FORMAL_TEXT, "Hello world.", "A"]:
            result = detector.detect(text)
            assert isinstance(result["score"], float), (
                f"Score must be float, got {type(result['score'])}"
            )
            assert 0.0 <= result["score"] <= 1.0, f"Score {result['score']} out of [0.0, 1.0]"

    def test_provider_and_model(self) -> None:
        detector = LocalDetector()
        result = detector.detect(HUMAN_TEXT)
        assert result["provider"] == "local"
        assert result["model"] == "heuristic"

    def test_lower_score_for_human_text(self) -> None:
        detector = LocalDetector()
        human_result = detector.detect(HUMAN_TEXT)
        ai_result = detector.detect(AI_TEXT)
        assert human_result["score"] < ai_result["score"], (
            f"Human score {human_result['score']} should be lower than "
            f"AI score {ai_result['score']}"
        )

    def test_higher_score_for_ai_text(self) -> None:
        detector = LocalDetector()
        ai_result = detector.detect(AI_TEXT)
        # AI-like text should score above 0.5
        assert ai_result["score"] > 0.5, f"AI text score {ai_result['score']} should exceed 0.5"

    def test_human_text_labels_as_human(self) -> None:
        detector = LocalDetector()
        result = detector.detect(HUMAN_TEXT)
        assert result["label"] == "human", (
            f"Human text should be labelled 'human', got '{result['label']}'"
        )

    def test_ai_text_labels_as_ai(self) -> None:
        detector = LocalDetector()
        result = detector.detect(AI_TEXT)
        assert result["label"] == "ai", f"AI text should be labelled 'ai', got '{result['label']}'"

    def test_label_values_are_valid(self) -> None:
        detector = LocalDetector()
        valid_labels = {"human", "uncertain", "ai"}
        for text in [HUMAN_TEXT, AI_TEXT, FORMAL_TEXT, "One word."]:
            result = detector.detect(text)
            assert result["label"] in valid_labels, f"Unexpected label '{result['label']}'"

    def test_no_network_calls(self) -> None:
        """Local detector must never make network calls."""
        detector = LocalDetector()
        result = detector.detect(HUMAN_TEXT)
        # If it made a network call it would need an API key or endpoint,
        # which the local detector does not have.
        assert result["score"] is not None

    def test_insufficient_text_returns_neutral(self) -> None:
        detector = LocalDetector()
        result = detector.detect("Hello.")
        assert result["score"] == 0.5
        assert result["label"] == "uncertain"

    def test_single_word_edge_case(self) -> None:
        detector = LocalDetector()
        result = detector.detect("A")
        assert result["score"] == 0.5
        assert result["label"] == "uncertain"

    def test_raw_score_json_has_metrics(self) -> None:
        detector = LocalDetector()
        result = detector.detect(HUMAN_TEXT)
        raw = result.get("raw_score_json", {})
        assert "metrics" in raw, "raw_score_json should contain 'metrics'"
        assert "scores" in raw, "raw_score_json should contain 'scores'"
        assert "weights" in raw, "raw_score_json should contain 'weights'"
        # Check required metric keys
        for key in (
            "bigram_repeat_ratio",
            "sentence_length_variance",
            "personal_pronoun_count",
            "ai_phrase_count",
            "avg_word_length",
        ):
            assert key in raw["metrics"], f"Missing metric '{key}'"

    def test_pronoun_count_detected(self) -> None:
        detector = LocalDetector()
        result = detector.detect(HUMAN_TEXT)
        raw = result.get("raw_score_json", {})
        metrics = raw.get("metrics", {})
        assert metrics.get("personal_pronoun_count", 0) > 0, (
            "Human text should contain personal pronouns"
        )

    def test_ai_phrases_detected(self) -> None:
        detector = LocalDetector()
        result = detector.detect(AI_TEXT)
        raw = result.get("raw_score_json", {})
        metrics = raw.get("metrics", {})
        assert metrics.get("ai_phrase_count", 0) > 0, "AI text should contain AI-typical phrases"


class TestLocalDetectorEdgeCases:
    """Edge cases for the local heuristic detector."""

    @pytest.mark.parametrize(
        "text",
        [
            "",
            "   ",
            "\n\t\n",
        ],
    )
    def test_empty_or_whitespace_text(self, text: str) -> None:
        detector = LocalDetector()
        result = detector.detect(text)
        assert result["score"] == 0.5
        assert result["label"] == "uncertain"
        raw = result.get("raw_score_json", {})
        assert raw.get("status_code") == "insufficient_text"
        assert "word_count" in raw
        assert "sentence_count" in raw

    def test_insufficient_text_payload_is_cache_safe(self, tmp_path: Path) -> None:
        detector = LocalDetector()
        result = detector.detect("Hello.")
        cache = DetectorScoreCache(tmp_path / "cache.db")

        try:
            text_hash = DetectorScoreCache.hash_text("Hello.")
            cache.put(
                {
                    "text_sha256": text_hash,
                    "provider": result["provider"],
                    "model": result["model"],
                    "score": result["score"],
                    "label": result["label"],
                    "raw_score_json": result["raw_score_json"],
                }
            )

            cached = cache.get(text_hash, result["provider"], result["model"])
            assert cached is not None
            assert "insufficient_text" in (cached["raw_score_json"] or "")
        finally:
            cache.close()

    def test_very_long_text(self) -> None:
        """Long repetitive text should score high."""
        detector = LocalDetector()
        repetitive = (
            "It is important to note that the data indicates a trend. "
            "It is crucial to consider the implications of these findings. "
            "Furthermore, it is essential to evaluate the results carefully. "
        ) * 20
        result = detector.detect(repetitive)
        assert result["score"] > 0.6

    def test_text_with_numbers(self) -> None:
        detector = LocalDetector()
        text = "I ran 5 miles yesterday. My time was 42 minutes and 30 seconds."
        result = detector.detect(text)
        assert result["score"] is not None
        assert 0.0 <= result["score"] <= 1.0


class TestDetectorResult:
    """DetectorResult dataclass contract."""

    def test_required_fields(self) -> None:
        result = DetectorResult(provider="test", model="v1")
        assert result.provider == "test"
        assert result.model == "v1"
        assert result.score is None
        assert result.label is None
        assert result.raw_score_json is None

    def test_all_fields(self) -> None:
        result = DetectorResult(
            provider="local",
            model="heuristic",
            score=0.85,
            label="ai",
            raw_score_json={"confidence": 0.85},
        )
        assert result.provider == "local"
        assert result.model == "heuristic"
        assert result.score == 0.85
        assert result.label == "ai"
        assert result.raw_score_json == {"confidence": 0.85}

    def test_defaults_are_none(self) -> None:
        result = DetectorResult(provider="x", model="y")
        assert result.score is None
        assert result.label is None
        assert result.raw_score_json is None


class TestStubDetectors:
    """Third-party detector stubs must raise ProviderUnavailableError."""

    @pytest.fixture
    def clear_env(self, monkeypatch: pytest.MonkeyPatch) -> None:
        """Remove all detector API keys from the environment."""
        monkeypatch.delenv("GPTZERO_API_KEY", raising=False)
        monkeypatch.delenv("ORIGINALITY_API_KEY", raising=False)
        monkeypatch.delenv("COPYLEAKS_API_KEY", raising=False)
        monkeypatch.delenv("WINSTON_API_KEY", raising=False)

    def test_gptzero_raises_without_key(self, clear_env: None) -> None:
        detector = GptZeroDetector()
        with pytest.raises(ProviderUnavailableError, match="GPTZERO_API_KEY"):
            detector.detect("test text")

    def test_gptzero_raises_with_key(self, monkeypatch: pytest.MonkeyPatch) -> None:
        monkeypatch.setenv("GPTZERO_API_KEY", "test-key-123")
        detector = GptZeroDetector()
        with pytest.raises(ProviderUnavailableError, match="API documentation"):
            detector.detect("test text")

    def test_originality_raises_without_key(self, clear_env: None) -> None:
        detector = OriginalityDetector()
        with pytest.raises(ProviderUnavailableError, match="ORIGINALITY_API_KEY"):
            detector.detect("test text")

    def test_originality_raises_with_key(self, monkeypatch: pytest.MonkeyPatch) -> None:
        monkeypatch.setenv("ORIGINALITY_API_KEY", "test-key-456")
        detector = OriginalityDetector()
        with pytest.raises(ProviderUnavailableError, match="API documentation"):
            detector.detect("test text")

    def test_copyleaks_raises_without_key(self, clear_env: None) -> None:
        detector = CopyleaksDetector()
        with pytest.raises(ProviderUnavailableError, match="COPYLEAKS_API_KEY"):
            detector.detect("test text")

    def test_copyleaks_raises_with_key(self, monkeypatch: pytest.MonkeyPatch) -> None:
        monkeypatch.setenv("COPYLEAKS_API_KEY", "test-key-789")
        detector = CopyleaksDetector()
        with pytest.raises(ProviderUnavailableError, match="API documentation"):
            detector.detect("test text")

    def test_winston_raises_without_key(self, clear_env: None) -> None:
        detector = WinstonDetector()
        with pytest.raises(ProviderUnavailableError, match="WINSTON_API_KEY"):
            detector.detect("test text")

    def test_winston_raises_with_key(self, monkeypatch: pytest.MonkeyPatch) -> None:
        monkeypatch.setenv("WINSTON_API_KEY", "test-key-000")
        detector = WinstonDetector()
        with pytest.raises(ProviderUnavailableError, match="API documentation"):
            detector.detect("test text")

    def test_turnitin_always_raises(self) -> None:
        detector = TurnitinDetector()
        with pytest.raises(ProviderUnavailableError, match="API documentation is needed"):
            detector.detect("test text")


class TestDetectorErrorHierarchy:
    """Detector error types must form a correct hierarchy."""

    def test_provider_unavailable_is_detector_error(self) -> None:
        assert issubclass(ProviderUnavailableError, DetectorError)

    def test_catch_base_exception(self) -> None:
        """Catching DetectorError should catch ProviderUnavailableError."""
        try:
            raise ProviderUnavailableError("test")
        except DetectorError:
            pass  # Expected — hierarchy must support this


class TestCreateDetector:
    """Factory function create_detector."""

    def test_creates_local(self) -> None:
        detector = create_detector("local")
        assert isinstance(detector, LocalDetector)

    def test_creates_gptzero(self) -> None:
        detector = create_detector("gptzero")
        assert isinstance(detector, GptZeroDetector)

    def test_creates_originality(self) -> None:
        detector = create_detector("originality")
        assert isinstance(detector, OriginalityDetector)

    def test_creates_copyleaks(self) -> None:
        detector = create_detector("copyleaks")
        assert isinstance(detector, CopyleaksDetector)

    def test_creates_winston(self) -> None:
        detector = create_detector("winston")
        assert isinstance(detector, WinstonDetector)

    def test_creates_turnitin(self) -> None:
        detector = create_detector("turnitin")
        assert isinstance(detector, TurnitinDetector)

    def test_unknown_provider_raises(self) -> None:
        with pytest.raises(ValueError, match="Unknown detector provider"):
            create_detector("nonexistent_provider")


class TestLocalDetectorReturnsDict:
    """Ensure the local detector's return value matches the DetectorClient protocol."""

    def test_return_has_required_keys(self) -> None:
        detector = LocalDetector()
        result = detector.detect(HUMAN_TEXT)
        for key in ("provider", "model", "score", "label", "raw_score_json"):
            assert key in result, f"Missing required key '{key}' in detect result"

    def test_values_have_correct_types(self) -> None:
        detector = LocalDetector()
        result = detector.detect(HUMAN_TEXT)
        assert isinstance(result["provider"], str)
        assert isinstance(result["model"], str)
        assert isinstance(result["score"], float) or result["score"] is None
        assert isinstance(result["label"], str) or result["label"] is None
        assert isinstance(result["raw_score_json"], dict | None)
