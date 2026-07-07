"""CLI output rendering helpers — human-readable and JSON modes.

All output goes to stdout.  Status and logs go to stderr via the logger.
Color is controlled by ``--no-color`` and the ``NO_COLOR`` environment variable.
"""

from __future__ import annotations

import json
import os
import sys

from humanhand import __version__
from humanhand.application.services import (
    DiffFactsResult,
    RewriteResult,
    ScrubResult,
    VerifyResult,
)
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
        term = os.getenv("TERM", "")
        if "xterm" not in term and "ansi" not in term.lower():
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
) -> None:
    """Render health check result to stdout."""
    if json_mode:
        result: dict[str, object] = {
            "status": "ok",
            "version": __version__,
            "python_version": sys.version,
            "platform": sys.platform,
            "llm_configured": config.llm_base_url is not None,
            "detector_provider": config.detector_provider,
            "cache_enabled": config.cache_enabled,
            "cache_dir": str(config.cache_dir),
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
        print(green("health: ok", no_color))


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
