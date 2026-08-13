"""Deterministic active-content detection for imported text containers."""

from __future__ import annotations

import re
from dataclasses import dataclass
from enum import StrEnum

from humanhand.domain.import_findings import (
    FindingCategory,
    FindingCode,
    FindingSeverity,
    ImportFinding,
)

# Captures the authority fragment; scheme_host_only then strips userinfo
# and port so evidence carries scheme and host only, never credentials.
# The 256-char capture bound keeps '@'-stripping effective even for long
# userinfo segments.
_SCHEME_HOST_RE = re.compile(r"[a-z][a-z0-9+.-]*://[^/\s\"'<>()?#]{0,256}", re.IGNORECASE)


class ActiveContentKind(StrEnum):
    """Kinds of active or externally-referencing content."""

    HTML_SCRIPT = "html_script"
    HTML_EVENT_HANDLER = "html_event_handler"
    JAVASCRIPT_LINK = "javascript_link"
    VBSCRIPT_LINK = "vbscript_link"
    DATA_URI = "data_uri"
    IFRAME = "iframe"
    EMBED_OBJECT = "embed_object"
    FILE_LINK = "file_link"
    REMOTE_RESOURCE = "remote_resource"


@dataclass(frozen=True)
class ActiveContentFinding:
    """One detected active-content occurrence.

    ``evidence`` contains at most a URL scheme and host, never document text.
    """

    kind: ActiveContentKind
    offset: int
    description: str
    evidence: str = ""


_PATTERN_SPECS: tuple[tuple[ActiveContentKind, re.Pattern[str], str], ...] = (
    (
        ActiveContentKind.HTML_SCRIPT,
        re.compile(r"<script\b", re.IGNORECASE),
        "HTML script element",
    ),
    (
        ActiveContentKind.HTML_EVENT_HANDLER,
        re.compile(r"<[^>]{0,4096}\bon[a-z]+\s*=", re.IGNORECASE),
        "HTML event handler attribute",
    ),
    (
        ActiveContentKind.JAVASCRIPT_LINK,
        re.compile(r"javascript:", re.IGNORECASE),
        "javascript: link",
    ),
    (
        ActiveContentKind.VBSCRIPT_LINK,
        re.compile(r"vbscript:", re.IGNORECASE),
        "vbscript: link",
    ),
    (
        ActiveContentKind.DATA_URI,
        re.compile(r"data:[a-z0-9+/._-]*;base64", re.IGNORECASE),
        "base64 data URI",
    ),
    (
        ActiveContentKind.IFRAME,
        re.compile(r"<iframe\b", re.IGNORECASE),
        "HTML iframe element",
    ),
    (
        ActiveContentKind.EMBED_OBJECT,
        re.compile(r"<object\b|<embed\b", re.IGNORECASE),
        "HTML object/embed element",
    ),
    (
        ActiveContentKind.FILE_LINK,
        re.compile(r"file://", re.IGNORECASE),
        "file:// link",
    ),
    (
        ActiveContentKind.REMOTE_RESOURCE,
        re.compile(
            r"(?:!\[[^\]]*\]\(\s*|\[[^\]]*\]\(\s*|"
            r"^\s{0,3}\[[^\]]+\]:\s*<?|<img\b[^>]*?src\s*=\s*[\"']\s*|<)"
            r"(?:https?://|//)",
            re.MULTILINE,
        ),
        "remote resource reference",
    ),
)


def scheme_host_only(fragment: str) -> str:
    """Reduce a URL to scheme://host, never credentials or paths.

    Strips userinfo (``user:pass@``), port, path, query, and fragment. If
    no ``scheme://`` is present the result is ``"remote_resource"``. Shared
    by the text scanner and every container adapter so evidence hygiene has
    exactly one implementation.
    """
    fragment = fragment.lower().strip()
    if "://" not in fragment:
        return "remote_resource"
    scheme, rest = fragment.split("://", 1)
    # Cut at the path/query/fragment boundary first.
    rest = re.split(r"[/?#]", rest, maxsplit=1)[0]
    # Strip userinfo (user:pass@) and port (:8443) — scheme and host only.
    if "@" in rest:
        rest = rest.rsplit("@", 1)[1]
    if ":" in rest:
        rest = rest.split(":", 1)[0]
    if not rest:
        return "remote_resource"
    return f"{scheme}://{rest}"


def _evidence_for(kind: ActiveContentKind, text: str, offset: int) -> str:
    """Extract at most a scheme+host fragment from the matched region."""
    if kind in {
        ActiveContentKind.JAVASCRIPT_LINK,
        ActiveContentKind.VBSCRIPT_LINK,
        ActiveContentKind.FILE_LINK,
    }:
        return str(kind.value)
    if kind is ActiveContentKind.REMOTE_RESOURCE:
        match = _SCHEME_HOST_RE.search(text[offset:])
        if not match:
            return "remote_resource"
        return scheme_host_only(str(match.group(0)))
    if kind is ActiveContentKind.DATA_URI:
        return "data_uri"
    return str(kind.value)


def scan_active_content(text: str) -> tuple[ActiveContentFinding, ...]:
    """Scan text deterministically for active-content markers.

    Returns findings sorted by offset. The scan never executes content and
    never follows or fetches remote resources.
    """
    findings: list[ActiveContentFinding] = []
    for kind, pattern, description in _PATTERN_SPECS:
        for match in pattern.finditer(text):
            findings.append(
                ActiveContentFinding(
                    kind=kind,
                    offset=match.start(),
                    description=description,
                    evidence=_evidence_for(kind, text, match.start()),
                )
            )
    findings.sort(key=lambda finding: finding.offset)
    return tuple(findings)


def active_content_findings(found: tuple[ActiveContentFinding, ...]) -> tuple[ImportFinding, ...]:
    """Map active-content occurrences to fail-closed import findings."""
    code_by_kind = {
        ActiveContentKind.HTML_SCRIPT: FindingCode.ACTIVE_CONTENT_SCRIPT,
        ActiveContentKind.HTML_EVENT_HANDLER: FindingCode.ACTIVE_CONTENT_EVENT_HANDLER,
        ActiveContentKind.JAVASCRIPT_LINK: FindingCode.ACTIVE_CONTENT_JAVASCRIPT_LINK,
        ActiveContentKind.VBSCRIPT_LINK: FindingCode.ACTIVE_CONTENT_VBSCRIPT_LINK,
        ActiveContentKind.DATA_URI: FindingCode.ACTIVE_CONTENT_DATA_URI,
        ActiveContentKind.IFRAME: FindingCode.ACTIVE_CONTENT_IFRAME,
        ActiveContentKind.EMBED_OBJECT: FindingCode.ACTIVE_CONTENT_EMBED_OBJECT,
        ActiveContentKind.FILE_LINK: FindingCode.ACTIVE_CONTENT_FILE_LINK,
        ActiveContentKind.REMOTE_RESOURCE: FindingCode.EXTERNAL_REMOTE_RESOURCE,
    }
    findings: list[ImportFinding] = []
    for found_item in found:
        category = (
            FindingCategory.EXTERNAL_RELATIONSHIP
            if found_item.kind is ActiveContentKind.REMOTE_RESOURCE
            else FindingCategory.ACTIVE_CONTENT
        )
        findings.append(
            ImportFinding(
                code=code_by_kind[found_item.kind],
                severity=FindingSeverity.ERROR,
                category=category,
                description=f"{found_item.description} at offset {found_item.offset}",
                evidence=found_item.evidence,
            )
        )
    return tuple(findings)
