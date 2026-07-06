"""Prompt contract construction — deterministic prompt building for LLM calls."""

from __future__ import annotations

from humanhand.domain.types import FactAnchor, FactDiffReport, PromptContract, StyleFingerprint


def build_rewrite_prompt(
    source: str,
    style_sample: str,
    fingerprint: StyleFingerprint,
    facts: list[FactAnchor],
) -> PromptContract:
    """Build a prompt contract for the initial rewrite request.

    The prompt instructs the LLM to rewrite source text in the target style
    while preserving all factual content and returning plain text only.

    Args:
        source: The AI-assisted source text to rewrite.
        style_sample: The human writing sample to match.
        fingerprint: Computed style fingerprint of the sample.
        facts: Extracted factual anchors from the source.

    Returns:
        PromptContract with system message, user message, and schema fields.
    """
    style_description = _describe_style(fingerprint)

    fact_summary_lines = [
        f"- {a.category}: {a.text}"
        for a in facts[:20]  # Cap at 20 for prompt size
    ]
    fact_summary = "\n".join(fact_summary_lines) if fact_summary_lines else "(none)"

    system_message = (
        "You are a precise text rewriter. Your task is to rewrite the provided text "
        "to match a target human writing style while preserving ALL factual content exactly.\n\n"
        "CRITICAL RULES:\n"
        "1. Preserve every fact, number, date, name, entity, and claim from the source.\n"
        "2. Match the target style's sentence structure, vocabulary level, and tone.\n"
        "3. Output ONLY plain text with no markdown, no JSON wrappers, no metadata.\n"
        "4. Do not add facts, commentary, disclaimers, or extra content.\n"
        "5. Do not include model names, provenance markers, or generation tags.\n"
        "6. Use standard UTF-8 text with normal paragraph breaks."
    )

    user_message = (
        f"SOURCE TEXT:\n```\n{source}\n```\n\n"
        f"TARGET STYLE SAMPLE:\n```\n{style_sample}\n```\n\n"
        f"STYLE CHARACTERISTICS TO MATCH:\n{style_description}\n\n"
        f"FACTS THAT MUST BE PRESERVED:\n{fact_summary}\n\n"
        "Rewrite the source text in the target style. Output plain text only."
    )

    return PromptContract(
        system_message=system_message,
        user_message=user_message,
        schema_fields=("rewritten_text",),
    )


def build_repair_prompt(
    source: str,
    candidate: str,
    diff_report: FactDiffReport,
    attempt: int,
) -> PromptContract:
    """Build a prompt contract for a repair attempt.

    Tells the LLM what facts were lost or changed and asks for a correction.

    Args:
        source: Original source text.
        candidate: Previous candidate output that needs repair.
        diff_report: The fact diff report showing what went wrong.
        attempt: Current repair attempt number (1-indexed).

    Returns:
        PromptContract for the repair request.
    """
    system_message = (
        "You are repairing a text rewrite that lost or changed some facts. "
        "Fix ONLY the factual errors listed below. Keep the style unchanged. "
        "Output ONLY plain text with no metadata."
    )
    issue_summary = _describe_diff_report(diff_report)

    user_message = (
        f"ORIGINAL SOURCE:\n```\n{source}\n```\n\n"
        f"PREVIOUS ATTEMPT (repair #{attempt}):\n```\n{candidate}\n```\n\n"
        f"FACTUAL ISSUES TO FIX:\n{issue_summary}\n\n"
        "Please fix the factual errors and output the corrected text as plain text only."
    )

    return PromptContract(
        system_message=system_message,
        user_message=user_message,
        schema_fields=("rewritten_text",),
    )


def _describe_style(fp: StyleFingerprint) -> str:
    """Build a natural-language description of a style fingerprint."""
    parts: list[str] = []

    if fp.total_words > 0:
        parts.append(
            f"Average sentence length: {fp.avg_sentence_length:.1f} words "
            f"(variance: {fp.sentence_length_variance:.1f})"
        )
        parts.append(f"Average word length: {fp.avg_word_length:.1f} characters")
        parts.append(f"Vocabulary richness: {fp.vocabulary_richness:.2%}")

    if fp.total_paragraphs > 0:
        parts.append(f"Average paragraph length: {fp.avg_paragraph_length:.1f} sentences")

    if fp.formality_score > 0.6:
        parts.append("Tone: formal and academic")
    elif fp.formality_score > 0.3:
        parts.append("Tone: neutral and balanced")
    else:
        parts.append("Tone: casual and conversational")

    if fp.common_phrases:
        phrases_str = ", ".join(fp.common_phrases[:5])
        parts.append(f"Common phrases: {phrases_str}")

    punct_notes = []
    if fp.punctuation_ratios.get("comma", 0) > 0.01:
        punct_notes.append("frequent comma use")
    if fp.punctuation_ratios.get("semicolon", 0) > 0.001:
        punct_notes.append("semicolon use")
    if fp.punctuation_ratios.get("dash", 0) > 0.0005:
        punct_notes.append("em-dash use")
    if fp.punctuation_ratios.get("question", 0) > 0.001:
        punct_notes.append("rhetorical questions")
    if punct_notes:
        parts.append("Punctuation style: " + ", ".join(punct_notes))

    return "\n".join(f"- {p}" for p in parts)


def _describe_diff_report(diff_report: FactDiffReport) -> str:
    """Summarize factual issues that a repair pass must address."""
    issues: list[str] = []

    for anchor in diff_report.omissions[:10]:
        issues.append(f"- Restore missing {anchor.category}: {anchor.text}")

    for anchor in diff_report.additions[:10]:
        issues.append(f"- Remove unsupported {anchor.category}: {anchor.text}")

    for source_anchor, candidate_anchor in diff_report.contradictions[:10]:
        issues.append(
            "- Replace contradicted "
            f"{source_anchor.category}: source '{source_anchor.text}' became "
            f"'{candidate_anchor.text}'"
        )

    if not issues:
        return "- No explicit diff items were recorded; improve factual fidelity conservatively."

    return "\n".join(issues)
