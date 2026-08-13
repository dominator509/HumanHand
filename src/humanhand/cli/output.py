"""CLI output rendering helpers — human-readable and JSON modes.

All output goes to stdout.  Status and logs go to stderr via the logger.
Color is controlled by ``--no-color`` and the ``NO_COLOR`` environment variable.
"""

from __future__ import annotations

import json
import os
import sys
from typing import Any

from humanhand import __version__
from humanhand.application.import_services import SourceImportResult, StyleImportResult
from humanhand.application.services import (
    DiffFactsResult,
    RewriteResult,
    ScrubResult,
    VerifyResult,
)
from humanhand.domain.canonical_document import ImportInspection
from humanhand.domain.document_serialization import inspection_to_json
from humanhand.infra.config import Config

# ── Color helpers ────────────────────────────────────────────────


def _color_enabled(no_color_flag: bool = False) -> bool:
    """Return True if ANSI color output should be emitted.

    Color is off when:
    - ``--no-color`` is passed.
    - The ``NO_COLOR`` environment variable is set (per https://no-color.org).
    - On Windows, unless the terminal advertises ANSI support.
    """
    if no_color_flag:
        return False
    if os.getenv("NO_COLOR"):
        return False
    if sys.platform == "win32":
        # Only enable if the terminal looks ANSI-capable
        term = os.getenv("TERM", "").lower()
        if "xterm" not in term and "ansi" not in term:
            return False
    return sys.stdout.isatty() if hasattr(sys.stdout, "isatty") else False


def _color(code: int, text: str, no_color: bool = False) -> str:
    """Wrap *text* in an ANSI SGR escape if color is enabled."""
    if _color_enabled(no_color):
        return f"\033[{code}m{text}\033[0m"
    return text


def bold(text: str, no_color: bool = False) -> str:
    """Return *text* in bold."""
    return _color(1, text, no_color)


def red(text: str, no_color: bool = False) -> str:
    """Return *text* in red."""
    return _color(31, text, no_color)


def green(text: str, no_color: bool = False) -> str:
    """Return *text* in green."""
    return _color(32, text, no_color)


def yellow(text: str, no_color: bool = False) -> str:
    """Return *text* in yellow."""
    return _color(33, text, no_color)


def dim(text: str, no_color: bool = False) -> str:
    """Return *text* in dim/low-contrast."""
    return _color(2, text, no_color)


# ── Status helpers ───────────────────────────────────────────────


def status(message: str) -> None:
    """Emit a short status line to stderr (no user text)."""
    print(f"  {message}", file=sys.stderr)


# ── Renderers ────────────────────────────────────────────────────


def render_health(
    config: Config,
    json_mode: bool = False,
    *,
    config_valid: bool = True,
    config_error: str | None = None,
    no_color: bool = False,
    cache_dir_writable: bool | None = None,
    endpoint_url_valid: bool | None = None,
) -> None:
    """Render health check result to stdout."""
    if json_mode:
        result: dict[str, object] = {
            "status": "ok",
            "version": __version__,
            "python_version": sys.version,
            "platform": sys.platform,
            "llm_configured": config.llm_base_url is not None and config.llm_model is not None,
            "detector_provider": config.detector_provider,
            "cache_enabled": config.cache_enabled,
            "cache_dir": str(config.cache_dir),
            "cache_dir_writable": cache_dir_writable,
            "endpoint_url_valid": endpoint_url_valid,
            "config_valid": config_valid,
            "config_error": config_error,
            "commands": {
                "health": True,
                "rewrite": True,
                "verify": True,
                "diff-facts": True,
                "scrub": True,
            },
        }
        print(json.dumps(result))
    else:
        if config_valid:
            print(green("health: ok", no_color))
        else:
            print(yellow("health: configuration is invalid", no_color))


def render_rewrite_result(
    result: RewriteResult,
    json_mode: bool = False,
    *,
    no_color: bool = False,
) -> None:
    """Render rewrite result to stdout."""
    if json_mode:
        output: dict[str, object] = {
            "status": "ok",
            "output_path": result.output_path,
            "input_chars": result.input_chars,
            "output_chars": result.output_chars,
            "repair_attempts": result.repair_attempts,
            "preservation_score": result.preservation_score,
            "duration_ms": result.duration_ms,
        }
        print(json.dumps(output))
    else:
        print(bold(f"Rewrite complete: {result.output_path}", no_color))
        print(f"  Characters: {result.input_chars} → {result.output_chars}")
        if result.repair_attempts > 0:
            print(f"  Repair attempts: {result.repair_attempts}")
        score = result.preservation_score
        score_text = f"{score:.2%}"
        if score >= 0.95:
            score_text = green(score_text, no_color)
        elif score < 0.85:
            score_text = yellow(score_text, no_color)
        print(f"  Fact preservation: {score_text}")


def render_verify_result(
    result: VerifyResult,
    json_mode: bool = False,
    *,
    no_color: bool = False,
) -> None:
    """Render verify result to stdout."""
    if json_mode:
        output: dict[str, object] = {
            "status": "ok",
            "provider": result.provider,
            "model": result.model,
            "score": result.score,
            "label": result.label,
            "cache_hit": result.cache_hit,
            "duration_ms": result.duration_ms,
        }
        print(json.dumps(output))
    else:
        score_str = f"{result.score:.4f}" if result.score is not None else "N/A"
        label_str = result.label or "N/A"
        cache_str = dim(" (cached)", no_color) if result.cache_hit else ""

        # Color-code the label
        if result.label == "human":
            label_str = green(label_str, no_color)
        elif result.label == "ai":
            label_str = red(label_str, no_color)
        else:
            label_str = yellow(label_str, no_color)

        print(f"Verify{cache_str}: score={score_str} label={label_str}")
        print(f"  Provider: {result.provider}/{result.model}")


def render_diff_facts_result(
    result: DiffFactsResult,
    json_mode: bool = False,
    *,
    no_color: bool = False,
) -> None:
    """Render diff-facts result to stdout."""
    report = result.report
    if json_mode:
        output: dict[str, object] = {
            "status": "ok",
            "preservation_score": report.preservation_score,
            "total_source_anchors": report.total_source_anchors,
            "total_candidate_anchors": report.total_candidate_anchors,
            "omissions": len(report.omissions),
            "additions": len(report.additions),
            "contradictions": len(report.contradictions),
            "has_drift": report.has_drift,
            "source_chars": result.source_chars,
            "candidate_chars": result.candidate_chars,
            "duration_ms": result.duration_ms,
        }
        print(json.dumps(output))
    else:
        score = report.preservation_score
        score_text = f"{score:.2%}"
        if score >= 0.95:
            score_text = green(score_text, no_color)
        elif score < 0.85:
            score_text = red(score_text, no_color)
        else:
            score_text = yellow(score_text, no_color)

        print(f"Fact diff: preservation={score_text}")
        print(f"  Source anchors: {report.total_source_anchors}")
        print(f"  Candidate anchors: {report.total_candidate_anchors}")
        print(f"  Omissions: {len(report.omissions)}")
        print(f"  Additions: {len(report.additions)}")
        print(f"  Contradictions: {len(report.contradictions)}")
        if report.has_drift:
            print(f"  {yellow('⚠ Factual drift detected', no_color)}")


def render_scrub_result(
    result: ScrubResult,
    json_mode: bool = False,
    *,
    no_color: bool = False,
) -> None:
    """Render scrub result to stdout."""
    report = result.report
    if json_mode:
        output: dict[str, object] = {
            "status": "ok",
            "audit_only": result.audit_only,
            "output_path": result.output_path,
            "findings_count": len(report.findings),
            "modifications": report.modifications,
            "findings": [
                {
                    "category": f.category,
                    "location": f.location,
                    "description": f.description,
                    "removed": f.removed,
                }
                for f in report.findings
            ],
            "duration_ms": result.duration_ms,
        }
        print(json.dumps(output))
    else:
        mode_str = "Audit" if result.audit_only else "Scrub"
        summary = f"{mode_str} complete: {len(report.findings)} finding(s)"
        if len(report.findings) == 0:
            summary = green(summary, no_color)
        print(summary)
        for f in report.findings:
            removed_str = dim(" [removed]", no_color) if f.removed else ""
            cat = bold(f"[{f.category}]", no_color)
            print(f"  {cat} {f.location}: {f.description}{removed_str}")
        if not result.audit_only and result.output_path:
            print(f"  Output: {result.output_path}")


# ── Style Fidelity Vault renderers (EP-014) ────────────────────────


def _asdict_payload(value: Any) -> dict[str, object]:
    import dataclasses

    payload = dataclasses.asdict(value)
    return payload


def render_style_review(
    package: object,
    json_mode: bool = False,
    *,
    no_color: bool = False,
) -> None:
    """Render a style package review state."""
    if json_mode:
        from humanhand.domain.style_serialization import package_to_payload

        print(
            json.dumps(package_to_payload(package), sort_keys=True, ensure_ascii=False)  # type: ignore[arg-type]
        )
        return
    authorship = package.authorship  # type: ignore[attr-defined]
    print(f"Style package: {package.package_id}")  # type: ignore[attr-defined]
    print(f"  Profile label: {package.profile_label}")  # type: ignore[attr-defined]
    print(f"  Spans: {len(authorship.spans)}")
    print(f"  Unresolved: {len(authorship.unresolved_spans)}")
    for span in authorship.spans:
        marker = " " if span.is_resolved else "*"
        print(
            f"  {marker} {span.span_id} [{span.authorship_class.value}] "
            f"({span.source_location.start_offset}..{span.source_location.end_offset})"
        )
    for excluded in authorship.excluded:
        print(f"  x {excluded.span_id} [excluded] {excluded.reason}")


def render_style_profile(
    profile: object,
    json_mode: bool = False,
    *,
    no_color: bool = False,
) -> None:
    """Render a style evidence profile."""
    if json_mode:
        from humanhand.domain.style_profiles import profile_to_json

        print(profile_to_json(profile), end="")  # type: ignore[arg-type]
        return
    print(f"Style profile: {profile.profile_id}")  # type: ignore[attr-defined]
    print(f"  Status: {profile.status}")  # type: ignore[attr-defined]
    print(f"  Sample words: {profile.sample_word_count}")  # type: ignore[attr-defined]
    print(f"  Packages: {len(profile.package_ids)}")  # type: ignore[attr-defined]
    print(f"  Hard invariants: {len(profile.hard_invariants)}")  # type: ignore[attr-defined]
    print(f"  Soft tendencies: {len(profile.soft_tendencies)}")  # type: ignore[attr-defined]


def render_style_coverage(
    report: object,
    json_mode: bool = False,
    *,
    no_color: bool = False,
) -> None:
    """Render a style coverage report."""
    if json_mode:
        print(json.dumps(_asdict_payload(report), sort_keys=True, ensure_ascii=False))
        return
    print(f"Coverage: {report.status}")  # type: ignore[attr-defined]
    print(f"  Visible text: {report.visible_text_coverage:.0%}")  # type: ignore[attr-defined]
    print(f"  Sample sufficiency: {report.sample_sufficiency}")  # type: ignore[attr-defined]
    print(f"  Unresolved spans: {report.unresolved_span_count}")  # type: ignore[attr-defined]


def render_style_invariants(
    profile: object,
    json_mode: bool = False,
    *,
    no_color: bool = False,
) -> None:
    """Render hard invariants and soft tendencies."""
    invariants = profile.hard_invariants  # type: ignore[attr-defined]
    tendencies = profile.soft_tendencies  # type: ignore[attr-defined]
    if json_mode:
        payload = {
            "hard_invariants": [_asdict_payload(item) for item in invariants],
            "soft_tendencies": [_asdict_payload(item) for item in tendencies],
        }
        print(json.dumps(payload, sort_keys=True, ensure_ascii=False))
        return
    for invariant in invariants:
        print(f"  [{invariant.status.value}] {invariant.kind.value}: {invariant.value}")
    for tendency in tendencies:
        print(f"  ~ {tendency.name} ({tendency.strength}): {tendency.value}")


def render_style_comparison(
    report: object,
    json_mode: bool = False,
    *,
    no_color: bool = False,
) -> None:
    """Render a style comparison report (no authorship conclusion)."""
    if json_mode:
        print(json.dumps(_asdict_payload(report), sort_keys=True, ensure_ascii=False))
        return
    print(f"Comparison: {report.profile_id}")  # type: ignore[attr-defined]
    print(f"  Confidence: {report.confidence:.2%}")  # type: ignore[attr-defined]
    print(f"  Evidence coverage: {report.evidence_coverage:.0%}")  # type: ignore[attr-defined]
    print(f"  Invariant violations: {len(report.hard_invariant_violations)}")  # type: ignore[attr-defined]
    for violation in report.hard_invariant_violations:  # type: ignore[attr-defined]
        print(f"  ! {violation.kind.value}: {violation.evidence}")
    print("  No authorship conclusion is drawn.")


def render_import_inspection(
    inspection: ImportInspection,
    json_mode: bool = False,
    *,
    no_color: bool = False,
    include_content: bool = False,
) -> None:
    """Render an import inspection result to stdout.

    Findings never contain user text; canonical content is opt-in via
    ``include_content`` and JSON-only.
    """
    if json_mode:
        payload = inspection.to_payload(include_content=include_content)
        print(json.dumps(payload, sort_keys=True, ensure_ascii=False))
        return

    identity = inspection.file_identity
    print(
        f"Import: {inspection.status.value} ({identity.given_path})"
        f" [{identity.declared_kind.value}, {identity.size_bytes} bytes, "
        f"{identity.magic.description}]"
    )
    print(f"  Findings: {len(inspection.findings)}")
    for finding in inspection.findings:
        location = ""
        if finding.location is not None:
            location = f" @line {finding.location.line_start}"
        print(
            f"  - {bold(f'[{finding.category.value}]', no_color)} "
            f"{finding.code}: {finding.description}{location}"
        )
    if inspection.measurements is not None:
        measurements = inspection.measurements
        print(
            f"  Nodes: {measurements.node_count}, depth {measurements.tree_depth}, "
            f"expanded {measurements.expanded_bytes} bytes"
        )


def render_source_import_result(
    result: SourceImportResult,
    json_mode: bool = False,
    *,
    no_color: bool = False,
) -> None:
    """Render a source-lane import result to stdout.

    JSON mode emits the full source package (document + evidence). When the
    import failed closed, JSON mode emits the inspection instead so the
    reason is always visible.
    """
    if result.package is not None:
        if json_mode:
            print(result.package.to_json(), end="")
        else:
            package = result.package
            print(f"Source package: {package.package_id}")
            print(f"  Status: {package.status.value}")
            print(f"  Nodes: {len(package.document.nodes)}")
            print(f"  Protected spans: {len(package.evidence.protected_spans.spans)}")
            print(f"  Quotations: {len(package.evidence.quotations)}")
            print(f"  Citations: {len(package.evidence.citations)}")
            print(f"  Findings: {len(package.findings)}")
        return

    # Fail-closed: no package; explain via the inspection.
    if json_mode:
        print(inspection_to_json(result.inspection), end="")
    else:
        render_import_inspection(result.inspection, json_mode=False, no_color=no_color)


def render_style_import_result(
    result: StyleImportResult,
    json_mode: bool = False,
    *,
    no_color: bool = False,
    vault_package_id: str | None = None,
) -> None:
    """Render a style-lane import result to stdout.

    JSON mode emits the full style sample package (document + metadata,
    never fact evidence) plus the vault review handle when persisted.
    Fail-closed imports emit the inspection instead.
    """
    if result.package is not None:
        if json_mode:
            if vault_package_id is not None:
                import json as _json

                payload = json.loads(result.package.to_json())
                payload["vault_package_id"] = vault_package_id
                print(_json.dumps(payload, sort_keys=True, ensure_ascii=False), end="")
                return
            print(result.package.to_json(), end="")
        else:
            package = result.package
            print(f"Style package: {package.package_id}")
            print(f"  Status: {package.status.value}")
            print(f"  Authorship status: {package.authorship_status}")
            print(f"  Nodes: {len(package.document.nodes)}")
            print(f"  Metadata items: {len(package.metadata.items)}")
            print(f"  Findings: {len(package.findings)}")
        return

    if json_mode:
        print(inspection_to_json(result.inspection), end="")
    else:
        render_import_inspection(result.inspection, json_mode=False, no_color=no_color)
