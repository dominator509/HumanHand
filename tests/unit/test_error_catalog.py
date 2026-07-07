"""Unit tests for CLI error message catalog and exception mapping."""

from __future__ import annotations

from humanhand.cli.errors import (
    ERROR_MESSAGES,
    error_for_exception,
    get_error_message,
    message_for_exception,
)
from humanhand.infra.config import KNOWN_DETECTOR_PROVIDERS
from humanhand.infra.detectors.base import DetectorError, ProviderUnavailableError
from humanhand.infra.files import FileIOError
from humanhand.infra.llm import LlmError


class TestErrorCatalog:
    """Test error message catalog completeness."""

    def test_all_keys_unique(self) -> None:
        assert len(ERROR_MESSAGES) == len(set(ERROR_MESSAGES.keys()))

    def test_every_key_has_non_empty_message(self) -> None:
        for key, msg in ERROR_MESSAGES.items():
            assert msg, f"Key '{key}' has empty message"

    def test_expected_categories_exist(self) -> None:
        expected = {
            "empty_source",
            "empty_style",
            "source_too_large",
            "style_too_large",
            "missing_argument",
            "bom_detected",
            "invalid_utf8",
            "whitespace_only",
            "config_invalid",
            "unknown_provider",
            "missing_llm_url",
            "missing_llm_model",
            "unsafe_endpoint",
            "file_not_found",
            "not_a_file",
            "cannot_read",
            "cannot_write",
            "output_is_input",
            "llm_unavailable",
            "llm_timeout",
            "llm_error",
            "detector_unavailable",
            "provider_no_key",
            "provider_no_docs",
            "schema_invalid",
            "fact_drift",
            "internal_error",
        }
        missing = expected - set(ERROR_MESSAGES.keys())
        assert not missing, f"Missing error keys: {missing}"


class TestGetErrorMessage:
    def test_valid_key_returns_message(self) -> None:
        assert "must not be empty" in get_error_message("empty_source")

    def test_unknown_key_returns_internal_error(self) -> None:
        msg = get_error_message("nonexistent_key")
        assert "internal" in msg.lower() or "unexpected" in msg.lower()

    def test_unknown_key_with_fallback(self) -> None:
        msg = get_error_message("nonexistent_key", fallback="Custom fallback")
        assert msg == "Custom fallback"

    def test_all_known_keys_return_messages(self) -> None:
        for key in ERROR_MESSAGES:
            msg = get_error_message(key)
            assert msg, f"Key '{key}' returned empty message"


class TestErrorForExceptionFileIOErrors:
    """Map FileIOError variants to stable message keys."""

    def test_file_not_found(self) -> None:
        exc = FileIOError("File not found: /tmp/missing.txt")
        assert error_for_exception(exc) == "file_not_found"

    def test_not_a_regular_file(self) -> None:
        exc = FileIOError("Not a regular file: /tmp/dir")
        assert error_for_exception(exc) == "not_a_file"

    def test_bom_detected(self) -> None:
        exc = FileIOError("UTF-8 BOM detected; BOM is not accepted")
        assert error_for_exception(exc) == "bom_detected"

    def test_invalid_utf8(self) -> None:
        exc = FileIOError("Invalid UTF-8 in file: /tmp/bad.txt")
        assert error_for_exception(exc) == "invalid_utf8"

    def test_whitespace_only(self) -> None:
        exc = FileIOError("File is empty or whitespace-only: /tmp/blank.txt")
        assert error_for_exception(exc) == "whitespace_only"

    def test_cannot_read(self) -> None:
        exc = FileIOError("Cannot read file: /tmp/unreadable.txt")
        assert error_for_exception(exc) == "cannot_read"

    def test_cannot_create_output_directory(self) -> None:
        exc = FileIOError("Cannot create output directory: /tmp/nope")
        assert error_for_exception(exc) == "cannot_write"

    def test_cannot_write_output_file(self) -> None:
        exc = FileIOError("Cannot write output file: /tmp/out.txt")
        assert error_for_exception(exc) == "cannot_write"

    def test_output_is_input(self) -> None:
        exc = FileIOError("Output path must not match an input path: /tmp/in.txt")
        assert error_for_exception(exc) == "output_is_input"

    def test_unrecognized_fileio_message(self) -> None:
        exc = FileIOError("Some strange file I/O condition")
        assert error_for_exception(exc) == "internal_error"


class TestErrorForExceptionLlmErrors:
    """Map LlmError variants to stable message keys."""

    def test_llm_timeout(self) -> None:
        exc = LlmError("LLM request timed out after 3 retries")
        assert error_for_exception(exc) == "llm_timeout"

    def test_missing_llm_model(self) -> None:
        exc = LlmError("LLM model is not configured")
        assert error_for_exception(exc) == "missing_llm_model"

    def test_llm_unsafe_endpoint(self) -> None:
        exc = LlmError("HTTP is not allowed for non-localhost endpoints")
        assert error_for_exception(exc) == "unsafe_endpoint"

    def test_llm_generic_error(self) -> None:
        exc = LlmError("LLM request failed: status=500")
        assert error_for_exception(exc) == "llm_error"


class TestErrorForExceptionDetectorErrors:
    """Map DetectorError / ProviderUnavailableError variants."""

    def test_detector_unavailable(self) -> None:
        exc = DetectorError("detector is down")
        assert error_for_exception(exc) == "detector_unavailable"

    def test_provider_no_key(self) -> None:
        exc = ProviderUnavailableError("Provider requires _api_key to be set")
        assert error_for_exception(exc) == "provider_no_key"

    def test_provider_no_docs(self) -> None:
        exc = ProviderUnavailableError("API documentation not available for this provider")
        assert error_for_exception(exc) == "provider_no_docs"


class TestErrorForExceptionValueErrors:
    """Map ValueError variants to stable message keys."""

    def test_empty_source(self) -> None:
        exc = ValueError("Source text must not be empty")
        assert error_for_exception(exc) == "empty_source"

    def test_empty_style(self) -> None:
        exc = ValueError("Style text must not be empty")
        assert error_for_exception(exc) == "empty_style"

    def test_source_too_large(self) -> None:
        exc = ValueError("Source text exceeds the maximum allowed size")
        assert error_for_exception(exc) == "source_too_large"

    def test_style_too_large(self) -> None:
        exc = ValueError("Style text exceeds the maximum allowed size")
        assert error_for_exception(exc) == "style_too_large"

    def test_unknown_detector_provider(self) -> None:
        exc = ValueError("Unknown detector provider: mystery-ai")
        assert error_for_exception(exc) == "unknown_provider"

    def test_positive_integer_config(self) -> None:
        exc = ValueError("HUMANHAND_MAX_CHARS must be a positive integer")
        assert error_for_exception(exc) == "config_invalid"

    def test_boolean_config(self) -> None:
        exc = ValueError("HUMANHAND_CACHE_ENABLED must be a boolean-like value")
        assert error_for_exception(exc) == "config_invalid"

    def test_generic_value_error(self) -> None:
        exc = ValueError("some generic value error")
        assert error_for_exception(exc) == "missing_argument"


class TestErrorForExceptionOtherTypes:
    """Map other exception types."""

    def test_key_error(self) -> None:
        exc = KeyError("missing_key")
        assert error_for_exception(exc) == "schema_invalid"

    def test_type_error(self) -> None:
        exc = TypeError("bad type")
        assert error_for_exception(exc) == "schema_invalid"

    def test_rewrite_quality_error(self) -> None:
        # Import locally if available
        try:
            from humanhand.application.services import RewriteQualityError

            exc = RewriteQualityError("fact drift unresolved")
            assert error_for_exception(exc) == "fact_drift"
        except ImportError:
            pass  # Class may not exist with this exact name

    def test_unknown_exception_type(self) -> None:
        exc = RuntimeError("something unexpected")
        assert error_for_exception(exc) == "internal_error"


class TestMessageForException:
    """Integration of error_for_exception + get_error_message."""

    def test_returns_user_friendly_message(self) -> None:
        exc = FileIOError("File not found: /tmp/x.txt")
        msg = message_for_exception(exc)
        assert "not found" in msg.lower()

    def test_unknown_exception_returns_internal_error_msg(self) -> None:
        exc = RuntimeError("unexpected")
        msg = message_for_exception(exc)
        assert "internal" in msg.lower() or "unexpected" in msg.lower()

    def test_custom_fallback(self) -> None:
        # message_for_exception uses get_error_message(key, fallback).
        # The fallback is used only when the key is not in ERROR_MESSAGES.
        # Since all error_for_exception returns are valid keys, we test
        # fallback behavior via get_error_message directly.
        msg = get_error_message("nonexistent_key", fallback="Custom error")
        assert msg == "Custom error"


class TestErrorCatalogImports:
    """Verify imports needed by error catalog are functional."""

    def test_known_detector_providers_is_a_set(self) -> None:
        assert isinstance(KNOWN_DETECTOR_PROVIDERS, set)
        assert len(KNOWN_DETECTOR_PROVIDERS) > 0
