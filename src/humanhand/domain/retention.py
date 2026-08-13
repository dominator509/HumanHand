"""Retention policy and read-only retention scanning (SPEC-013, blueprint 10).

Retention applies to exactly two scopes — ``cache`` and ``reports`` — and
is enforced only when the active privacy policy enables it. This module is
strictly read-only: it reports expired files but never deletes anything.
Deletion belongs to the infra enforcement layer in a later plan.
"""

from __future__ import annotations

import os
import time
from dataclasses import dataclass

from humanhand.domain.privacy import PrivacyPolicy
from humanhand.domain.types import DomainError

RETENTION_SCHEMA_VERSION = 1
_SCHEMA_NAME = "retention-policy"

#: The only two retention scopes this module ever emits.
RETENTION_SCOPES: tuple[str, ...] = ("cache", "reports")

_DAY_SECONDS = 86400


@dataclass(frozen=True)
class RetentionPolicy:
    """Immutable retention policy."""

    enabled: bool
    max_age_days: int = 30
    scopes: tuple[str, ...] = RETENTION_SCOPES


def retention_policy_for(privacy: PrivacyPolicy) -> RetentionPolicy:
    """Map a privacy policy to the retention policy it requires.

    Retention is enforced exactly when ``privacy.retention_enforced`` is
    True. The 30-day default and the scope set (``cache``, ``reports``)
    are the module's only values; regulated-mode extras (encrypted
    sensitive fields, immutable audit records) are already reflected in
    the privacy policy itself and do not change this mapping.
    """
    return RetentionPolicy(enabled=privacy.retention_enforced)


def retention_to_payload(policy: RetentionPolicy) -> dict[str, object]:
    """Render a retention policy as a stable JSON-ready payload.

    Raises DomainError when the policy scopes are anything other than the
    module's two documented scopes.
    """
    if policy.scopes != RETENTION_SCOPES:
        raise DomainError("Retention policy scopes must be exactly ('cache', 'reports')")
    return {
        "schema": _SCHEMA_NAME,
        "schema_version": RETENTION_SCHEMA_VERSION,
        "enabled": policy.enabled,
        "max_age_days": policy.max_age_days,
        "scopes": list(policy.scopes),
    }


@dataclass(frozen=True)
class RetentionFinding:
    """One file that exceeds the retention age."""

    path: str  # relative path under the scanned directory
    age_days: int
    action: str  # "expired"


def scan_retention(directory: str, policy: RetentionPolicy) -> tuple[RetentionFinding, ...]:
    """READ-ONLY scan of a directory for files older than ``max_age_days``.

    Walks the directory non-recursively and reports only regular files
    (symlinks excluded) whose mtime is older than the cutoff. Findings are
    returned in sorted path order with ``age_days`` floored to whole days.
    NO deletion ever happens here: this module only reports, and deletion
    belongs to the infra enforcement layer in a later plan.

    Raises DomainError when the directory does not exist or is not a
    directory, a file cannot be stat'd, the age limit is negative, or the
    policy carries scopes other than the module's two documented scopes.
    """
    if not policy.enabled:
        return ()
    if policy.max_age_days < 0:
        raise DomainError("Retention max_age_days must be non-negative")
    if policy.scopes != RETENTION_SCOPES:
        raise DomainError("Retention policy scopes must be exactly ('cache', 'reports')")
    try:
        entries = list(os.scandir(directory))
    except OSError as exc:
        raise DomainError(f"Cannot scan retention directory {directory!r}: {exc}") from exc
    now = time.time()
    cutoff = now - policy.max_age_days * _DAY_SECONDS
    findings: list[RetentionFinding] = []
    for entry in entries:
        if not entry.is_file(follow_symlinks=False):
            continue
        try:
            stat = entry.stat(follow_symlinks=False)
        except OSError as exc:
            raise DomainError(f"Cannot stat retention candidate {entry.name!r}: {exc}") from exc
        if stat.st_mtime >= cutoff:
            continue
        age_days = int((now - stat.st_mtime) / _DAY_SECONDS)
        findings.append(RetentionFinding(path=entry.name, age_days=age_days, action="expired"))
    findings.sort(key=lambda finding: finding.path)
    return tuple(findings)
