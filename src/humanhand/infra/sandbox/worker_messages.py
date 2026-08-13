"""Wire protocol messages for the parser worker channel."""

from __future__ import annotations

from typing import Literal

from pydantic import BaseModel, ConfigDict

PROTOCOL_VERSION: Literal["parser-worker-1"] = "parser-worker-1"


class ParseRequest(BaseModel):
    """One parser task handed to a worker process over stdin."""

    model_config = ConfigDict(extra="forbid")

    protocol: Literal["parser-worker-1"]
    task_id: str
    parser_name: str
    policy: dict[str, object]
    data_b64: str


class ParseResult(BaseModel):
    """One structured parser outcome emitted by a worker process."""

    model_config = ConfigDict(extra="forbid")

    protocol: Literal["parser-worker-1"]
    task_id: str
    status: str
    document: dict[str, object] | None
    findings: list[dict[str, object]]
    unicode: dict[str, object] | None
    active_content: list[dict[str, object]]
    metadata: dict[str, object]
    coverage: dict[str, object]
    measurements: dict[str, object] | None


def make_finding_payload(
    code: str,
    severity: str,
    category: str,
    description: str,
    evidence: str = "",
) -> dict[str, object]:
    """Render one finding in the exact shape document_serialization emits."""
    return {
        "category": category,
        "code": code,
        "description": description,
        "evidence": evidence,
        "location": None,
        "severity": severity,
    }
