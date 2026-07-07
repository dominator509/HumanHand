"""Integration tests for endpoint security and schema validation."""

from __future__ import annotations

import pytest
import respx

from humanhand.domain.types import PromptContract
from humanhand.infra.config import Config
from humanhand.infra.http import HttpError, build_client, validate_endpoint
from humanhand.infra.llm import LlmError, OpenAiLlmClient

# ---------------------------------------------------------------------------
# Endpoint validation (unit-level exercised via integration harness)
# ---------------------------------------------------------------------------


class TestEndpointValidation:
    """Validate HTTPS enforcement and localhost rules."""

    def test_https_allowed(self) -> None:
        url = validate_endpoint("https://api.example.com")
        assert url.startswith("https://")

    def test_http_rejected_for_non_localhost(self) -> None:
        with pytest.raises(HttpError, match="HTTP is not allowed"):
            validate_endpoint("http://api.example.com/v1")

    def test_http_localhost_allowed_without_flag(self) -> None:
        url = validate_endpoint("http://localhost:8080/v1")
        assert url.startswith("http://")

    def test_http_127_0_0_1_allowed(self) -> None:
        url = validate_endpoint("http://127.0.0.1:8080/v1")
        assert url.startswith("http://")

    def test_http_ipv6_localhost_allowed(self) -> None:
        url = validate_endpoint("http://[::1]:8080/v1")
        assert url.startswith("http://")

    def test_http_non_localhost_allowed_with_flag(self) -> None:
        url = validate_endpoint("http://api.example.com/v1", allow_insecure=True)
        assert url.startswith("http://")

    def test_missing_scheme_rejected(self) -> None:
        with pytest.raises(HttpError, match="Missing scheme"):
            validate_endpoint("api.example.com/v1")

    def test_missing_host_rejected(self) -> None:
        with pytest.raises(HttpError, match="Missing host"):
            validate_endpoint("https:///v1")

    def test_adds_v1_suffix_when_missing(self) -> None:
        url = validate_endpoint("https://api.example.com")
        assert url.endswith("/v1")

    def test_preserves_v1_when_present(self) -> None:
        url = validate_endpoint("https://api.example.com/v1")
        assert url.endswith("/v1")
        assert url.count("/v1") == 1  # No double /v1/v1

    def test_preserves_query_string(self) -> None:
        url = validate_endpoint("https://api.example.com?debug=true")
        assert "?debug=true" in url
        assert "/v1?" in url


# ---------------------------------------------------------------------------
# LLM response schema validation (integration with mocked HTTP)
# ---------------------------------------------------------------------------


class TestLlmSchemaValidation:
    """Test response schema validation in the LLM client."""

    @pytest.fixture
    def config(self) -> Config:
        return Config(
            llm_base_url="https://api.openai.com/v1",
            llm_api_key="sk-test-key",
            llm_model="gpt-4o-mini",
        )

    @pytest.fixture
    def contract(self) -> PromptContract:
        return PromptContract(
            system_message="System prompt.",
            user_message="User prompt.",
        )

    def test_valid_response_accepted(self, config: Config, contract: PromptContract) -> None:
        with respx.mock:
            respx.post("https://api.openai.com/v1/chat/completions").respond(
                status_code=200,
                json={"choices": [{"message": {"content": "Generated text."}}]},
            )
            client = OpenAiLlmClient(config)
            result = client.rewrite(contract)
            assert result == "Generated text."

    def test_null_content_rejected(self, config: Config, contract: PromptContract) -> None:
        with respx.mock:
            respx.post("https://api.openai.com/v1/chat/completions").respond(
                status_code=200,
                json={"choices": [{"message": {"content": None}}]},
            )
            client = OpenAiLlmClient(config)
            with pytest.raises(LlmError, match="Unexpected LLM response structure"):
                client.rewrite(contract)

    def test_missing_message_rejected(self, config: Config, contract: PromptContract) -> None:
        with respx.mock:
            respx.post("https://api.openai.com/v1/chat/completions").respond(
                status_code=200,
                json={"choices": [{}]},
            )
            client = OpenAiLlmClient(config)
            with pytest.raises(LlmError, match="Unexpected LLM response structure"):
                client.rewrite(contract)

    def test_choices_not_list_rejected(self, config: Config, contract: PromptContract) -> None:
        with respx.mock:
            respx.post("https://api.openai.com/v1/chat/completions").respond(
                status_code=200,
                json={"choices": "not-a-list"},
            )
            client = OpenAiLlmClient(config)
            with pytest.raises(LlmError, match="Unexpected LLM response structure"):
                client.rewrite(contract)

    def test_empty_object_rejected(self, config: Config, contract: PromptContract) -> None:
        with respx.mock:
            respx.post("https://api.openai.com/v1/chat/completions").respond(
                status_code=200,
                json={},
            )
            client = OpenAiLlmClient(config)
            with pytest.raises(LlmError, match="Unexpected LLM response structure"):
                client.rewrite(contract)

    def test_error_response_does_not_log_body(
        self, config: Config, contract: PromptContract
    ) -> None:
        """4xx error messages must not include response body content."""
        with respx.mock:
            respx.post("https://api.openai.com/v1/chat/completions").respond(
                status_code=401,
                json={"error": {"message": "Invalid API key", "type": "auth_error"}},
            )
            client = OpenAiLlmClient(config)
            with pytest.raises(LlmError) as exc_info:
                client.rewrite(contract)

            error_msg = str(exc_info.value)
            # Error should tell us the status but NOT include the body
            assert "401" in error_msg
            assert "Invalid API key" not in error_msg
            assert "auth_error" not in error_msg


# ---------------------------------------------------------------------------
# HTTPS enforcement on client construction
# ---------------------------------------------------------------------------


class TestClientConstructionSecurity:
    def test_https_client_created(self) -> None:
        client = build_client("https://api.example.com/v1", "sk-test-key", timeout=5.0)
        assert str(client.base_url).rstrip("/") == "https://api.example.com/v1"
        assert "Authorization" in client.headers
        client.close()

    def test_client_without_api_key(self) -> None:
        client = build_client("https://api.example.com/v1", None)
        assert "Authorization" not in client.headers
        client.close()

    def test_insecure_endpoint_rejected_in_llm_client(self) -> None:
        config = Config(
            llm_base_url="http://api.openai.com/v1",
            allow_insecure=False,
        )
        with pytest.raises(LlmError, match="HTTP is not allowed"):
            OpenAiLlmClient(config)

    def test_llm_client_respects_allow_insecure_flag(self) -> None:
        config = Config(
            llm_base_url="http://192.168.1.1:8080/v1",
            allow_insecure=True,
        )
        with respx.mock:
            respx.post("http://192.168.1.1:8080/v1/chat/completions").respond(
                status_code=200,
                json={"choices": [{"message": {"content": "OK"}}]},
            )
            client = OpenAiLlmClient(config)
            result = client.rewrite(
                PromptContract(
                    system_message="sys",
                    user_message="usr",
                )
            )
            assert result == "OK"
