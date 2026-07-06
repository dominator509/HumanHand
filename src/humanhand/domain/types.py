"""Shared domain types — dataclasses, enums, and exceptions."""

from __future__ import annotations

from dataclasses import dataclass, field
from enum import Enum, auto


class RepairDecision(Enum):
    """Deterministic repair-loop state transition."""

    ACCEPT = auto()
    REPAIR = auto()
    FAIL = auto()


class DomainError(Exception):
    """Base exception for domain-layer errors."""


@dataclass(frozen=True)
class StyleFingerprint:
    """Deterministic style traits extracted from a human writing sample."""

    avg_sentence_length: float = 0.0
    sentence_length_variance: float = 0.0
    avg_paragraph_length: float = 0.0
    punctuation_ratios: dict[str, float] = field(default_factory=dict)
    vocabulary_richness: float = 0.0
    common_phrases: tuple[str, ...] = ()
    formality_score: float = 0.0
    avg_word_length: float = 0.0
    total_sentences: int = 0
    total_paragraphs: int = 0
    total_words: int = 0


@dataclass(frozen=True)
class FactAnchor:
    """A factual item extracted from text."""

    text: str
    category: str  # "number", "date", "entity", "claim", "quote", "citation"
    position: int  # character offset in source text


@dataclass(frozen=True)
class FactDiffReport:
    """Result of comparing factual anchors between source and candidate."""

    omissions: tuple[FactAnchor, ...] = ()
    additions: tuple[FactAnchor, ...] = ()
    contradictions: tuple[tuple[FactAnchor, FactAnchor], ...] = ()
    preservation_score: float = 1.0
    total_source_anchors: int = 0
    total_candidate_anchors: int = 0

    @property
    def has_drift(self) -> bool:
        return len(self.omissions) > 0 or len(self.additions) > 0 or len(self.contradictions) > 0


@dataclass(frozen=True)
class ScrubFinding:
    """A single metadata-like artifact found during scrub audit."""

    category: str
    location: str  # "header", "body", "footer", "embedded"
    description: str
    removed: bool = False


@dataclass(frozen=True)
class ScrubReport:
    """Result of scrubbing metadata from candidate output."""

    findings: tuple[ScrubFinding, ...] = ()
    cleaned_text: str = ""
    modifications: int = 0


@dataclass(frozen=True)
class PromptContract:
    """Deterministic prompt payload for LLM rewrite or repair."""

    system_message: str = ""
    user_message: str = ""
    schema_fields: tuple[str, ...] = ()
