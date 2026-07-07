"""Unit tests for the redaction and logging safety module."""

from __future__ import annotations

import json

import pytest

from humanhand.infra.logging import (
    _is_secret_key_name,
    _redact_string,
    log_debug,
    log_error,
    log_info,
    log_warning,
    redact_value,
    safe_length,
    safe_sha256_prefix,
)

# ---------------------------------------------------------------------------
# redact_value — secret key names
# ---------------------------------------------------------------------------


class TestRedactValueSecretKeys:
    def test_api_key_fully_redacted(self) -> None:
        result = redact_value("sk-abc123verylongsecretkey", key="api_key")
        assert result == "<REDACTED_SECRET>"

    def test_apikey_variant_redacted(self) -> None:
        result = redact_value("my-secret-123", key="apikey")
        assert result == "<REDACTED_SECRET>"

    def test_secret_key_redacted(self) -> None:
        result = redact_value("s3cr3t!", key="secret")
        assert result == "<REDACTED_SECRET>"

    def test_password_key_redacted(self) -> None:
        result = redact_value("p@ssw0rd", key="password")
        assert result == "<REDACTED_SECRET>"

    def test_token_key_redacted(self) -> None:
        result = redact_value("jwt-token-here", key="token")
        assert result == "<REDACTED_SECRET>"

    def test_credential_key_redacted(self) -> None:
        result = redact_value("my-creds", key="credential")
        assert result == "<REDACTED_SECRET>"

    def test_authorization_key_redacted(self) -> None:
        result = redact_value("Bearer xyz", key="authorization")
        assert result == "<REDACTED_SECRET>"

    def test_snake_case_api_key_redacted(self) -> None:
        result = redact_value("secret123", key="api_key_name")
        assert result == "<REDACTED_SECRET>"

    def test_nested_secret_key_redacted(self) -> None:
        nested = {"auth": {"api_key": "sk-very-secret"}}
        result = redact_value(nested)
        assert result["auth"]["api_key"] == "<REDACTED_SECRET>"


# ---------------------------------------------------------------------------
# _is_secret_key_name
# ---------------------------------------------------------------------------


class TestIsSecretKeyName:
    def test_api_key(self) -> None:
        assert _is_secret_key_name("api_key") is True

    def test_apikey_no_underscore(self) -> None:
        assert _is_secret_key_name("apikey") is True

    def test_secret(self) -> None:
        assert _is_secret_key_name("secret") is True

    def test_password(self) -> None:
        assert _is_secret_key_name("password") is True

    def test_token(self) -> None:
        assert _is_secret_key_name("token") is True

    def test_credential(self) -> None:
        assert _is_secret_key_name("credential") is True

    def test_authorization(self) -> None:
        assert _is_secret_key_name("authorization") is True

    def test_normal_key(self) -> None:
        assert _is_secret_key_name("username") is False
        assert _is_secret_key_name("model") is False
        assert _is_secret_key_name("endpoint_host") is False

    def test_hyphenated(self) -> None:
        assert _is_secret_key_name("api-key") is True


# ---------------------------------------------------------------------------
# _redact_string — pattern-based redaction
# ---------------------------------------------------------------------------


class TestRedactString:
    def test_openai_key_redacted(self) -> None:
        result = _redact_string("Using key sk-abc123xyz456verylongsecret")
        assert "sk-abc123xyz456verylongsecret" not in result
        assert "<REDACTED_KEY>" in result

    def test_github_token_redacted(self) -> None:
        result = _redact_string("Token: ghp_1234567890abcdef1234567890")
        assert "ghp_1234567890abcdef1234567890" not in result
        assert "<REDACTED_GH_TOKEN>" in result

    def test_slack_token_redacted(self) -> None:
        result = _redact_string("xoxb-123456789012-123456789012-abcdefghijklmnop")
        assert "xoxb-" not in result or "<REDACTED_SLACK>" in result

    def test_aws_key_redacted(self) -> None:
        result = _redact_string("Key: AKIA1234567890ABCDEF")
        assert "AKIA1234567890ABCDEF" not in result
        assert "<REDACTED_AWS_KEY>" in result

    def test_bearer_redacted(self) -> None:
        result = _redact_string("Authorization: Bearer abc.def.ghi")
        assert "abc.def.ghi" not in result
        assert "Bearer <REDACTED>" in result

    def test_url_credentials_redacted(self) -> None:
        result = _redact_string("Connected to http://user:pass@example.com/api")
        assert "user:pass" not in result
        assert "<REDACTED_CREDENTIALS>" in result

    def test_normal_text_unchanged(self) -> None:
        result = _redact_string("The rewrite completed in 1.2 seconds")
        assert result == "The rewrite completed in 1.2 seconds"

    def test_api_key_inline_redacted(self) -> None:
        result = _redact_string("api_key=abc123secret")
        assert "abc123secret" not in result
        assert "<REDACTED>" in result

    def test_multiple_patterns(self) -> None:
        # Use realistic-length tokens (>20 chars after prefix for key patterns)
        result = _redact_string(
            "key=sk-abcdefghijklmnopqrstuvwxyz12345 and token=ghp_1234567890abcdef1234567890"
        )
        assert "sk-abcdefghijklmnopqrstuvwxyz12345" not in result
        assert "ghp_1234567890abcdef1234567890" not in result
        assert "<REDACTED_KEY>" in result
        assert "<REDACTED_GH_TOKEN>" in result

    def test_no_false_positive_on_short_strings(self) -> None:
        result = _redact_string("sk- short-string ghp_ normal text")
        # Short strings should not match the minimum-length patterns
        assert result == "sk- short-string ghp_ normal text"


# ---------------------------------------------------------------------------
# redact_value — complex structures
# ---------------------------------------------------------------------------


class TestRedactValueComplex:
    def test_dict_recursive(self) -> None:
        data = {
            "message": "OK",
            "config": {
                "llm_api_key": "sk-secret-key-value",
                "model": "gpt-4o",
            },
        }
        result = redact_value(data)
        assert result["message"] == "OK"
        assert result["config"]["llm_api_key"] == "<REDACTED_SECRET>"
        assert result["config"]["model"] == "gpt-4o"

    def test_list_of_dicts(self) -> None:
        data = [
            {"name": "item1", "secret": "hidden"},
            {"name": "item2", "token": "abc123"},
        ]
        result = redact_value(data)
        assert result[0]["secret"] == "<REDACTED_SECRET>"
        assert result[1]["token"] == "<REDACTED_SECRET>"

    def test_bytes_redacted(self) -> None:
        result = redact_value(b"some binary data \x00\x01")
        assert isinstance(result, str)
        assert "bytes" in result

    def test_primitives_pass_through(self) -> None:
        assert redact_value(42) == 42
        assert redact_value(3.14) == 3.14
        assert redact_value(True) is True
        assert redact_value(None) is None

    def test_never_log_keys(self) -> None:
        assert redact_value("prompt text here", key="prompt") == "<REDACTED>"
        assert redact_value("source text", key="source_text") == "<REDACTED>"
        assert redact_value("output text", key="output_text") == "<REDACTED>"
        assert redact_value("style text", key="style_text") == "<REDACTED>"
        assert redact_value("llm response", key="llm_response") == "<REDACTED>"
        assert redact_value("detector response", key="detector_response") == "<REDACTED>"

    def test_set_converted_to_list(self) -> None:
        result = redact_value({"items": {1, 2, 3}})
        assert isinstance(result["items"], list)
        assert sorted(result["items"]) == [1, 2, 3]


# ---------------------------------------------------------------------------
# Log emission (captures stderr)
# ---------------------------------------------------------------------------


class TestLogEmission:
    def test_log_info_emits_jsonl(self, capsys: pytest.CaptureFixture[str]) -> None:
        log_info("rewrite.start", "Rewrite started", model="gpt-4o-mini")
        captured = capsys.readouterr()
        assert captured.err, "Expected stderr output"
        record = json.loads(captured.err.strip())
        assert record["level"] == "info"
        assert record["event"] == "rewrite.start"
        assert record["message"] == "Rewrite started"
        assert record["model"] == "gpt-4o-mini"
        assert "timestamp" in record

    def test_log_error_emits_jsonl(self, capsys: pytest.CaptureFixture[str]) -> None:
        log_error("rewrite.failed", "LLM timeout")
        captured = capsys.readouterr()
        record = json.loads(captured.err.strip())
        assert record["level"] == "error"
        assert record["event"] == "rewrite.failed"

    def test_log_debug_emits_jsonl(self, capsys: pytest.CaptureFixture[str]) -> None:
        log_debug("cache.check", "Checking cache", sha256_prefix="abc12345")
        captured = capsys.readouterr()
        record = json.loads(captured.err.strip())
        assert record["level"] == "debug"
        assert record["sha256_prefix"] == "abc12345"

    def test_log_warning_emits_jsonl(self, capsys: pytest.CaptureFixture[str]) -> None:
        log_warning("endpoint.insecure", "HTTP endpoint used on localhost")
        captured = capsys.readouterr()
        record = json.loads(captured.err.strip())
        assert record["level"] == "warning"

    def test_api_key_redacted_in_log_message(self, capsys: pytest.CaptureFixture[str]) -> None:
        log_info("auth.check", "Using key sk-abcdef1234567890abcdef123456")
        captured = capsys.readouterr()
        record = json.loads(captured.err.strip())
        assert "sk-abcdef" not in record["message"]
        assert "<REDACTED_KEY>" in record["message"]

    def test_api_key_redacted_in_extra(self, capsys: pytest.CaptureFixture[str]) -> None:
        log_info("config.loaded", "Config loaded", api_key="sk-secret-12345")
        captured = capsys.readouterr()
        record = json.loads(captured.err.strip())
        assert record["api_key"] == "<REDACTED_SECRET>"

    def test_user_text_redacted_in_extra(self, capsys: pytest.CaptureFixture[str]) -> None:
        log_info("rewrite.complete", "Done", source_text="user's private writing")
        captured = capsys.readouterr()
        record = json.loads(captured.err.strip())
        assert record["source_text"] == "<REDACTED>"

    def test_log_fields_present(self, capsys: pytest.CaptureFixture[str]) -> None:
        log_info(
            "test.event",
            "Test message",
            elapsed_ms=150.5,
            endpoint_host="api.openai.com",
            input_length=1024,
            output_length=512,
            sha256_prefix="abcdef01",
            cache_hit=True,
            attempt=2,
            retry_reason="http_503",
            model="gpt-4o-mini",
        )
        captured = capsys.readouterr()
        record = json.loads(captured.err.strip())
        assert record["elapsed_ms"] == 150.5
        assert record["endpoint_host"] == "api.openai.com"
        assert record["input_length"] == 1024
        assert record["output_length"] == 512
        assert record["sha256_prefix"] == "abcdef01"
        assert record["cache_hit"] is True
        assert record["attempt"] == 2
        assert record["retry_reason"] == "http_503"
        assert record["model"] == "gpt-4o-mini"


# ---------------------------------------------------------------------------
# safe_length / safe_sha256_prefix
# ---------------------------------------------------------------------------


class TestSafeHelpers:
    def test_safe_length(self) -> None:
        assert safe_length("hello") == 5
        assert safe_length("") == 0
        assert safe_length(None) is None

    def test_safe_sha256_prefix(self) -> None:
        prefix = safe_sha256_prefix("hello world")
        assert len(prefix) == 8
        assert isinstance(prefix, str)

    def test_safe_sha256_deterministic(self) -> None:
        p1 = safe_sha256_prefix("hello")
        p2 = safe_sha256_prefix("hello")
        assert p1 == p2

    def test_safe_sha256_different_for_different_text(self) -> None:
        p1 = safe_sha256_prefix("hello")
        p2 = safe_sha256_prefix("world")
        assert p1 != p2

    def test_safe_sha256_custom_length(self) -> None:
        prefix = safe_sha256_prefix("test", prefix_len=16)
        assert len(prefix) == 16
