"""Unit tests for prompt contract construction."""

from humanhand.domain.prompts import build_repair_prompt, build_rewrite_prompt
from humanhand.domain.types import (
    FactAnchor,
    FactDiffReport,
    PromptContract,
    StyleFingerprint,
)


class TestBuildRewritePrompt:
    def test_basic_prompt(self) -> None:
        source = "The study found 42% improvement."
        style = "The analysis revealed significant progress."
        fp = StyleFingerprint(total_words=5, avg_sentence_length=10.0)
        facts = [FactAnchor(text="42%", category="number", position=16)]

        contract = build_rewrite_prompt(source, style, fp, facts)

        assert isinstance(contract, PromptContract)
        assert len(contract.system_message) > 0
        assert len(contract.user_message) > 0
        assert source in contract.user_message
        assert style in contract.user_message
        assert "42%" in contract.user_message
        assert "rewritten_text" in contract.schema_fields

    def test_no_facts(self) -> None:
        source = "Hello world."
        style = "Greetings earth."
        fp = StyleFingerprint()

        contract = build_rewrite_prompt(source, style, fp, [])

        assert "Hello world" in contract.user_message
        assert "Greetings earth" in contract.user_message

    def test_fact_cap_at_20(self) -> None:
        source = "test " * 50
        style = "style sample"
        fp = StyleFingerprint(total_words=50)
        facts = [FactAnchor(text=str(i), category="number", position=i) for i in range(30)]

        contract = build_rewrite_prompt(source, style, fp, facts)
        # Should cap facts at 20 in the prompt
        fact_lines = [
            line for line in contract.user_message.split("\n") if line.startswith("- number:")
        ]
        assert len(fact_lines) <= 20

    def test_system_message_includes_rules(self) -> None:
        source = "text"
        style = "sample"
        fp = StyleFingerprint()
        facts: list[FactAnchor] = []

        contract = build_rewrite_prompt(source, style, fp, facts)
        assert "plain text" in contract.system_message.lower()
        assert "fact" in contract.system_message.lower()

    def test_long_source_handled(self) -> None:
        source = "The quick brown fox. " * 500
        style = "sample"
        fp = StyleFingerprint(total_words=10)
        facts: list[FactAnchor] = []

        contract = build_rewrite_prompt(source, style, fp, facts)
        assert source in contract.user_message

    def test_style_description_all_branches(self) -> None:
        """Cover _describe_style: total_paragraphs, formality, common_phrases, punctuation."""
        source = "Some source text."
        style = "Some style sample."
        fp = StyleFingerprint(
            total_words=100,
            avg_sentence_length=18.0,
            sentence_length_variance=4.0,
            avg_paragraph_length=3.5,
            total_paragraphs=4,
            formality_score=0.45,
            common_phrases=("in other words", "for example"),
            punctuation_ratios={
                "comma": 0.03,
                "semicolon": 0.005,
                "dash": 0.002,
                "question": 0.005,
            },
            vocabulary_richness=0.55,
        )
        facts: list[FactAnchor] = []

        contract = build_rewrite_prompt(source, style, fp, facts)

        # Line 116: total_paragraphs > 0
        assert "Average paragraph length" in contract.user_message
        # Line 121: formality_score in (0.3, 0.6] → neutral tone
        assert "neutral and balanced" in contract.user_message
        # Line 126-127: common_phrases non-empty
        assert "Common phrases:" in contract.user_message
        assert "in other words" in contract.user_message
        # Punctuation (lines 131-139)
        assert "frequent comma use" in contract.user_message
        assert "semicolon use" in contract.user_message
        assert "em-dash use" in contract.user_message
        assert "rhetorical questions" in contract.user_message
        assert "Punctuation style:" in contract.user_message

    def test_style_description_formal_tone(self) -> None:
        """Line 119: formality_score > 0.6 produces formal tone description."""
        source = "Source text."
        style = "Style text."
        fp = StyleFingerprint(
            total_words=50,
            avg_sentence_length=22.0,
            formality_score=0.85,
        )
        contract = build_rewrite_prompt(source, style, fp, [])
        assert "formal and academic" in contract.user_message


class TestBuildRepairPrompt:
    def test_basic_repair(self) -> None:
        source = "Original text."
        candidate = "Fixed text."
        diff = FactDiffReport(omissions=(), additions=(), contradictions=())

        contract = build_repair_prompt(source, candidate, diff, attempt=1)

        assert isinstance(contract, PromptContract)
        assert len(contract.system_message) > 0
        assert "repair" in contract.system_message.lower()
        assert source in contract.user_message
        assert candidate in contract.user_message

    def test_repair_attempt_tracked(self) -> None:
        source = "text"
        candidate = "text"
        diff = FactDiffReport()

        contract = build_repair_prompt(source, candidate, diff, attempt=3)
        assert "repair #3" in contract.user_message

    def test_repair_prompt_includes_diff_details(self) -> None:
        source = "Alice paid $50 on 2024-01-15."
        candidate = "Alice paid $60."
        diff = FactDiffReport(
            omissions=(FactAnchor(text="2024-01-15", category="date", position=18),),
            additions=(FactAnchor(text="$60", category="number", position=12),),
            contradictions=(
                (
                    FactAnchor(text="$50", category="number", position=12),
                    FactAnchor(text="$60", category="number", position=12),
                ),
            ),
        )

        contract = build_repair_prompt(source, candidate, diff, attempt=2)
        assert "Restore missing date: 2024-01-15" in contract.user_message
        assert "Remove unsupported number: $60" in contract.user_message
        assert "source '$50' became '$60'" in contract.user_message
