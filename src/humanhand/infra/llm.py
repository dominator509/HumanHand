"""OpenAI-compatible LLM client implementing the ``LlmClient`` protocol.

Uses ``httpx`` directly (not the openai SDK) for fine-grained control over
retries, timeouts, error handling, and privacy.
"""

from __future__ import annotations

import json

import httpx

from humanhand.application.ports import LlmClient
from humanhand.domain.types import PromptContract
from humanhand.infra.config import Config
from humanhand.infra.http import HttpError, build_client, validate_endpoint


class LlmError(Exception):
    """Raised when an LLM operation fails."""


class OpenAiLlmClient(LlmClient):
    """OpenAI-compatible LLM client with retry, timeout, and privacy controls.

    Wraps an ``httpx.Client`` pointed at an OpenAI-compatible ``/chat/completions``
    endpoint.  Retries on network errors and server (5xx) errors up to 3 times.
    Client (4xx) errors are not retried.  No request/response bodies are logged;
    error messages are scrubbed of sensitive data.
    """

    _MODEL_DEFAULT = "gpt-4o-mini"
    _BASE_URL_DEFAULT = "https://api.openai.com"
    _MAX_RETRIES = 3

    def __init__(self, config: Config) -> None:
        """Initialize the client from application configuration.

        Args:
            config: Application configuration containing LLM endpoint, key,
                model, and timeout settings.

        Raises:
            LlmError: If endpoint validation or client construction fails.
        """
        self._config = config
        base_url = config.llm_base_url or self._BASE_URL_DEFAULT

        try:
            validated = validate_endpoint(base_url, config.allow_insecure)
        except HttpError as exc:
            raise LlmError(str(exc)) from exc

        self._base_url = validated
        self._model = config.llm_model or self._MODEL_DEFAULT

        try:
            self._client = build_client(
                validated,
                config.llm_api_key,
                config.timeout_seconds,
            )
        except HttpError as exc:
            raise LlmError(str(exc)) from exc

    def rewrite(self, prompt_contract: PromptContract) -> str:
        """Send a rewrite/repair prompt and return the generated text.

        Args:
            prompt_contract: The prompt to send (system + user messages).

        Returns:
            Generated text from the LLM.

        Raises:
            LlmError: On network, auth, schema, or persistent server errors.
        """
        payload: dict[str, object] = {
            "model": self._model,
            "messages": [
                {"role": "system", "content": prompt_contract.system_message},
                {"role": "user", "content": prompt_contract.user_message},
            ],
        }

        for attempt in range(self._MAX_RETRIES):
            try:
                response = self._client.post("/chat/completions", json=payload)
            except httpx.TimeoutException:
                if attempt < self._MAX_RETRIES - 1:
                    continue
                raise LlmError("LLM request timed out after 3 retries") from None
            except httpx.NetworkError:
                if attempt < self._MAX_RETRIES - 1:
                    continue
                raise LlmError("LLM network error after 3 retries") from None
            except httpx.HTTPError as exc:
                raise LlmError(f"LLM HTTP error: {type(exc).__name__}") from exc

            # Retry on server errors, no retry on client errors
            if response.status_code >= 500:
                if attempt < self._MAX_RETRIES - 1:
                    continue
                raise LlmError(
                    f"LLM server error after {self._MAX_RETRIES} retries: "
                    f"status={response.status_code}"
                )

            if response.status_code >= 400:
                raise LlmError(f"LLM request failed: status={response.status_code}")

            # Parse the response body
            try:
                data = response.json()
            except json.JSONDecodeError as exc:
                raise LlmError(f"Invalid JSON response from LLM: {exc}") from exc

            # Validate the expected response shape
            try:
                content: str = data["choices"][0]["message"]["content"]
            except (KeyError, IndexError, TypeError) as exc:
                raise LlmError(f"Unexpected LLM response structure: {exc}") from exc

            if content is None or not isinstance(content, str):
                raise LlmError("Unexpected LLM response structure: content is missing or invalid")

            return content

        # Guard -- the loop always returns or raises.
        raise LlmError("LLM request failed unexpectedly")
