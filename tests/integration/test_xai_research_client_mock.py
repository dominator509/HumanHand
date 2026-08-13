"""Integration tests for the Research Beacon xAI research client.

All HTTP is mocked with respx; no real network request is made and no real
API key is used. The beacon DOMAIN modules (``humanhand.domain.beacon_*``)
are owned by a parallel agent and are absent at EP-018 validation time; this
file defines a minimal local stand-in (``_PolicyStub``) carrying the
attribute names the adapter reads, and reports that honestly.
"""

from __future__ import annotations

import json
from pathlib import Path
from typing import Any

import httpx
import pytest
import respx

from humanhand.infra.beacon.model_selector import select_model
from humanhand.infra.beacon.xai_research_client import (
    XaiResearchClient,
    XaiResearchError,
    _sanitize_context,
)

pytestmark = pytest.mark.importers

FIXTURES = Path(__file__).resolve().parents[1] / "fixtures" / "beacon"
FIXTURE_PATH = FIXTURES / "mock-xai-response.json"

BASE_URL = "https://api.x.ai/v1"
CHAT_URL = "https://api.x.ai/v1/chat/completions"


class _PolicyStub:
    """Minimal local stand-in for the beacon privacy policy.

    The real policy object lives in ``humanhand.domain.beacon_policy``
    (parallel agent, absent at validation time). The adapter reads only the
    ``network_allowed`` attribute; this stub carries that exact name.
    """

    def __init__(self, *, network_allowed: bool) -> None:
        self.network_allowed = network_allowed


def _load_fixture() -> Any:
    """Load the synthetic research response fixture as raw JSON."""
    return json.loads(FIXTURE_PATH.read_text(encoding="utf-8"))


def _client(
    *,
    model: str | None = "grok-4.6",
    test_mode: bool = True,
    policy: _PolicyStub | None = None,
    zdr_compliant_models: frozenset[str] = frozenset(),
) -> XaiResearchClient:
    return XaiResearchClient(
        base_url=BASE_URL,
        api_key="sk-test-beacon-key",
        model=model,
        privacy_policy=policy,
        test_mode=test_mode,
        zdr_compliant_models=zdr_compliant_models,
    )


# ----------------------------------------------------------------------
# Success path: documented response shape and request payload
# ----------------------------------------------------------------------


def test_documented_response_shape_and_request_payload() -> None:
    """A well-formed response returns the validated structured result, and the
    outgoing request carries exactly the sanitized keys (no private text)."""
    fixture = _load_fixture()
    with respx.mock:
        route = respx.post(CHAT_URL)
        route.respond(status_code=200, json=fixture)

        client = _client(policy=_PolicyStub(network_allowed=True))
        result = client.research(
            "security_advisory",
            "pypdf release status",
            "public_release_notes",
        )

    assert route.call_count == 1
    expected = json.loads(fixture["choices"][0]["message"]["content"])
    assert result["summary"] == expected["summary"]
    assert result["findings"] == expected["findings"]
    assert result["sources"] == expected["sources"]
    assert result["confidence"] == expected["confidence"]

    sent = route.calls[0].request
    assert sent.url == CHAT_URL
    assert sent.headers["authorization"] == "Bearer sk-test-beacon-key"
    body = json.loads(sent.content)
    assert body["model"] == "grok-4.6"
    assert body["response_format"] == {"type": "json_object"}
    messages = body["messages"]
    assert len(messages) == 2
    assert messages[0]["role"] == "system"
    assert messages[1]["role"] == "user"
    user_payload = json.loads(messages[1]["content"])
    # The payload carries exactly the sanitized keys: no "document" or "text"
    # key (the privacy guarantee) and nothing else.
    assert set(user_payload) == {"trigger_id", "topic", "context_kind"}
    assert user_payload["trigger_id"] == "security_advisory"
    assert user_payload["topic"] == "pypdf release status"
    assert user_payload["context_kind"] == "public_release_notes"
    assert "document" not in user_payload
    assert "text" not in user_payload


def test_invalid_response_schema_rejected() -> None:
    """A response with the wrong key set is rejected, never reparsed."""
    with respx.mock:
        route = respx.post(CHAT_URL)
        route.respond(
            status_code=200,
            json={
                "choices": [
                    {"message": {"content": '{"summary": "only a summary"}'}},
                ],
            },
        )

        client = _client(policy=_PolicyStub(network_allowed=True))
        with pytest.raises(XaiResearchError, match="Invalid research response schema"):
            client.research("security_advisory", "topic", "public_release_notes")

        assert route.call_count == 1


# ----------------------------------------------------------------------
# Live-call gate and network policy
# ----------------------------------------------------------------------


def test_live_calls_require_gate(monkeypatch: pytest.MonkeyPatch) -> None:
    """Non-test-mode without the live gate refuses before any network use."""
    monkeypatch.delenv("HUMANHAND_RUN_LIVE_BEACON", raising=False)
    client = _client(test_mode=False, policy=_PolicyStub(network_allowed=True))
    with respx.mock:
        route = respx.post(CHAT_URL)
        route.respond(status_code=200, json=_load_fixture())

        with pytest.raises(XaiResearchError, match="live_calls_not_enabled"):
            client.research("security_advisory", "topic", "public_release_notes")

        assert route.call_count == 0


def test_gate_opens_with_environment(monkeypatch: pytest.MonkeyPatch) -> None:
    """HUMANHAND_RUN_LIVE_BEACON=1 opens the live gate; the request proceeds."""
    monkeypatch.setenv("HUMANHAND_RUN_LIVE_BEACON", "1")
    client = _client(test_mode=False, policy=_PolicyStub(network_allowed=True))
    with respx.mock:
        route = respx.post(CHAT_URL)
        route.respond(status_code=200, json=_load_fixture())

        result = client.research(
            "security_advisory",
            "pypdf release status",
            "public_release_notes",
        )

        assert result["confidence"] == 0.82
        assert route.call_count == 1


def test_network_forbidden_without_policy() -> None:
    """No privacy policy at all means network permission is denied."""
    client = _client()
    with respx.mock:
        route = respx.post(CHAT_URL)
        route.respond(status_code=200, json=_load_fixture())

        with pytest.raises(XaiResearchError, match="network_forbidden"):
            client.research("security_advisory", "topic", "public_release_notes")

        assert route.call_count == 0


def test_network_forbidden_with_denying_policy() -> None:
    """A policy that does not grant network access is a hard denial."""
    client = _client(policy=_PolicyStub(network_allowed=False))
    with respx.mock:
        route = respx.post(CHAT_URL)
        route.respond(status_code=200, json=_load_fixture())

        with pytest.raises(XaiResearchError, match="network_forbidden"):
            client.research("security_advisory", "topic", "public_release_notes")

        assert route.call_count == 0


# ----------------------------------------------------------------------
# Model pinning and ZDR
# ----------------------------------------------------------------------


def test_model_not_selected_refuses() -> None:
    """No configured model and no availability data fails closed."""
    client = _client(model=None, policy=_PolicyStub(network_allowed=True))
    with respx.mock:
        route = respx.post(CHAT_URL)
        route.respond(status_code=200, json=_load_fixture())

        with pytest.raises(XaiResearchError, match="model_not_selected"):
            client.research("security_advisory", "topic", "public_release_notes")

        assert route.call_count == 0


def test_zdr_required_refuses_non_compliant_model(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """With ZDR required, a non-compliant model name is refused."""
    monkeypatch.setenv("HUMANHAND_BEACON_ZDR_REQUIRED", "1")
    client = _client(model="grok-4.6", policy=_PolicyStub(network_allowed=True))
    with respx.mock:
        route = respx.post(CHAT_URL)
        route.respond(status_code=200, json=_load_fixture())

        with pytest.raises(XaiResearchError, match="zdr_required"):
            client.research("security_advisory", "topic", "public_release_notes")

        assert route.call_count == 0


def test_zdr_compliant_model_accepted(monkeypatch: pytest.MonkeyPatch) -> None:
    """With ZDR required, a zdr-named model proceeds normally."""
    monkeypatch.setenv("HUMANHAND_BEACON_ZDR_REQUIRED", "1")
    client = _client(
        model="verified-test-model",
        policy=_PolicyStub(network_allowed=True),
        zdr_compliant_models=frozenset({"verified-test-model"}),
    )
    with respx.mock:
        route = respx.post(CHAT_URL)
        route.respond(status_code=200, json=_load_fixture())

        result = client.research(
            "security_advisory",
            "pypdf release status",
            "public_release_notes",
        )

        assert result["confidence"] == 0.82
        assert route.call_count == 1


# ----------------------------------------------------------------------
# Context sanitization
# ----------------------------------------------------------------------


def test_sanitize_context_blocks_private_documents() -> None:
    """Contexts carrying document or text keys are refused."""
    with pytest.raises(XaiResearchError, match="private_document_blocked:document"):
        _sanitize_context({"document": "full private document"})
    with pytest.raises(XaiResearchError, match="private_document_blocked:text"):
        _sanitize_context({"text": "private text"})
    with pytest.raises(XaiResearchError, match="unsanitized_context"):
        _sanitize_context({"topic": "only topic"})
    with pytest.raises(XaiResearchError, match="unsanitized_context"):
        _sanitize_context({"topic": "t", "context_kind": "public_release_notes", "extra": "x"})
    with pytest.raises(XaiResearchError, match="unsanitized_context"):
        _sanitize_context({"topic": "t", "context_kind": 42})
    assert _sanitize_context({"topic": "t", "context_kind": "public_release_notes"}) == {
        "topic": "t",
        "context_kind": "public_release_notes",
    }


@pytest.mark.parametrize(
    "content",
    (
        '{"summary":"ok","findings":["x"],"sources":["http://example.org"],"confidence":0.5}',
        '{"summary":"ok","findings":[],"sources":["https://example.org"],"confidence":0.5}',
        '{"summary":"ok","findings":["x"],"sources":["https://example.org"],"confidence":1.1}',
    ),
)
def test_untraceable_or_out_of_range_response_is_rejected(content: str) -> None:
    with respx.mock:
        respx.post(CHAT_URL).respond(
            status_code=200,
            json={"choices": [{"message": {"content": content}}]},
        )
        with pytest.raises(XaiResearchError, match="Invalid research response schema"):
            _client(policy=_PolicyStub(network_allowed=True)).research(
                "security_advisory", "topic", "public_release_notes"
            )


# ----------------------------------------------------------------------
# Model selector
# ----------------------------------------------------------------------


def test_select_model_pinning() -> None:
    """Configured model wins; otherwise first preferred available; else None."""
    assert (
        select_model(
            configured_model="grok-x",
            available=("grok-4.6",),
        )
        == "grok-x"
    )
    assert (
        select_model(
            configured_model=None,
            available=("grok-3-mini", "grok-4.6"),
        )
        == "grok-4.6"
    )
    assert select_model(configured_model=None, available=("grok-3",)) == "grok-3"
    assert select_model(configured_model=None, available=()) is None
    assert (
        select_model(
            configured_model=None,
            available=("some-other-model",),
        )
        is None
    )


# ----------------------------------------------------------------------
# HTTP endpoint enforcement
# ----------------------------------------------------------------------


def test_http_base_url_rejected(monkeypatch: pytest.MonkeyPatch) -> None:
    """Non-localhost HTTP endpoint without insecure opt-in is rejected."""
    monkeypatch.delenv("HUMANHAND_ALLOW_INSECURE", raising=False)
    with pytest.raises(XaiResearchError, match="HTTP is not allowed"):
        XaiResearchClient(base_url="http://api.x.ai/v1", api_key="sk-test-beacon-key")


# ----------------------------------------------------------------------
# Retry behaviour
# ----------------------------------------------------------------------


def test_retry_after_server_error() -> None:
    """A 500 followed by success retries once and returns the result."""
    fixture = _load_fixture()
    with respx.mock:
        route = respx.post(CHAT_URL)
        route.side_effect = [
            httpx.Response(500),
            httpx.Response(200, json=fixture),
        ]

        client = _client(policy=_PolicyStub(network_allowed=True))
        result = client.research(
            "security_advisory",
            "pypdf release status",
            "public_release_notes",
        )

        assert result["confidence"] == 0.82
        assert route.call_count == 2


def test_retries_exhausted_on_server_error() -> None:
    """Persistent 5xx raises after 3 attempts."""
    with respx.mock:
        route = respx.post(CHAT_URL)
        route.respond(status_code=500)

        client = _client(policy=_PolicyStub(network_allowed=True))
        with pytest.raises(XaiResearchError, match="server error after 3 retries"):
            client.research("security_advisory", "topic", "public_release_notes")

        assert route.call_count == 3


def test_no_retry_on_client_error() -> None:
    """4xx responses are not retried."""
    with respx.mock:
        route = respx.post(CHAT_URL)
        route.respond(status_code=401, json={"error": "unauthorized"})

        client = _client(policy=_PolicyStub(network_allowed=True))
        with pytest.raises(XaiResearchError, match="status=401"):
            client.research("security_advisory", "topic", "public_release_notes")

        assert route.call_count == 1


def test_retry_on_timeout() -> None:
    """Network timeouts are retried up to 3 times."""
    with respx.mock:
        route = respx.post(CHAT_URL)
        route.side_effect = httpx.TimeoutException("Connection timed out")

        client = _client(policy=_PolicyStub(network_allowed=True))
        with pytest.raises(XaiResearchError, match="timed out after 3 retries"):
            client.research("security_advisory", "topic", "public_release_notes")

        assert route.call_count == 3
