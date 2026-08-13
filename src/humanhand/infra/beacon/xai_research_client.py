"""OpenAI-compatible research adapter for the Research Beacon (blueprint 13.3).

Uses ``httpx`` directly against the documented OpenAI-compatible
``/chat/completions`` shape (same pattern as ``humanhand.infra.llm``) with
retries on network errors and server errors, HTTPS enforcement via
``humanhand.infra.http.validate_endpoint``, and strict response-schema
validation.

Guarantees, enforced in ``research`` in this order:

- Live calls are gated: ``research`` refuses with ``live_calls_not_enabled``
  unless the client is in ``test_mode`` or ``HUMANHAND_RUN_LIVE_BEACON=1``.
- Network permission is required: a privacy policy whose ``network_allowed``
  is not exactly True (or no policy at all) refuses with ``network_forbidden``.
- The model is pinned per run: ``select_model`` result None refuses with
  ``model_not_selected`` (no silent fallback).
- ZDR: with ``HUMANHAND_BEACON_ZDR_REQUIRED=1`` the selected model must be in
  an explicit operator-supplied set of models verified for the endpoint.
- Private documents are never transmitted: the prompt builder only accepts a
  sanitized context dict with the keys ``topic``/``context_kind`` and refuses
  any context carrying a ``document`` or ``text`` key
  (``private_document_blocked`` / ``unsanitized_context``).
"""

from __future__ import annotations

import json
import math
import os
from collections.abc import Mapping
from typing import Protocol, cast

import httpx

from humanhand.infra.beacon.model_selector import select_model
from humanhand.infra.config import TRUE_VALUES
from humanhand.infra.http import HttpError, build_client, validate_endpoint


class XaiResearchError(Exception):
    """Raised when a beacon research operation fails."""


def _env_flag(name: str) -> bool:
    """Read a boolean-ish environment variable using the repo's TRUE_VALUES."""
    return os.getenv(name, "").strip().lower() in TRUE_VALUES


def _sanitize_context(context: Mapping[str, object]) -> dict[str, object]:
    """Prompt-builder guard: only ``topic``/``context_kind`` are accepted.

    Refuses (``private_document_blocked``) any context that carries a
    ``document`` or ``text`` key and refuses (``unsanitized_context``)
    contexts that are missing keys, carry extra keys, or hold non-string
    values.
    """
    for key in context:
        if key in {"document", "text"}:
            raise XaiResearchError(f"private_document_blocked:{key}")
    if set(context) != {"topic", "context_kind"}:
        raise XaiResearchError("unsanitized_context")
    if not all(isinstance(value, str) for value in context.values()):
        raise XaiResearchError("unsanitized_context")
    return dict(context)


_SYSTEM_PROMPT = (
    "You are the Human Hand research beacon. Produce verifiable research "
    "notes as a single JSON object with exactly these keys: summary "
    "(string), findings (list of strings), sources (list of strings), "
    "confidence (number). Never request or accept private user documents."
)


class _ResearchPolicy(Protocol):
    """Structural contract for the beacon privacy policy.

    The real policy object is owned by ``humanhand.domain.beacon_policy``
    (parallel agent); the adapter reads only ``network_allowed``.
    """

    network_allowed: bool


class XaiResearchClient:
    """OpenAI-compatible research adapter for the Research Beacon."""

    _MAX_RETRIES = 3
    _RESPONSE_KEYS = frozenset({"summary", "findings", "sources", "confidence"})

    def __init__(
        self,
        *,
        base_url: str,
        api_key: str,
        model: str | None = None,
        timeout_seconds: float = 30.0,
        privacy_policy: object | None = None,
        test_mode: bool = False,
        zdr_compliant_models: frozenset[str] = frozenset(),
    ) -> None:
        """Initialize the adapter.

        ``test_mode`` is a documented test seam: tests pass True and mock the
        endpoint with respx; production callers keep the default False and
        must set ``HUMANHAND_RUN_LIVE_BEACON=1`` to run live calls.

        Raises:
            XaiResearchError: If the endpoint fails HTTPS validation or the
                HTTP client cannot be built.
        """
        allow_insecure = _env_flag("HUMANHAND_ALLOW_INSECURE")
        try:
            validated = validate_endpoint(base_url, allow_insecure)
        except HttpError as exc:
            raise XaiResearchError(str(exc)) from exc
        try:
            self._client = build_client(validated, api_key, timeout_seconds)
        except HttpError as exc:
            raise XaiResearchError(str(exc)) from exc
        self._model = model
        self._privacy_policy = privacy_policy
        self._test_mode = test_mode
        self._zdr_compliant_models = zdr_compliant_models

    def _network_permitted(self) -> bool:
        """True only when an explicit policy grants network access."""
        policy = self._privacy_policy
        if policy is None:
            return False
        if not hasattr(policy, "network_allowed"):
            return False
        return cast(_ResearchPolicy, policy).network_allowed is True

    def research(
        self,
        trigger_id: str,
        topic: str,
        context_kind: str,
    ) -> dict[str, object]:
        """Run one research request and return the validated structured result.

        Raises:
            XaiResearchError: On gate refusal (``live_calls_not_enabled``,
                ``network_forbidden``, ``model_not_selected``,
                ``zdr_required``), transport failure, or invalid response
                schema.
        """
        if not self._test_mode and not _env_flag("HUMANHAND_RUN_LIVE_BEACON"):
            raise XaiResearchError("live_calls_not_enabled")
        if not self._network_permitted():
            raise XaiResearchError("network_forbidden")

        model = select_model(configured_model=self._model)
        if model is None:
            raise XaiResearchError("model_not_selected")
        if _env_flag("HUMANHAND_BEACON_ZDR_REQUIRED") and model not in self._zdr_compliant_models:
            raise XaiResearchError("zdr_required")

        context = _sanitize_context({"topic": topic, "context_kind": context_kind})
        user_message = json.dumps(
            {"trigger_id": trigger_id, **context},
            sort_keys=True,
        )
        payload: dict[str, object] = {
            "model": model,
            "messages": [
                {"role": "system", "content": _SYSTEM_PROMPT},
                {"role": "user", "content": user_message},
            ],
            "response_format": {"type": "json_object"},
        }

        for attempt in range(self._MAX_RETRIES):
            try:
                response = self._client.post("/chat/completions", json=payload)
            except httpx.TimeoutException:
                if attempt < self._MAX_RETRIES - 1:
                    continue
                raise XaiResearchError("research request timed out after 3 retries") from None
            except httpx.NetworkError:
                if attempt < self._MAX_RETRIES - 1:
                    continue
                raise XaiResearchError("research network error after 3 retries") from None
            except httpx.HTTPError as exc:
                raise XaiResearchError(f"research HTTP error: {type(exc).__name__}") from exc

            if response.status_code >= 500:
                if attempt < self._MAX_RETRIES - 1:
                    continue
                raise XaiResearchError(
                    f"research server error after {self._MAX_RETRIES} retries: "
                    f"status={response.status_code}"
                )
            if response.status_code >= 400:
                raise XaiResearchError(f"research request failed: status={response.status_code}")

            try:
                data = response.json()
            except json.JSONDecodeError as exc:
                raise XaiResearchError(
                    f"Invalid JSON response from research endpoint: {exc}"
                ) from exc

            try:
                content = data["choices"][0]["message"]["content"]
            except (KeyError, IndexError, TypeError) as exc:
                raise XaiResearchError(f"Unexpected research response structure: {exc}") from exc
            if not isinstance(content, str):
                raise XaiResearchError(
                    "Unexpected research response structure: content is not a string"
                )
            return self._validate_research_payload(content)

        raise XaiResearchError("research request failed unexpectedly")

    def _validate_research_payload(self, content: str) -> dict[str, object]:
        """Strictly validate the model's JSON against the documented shape.

        The payload must be a JSON object with exactly the keys ``summary``
        (str), ``findings`` (list of str), ``sources`` (list of str), and
        ``confidence`` (finite number, not bool). Anything else raises
        ``XaiResearchError``; invalid payloads are never reparsed best-effort.
        """
        try:
            parsed = json.loads(content)
        except json.JSONDecodeError as exc:
            raise XaiResearchError(f"Invalid JSON in research response content: {exc}") from exc
        if not isinstance(parsed, dict):
            raise XaiResearchError("Invalid research response schema: expected a JSON object")
        if set(parsed) != self._RESPONSE_KEYS:
            raise XaiResearchError("Invalid research response schema: unexpected or missing keys")

        summary = parsed["summary"]
        if not isinstance(summary, str):
            raise XaiResearchError("Invalid research response schema: summary must be a string")
        if not summary.strip():
            raise XaiResearchError("Invalid research response schema: summary must not be empty")

        findings = parsed["findings"]
        if not isinstance(findings, list) or not all(isinstance(item, str) for item in findings):
            raise XaiResearchError(
                "Invalid research response schema: findings must be a list of strings"
            )
        if not findings or any(not item.strip() for item in findings):
            raise XaiResearchError("Invalid research response schema: findings must not be empty")

        sources = parsed["sources"]
        if not isinstance(sources, list) or not all(isinstance(item, str) for item in sources):
            raise XaiResearchError(
                "Invalid research response schema: sources must be a list of strings"
            )
        if not sources or any(not source.startswith("https://") for source in sources):
            raise XaiResearchError(
                "Invalid research response schema: sources must be public HTTPS URLs"
            )

        confidence = parsed["confidence"]
        if (
            isinstance(confidence, bool)
            or not isinstance(confidence, (int, float))
            or not math.isfinite(float(confidence))
            or not 0.0 <= float(confidence) <= 1.0
        ):
            raise XaiResearchError(
                "Invalid research response schema: confidence must be a finite number"
            )

        return {
            "summary": summary,
            "findings": findings,
            "sources": sources,
            "confidence": confidence,
        }
