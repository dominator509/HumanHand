"""Integration tests for the LLM client component.

Uses ``respx`` to mock HTTP calls — no real network requests are made.
"""

from __future__ import annotations

import httpx
import pytest
import respx

from humanhand.domain.types import PromptContract
from humanhand.infra.config import Config
from humanhand.infra.llm import LlmError, OpenAiLlmClient


class TestOpenAiLlmClient:
    """Integration tests for :class:`OpenAiLlmClient`.

    Every test is isolated behind a ``respx.mock`` context manager so no real
    HTTP traffic can escape.
    """

    # ------------------------------------------------------------------
    # Fixtures
    # ------------------------------------------------------------------

    @pytest.fixture
    def config(self) -> Config:
        """Default configuration pointing at a real-looking but mocked endpoint."""
        return Config(
            llm_base_url="https://api.openai.com/v1",
            llm_api_key="sk-test-key-12345",
            llm_model="gpt-4o-mini",
        )

    @pytest.fixture
    def contract(self) -> PromptContract:
        """Generic rewrite prompt for tests."""
        return PromptContract(
            system_message="You are a helpful assistant.",
            user_message="Rewrite this text in a human style.",
        )

    # ------------------------------------------------------------------
    # Success path
    # ------------------------------------------------------------------

    def test_successful_completion(self, config: Config, contract: PromptContract) -> None:
        """A well-formed request returns the expected generated text."""
        with respx.mock:
            route = respx.post("https://api.openai.com/v1/chat/completions")
            route.respond(
                status_code=200,
                json={
                    "choices": [
                        {"message": {"content": "This is the rewritten text."}},
                    ],
                },
            )

            client = OpenAiLlmClient(config)
            result = client.rewrite(contract)

            assert result == "This is the rewritten text."
            assert route.call_count == 1

    # ------------------------------------------------------------------
    # Retry behaviour
    # ------------------------------------------------------------------

    def test_retry_on_5xx(self, config: Config, contract: PromptContract) -> None:
        """Server errors (5xx) are retried up to 3 times before giving up."""
        with respx.mock:
            route = respx.post("https://api.openai.com/v1/chat/completions")
            route.respond(status_code=500)

            client = OpenAiLlmClient(config)
            with pytest.raises(LlmError, match="server error after 3 retries"):
                client.rewrite(contract)

            assert route.call_count == 3

    def test_no_retry_on_4xx(self, config: Config, contract: PromptContract) -> None:
        """Client errors (4xx) are *not* retried — fail immediately."""
        with respx.mock:
            route = respx.post("https://api.openai.com/v1/chat/completions")
            route.respond(status_code=401, json={"error": "unauthorized"})

            client = OpenAiLlmClient(config)
            with pytest.raises(LlmError, match="status=401"):
                client.rewrite(contract)

            assert route.call_count == 1

    def test_retry_on_timeout(self, config: Config, contract: PromptContract) -> None:
        """Network timeouts are retried up to 3 times."""
        with respx.mock:
            route = respx.post("https://api.openai.com/v1/chat/completions")
            route.side_effect = httpx.TimeoutException("Connection timed out")

            client = OpenAiLlmClient(config)
            with pytest.raises(LlmError, match="timed out after 3 retries"):
                client.rewrite(contract)

            assert route.call_count == 3

    def test_retry_on_network_error(self, config: Config, contract: PromptContract) -> None:
        """Transient network errors are retried up to 3 times."""
        with respx.mock:
            route = respx.post("https://api.openai.com/v1/chat/completions")
            route.side_effect = httpx.NetworkError("DNS resolution failed")

            client = OpenAiLlmClient(config)
            with pytest.raises(LlmError, match="network error after 3 retries"):
                client.rewrite(contract)

            assert route.call_count == 3

    # ------------------------------------------------------------------
    # Response validation
    # ------------------------------------------------------------------

    def test_invalid_json_response(self, config: Config, contract: PromptContract) -> None:
        """Non-JSON response raises ``LlmError``."""
        with respx.mock:
            route = respx.post("https://api.openai.com/v1/chat/completions")
            route.respond(status_code=200, content=b"<html>not json</html>")

            client = OpenAiLlmClient(config)
            with pytest.raises(LlmError, match="Invalid JSON"):
                client.rewrite(contract)

            assert route.call_count == 1

    def test_missing_choices_in_response(self, config: Config, contract: PromptContract) -> None:
        """Response with empty choices list raises ``LlmError``."""
        with respx.mock:
            route = respx.post("https://api.openai.com/v1/chat/completions")
            route.respond(status_code=200, json={"choices": []})

            client = OpenAiLlmClient(config)
            with pytest.raises(LlmError, match="Unexpected LLM response structure"):
                client.rewrite(contract)

            assert route.call_count == 1

    def test_missing_content_in_choice(self, config: Config, contract: PromptContract) -> None:
        """Response without ``message.content`` raises ``LlmError``."""
        with respx.mock:
            route = respx.post("https://api.openai.com/v1/chat/completions")
            route.respond(
                status_code=200,
                json={"choices": [{"message": {}}]},
            )

            client = OpenAiLlmClient(config)
            with pytest.raises(LlmError, match="Unexpected LLM response structure"):
                client.rewrite(contract)

            assert route.call_count == 1

    # ------------------------------------------------------------------
    # HTTP endpoint enforcement
    # ------------------------------------------------------------------

    def test_http_endpoint_rejected(self) -> None:
        """Non-localhost HTTP endpoint without ``allow_insecure`` is rejected."""
        config = Config(llm_base_url="http://api.openai.com/v1", llm_model="gpt-4.1-mini")
        with pytest.raises(LlmError, match="HTTP is not allowed"):
            OpenAiLlmClient(config)

    def test_http_localhost_requires_allow_insecure(self) -> None:
        """Loopback HTTP still requires explicit insecure opt-in."""
        config = Config(llm_base_url="http://localhost:8080/v1", llm_model="local-model")
        with pytest.raises(LlmError, match="HUMANHAND_ALLOW_INSECURE=1"):
            OpenAiLlmClient(config)

    def test_missing_endpoint_rejected(self) -> None:
        """LLM client requires an explicit endpoint URL."""
        config = Config()
        with pytest.raises(LlmError, match="LLM endpoint URL is not configured"):
            OpenAiLlmClient(config)

    def test_missing_model_rejected(self) -> None:
        """LLM client requires an explicit model name."""
        config = Config(llm_base_url="https://api.openai.com/v1")
        with pytest.raises(LlmError, match="LLM model is not configured"):
            OpenAiLlmClient(config)

    def test_http_localhost_accepted(self, contract: PromptContract) -> None:
        """HTTP localhost is accepted when ``allow_insecure`` is set."""
        config = Config(
            llm_base_url="http://localhost:8080/v1",
            llm_model="local-model",
            allow_insecure=True,
        )
        with respx.mock:
            route = respx.post("http://localhost:8080/v1/chat/completions")
            route.respond(
                status_code=200,
                json={"choices": [{"message": {"content": "OK"}}]},
            )

            client = OpenAiLlmClient(config)
            result = client.rewrite(contract)
            assert result == "OK"
            assert route.call_count == 1

    # ------------------------------------------------------------------
    # Privacy / secret redaction
    # ------------------------------------------------------------------

    def test_api_key_redacted_in_error(self, contract: PromptContract) -> None:
        """Error messages must not contain the full API key."""
        config = Config(
            llm_base_url="https://api.openai.com/v1",
            llm_api_key="sk-very-secret-key",
            llm_model="gpt-4.1-mini",
        )
        with respx.mock:
            route = respx.post("https://api.openai.com/v1/chat/completions")
            route.respond(status_code=401, json={"error": "unauthorized"})

            client = OpenAiLlmClient(config)
            with pytest.raises(LlmError) as exc_info:
                client.rewrite(contract)

            error_msg = str(exc_info.value)
            assert "sk-very-secret-key" not in error_msg
            assert route.call_count == 1
