# ADR-007: Deterministic Lexical Normalization

- Date: 2026-08-12
- Status: Accepted for the Pre-SLM program

## Decision

Lexical finalization is conservative, sense-aware, protected-span-aware, style- and
glossary-constrained, deterministic, and a no-op when ambiguity cannot be resolved.
Non-trivial changes require human review.

## Reason

The pre-SLM workflow must improve terminology consistency without becoming a blanket
synonym spinner or detector-score optimization loop.

## Consequence

Every proposal has a versioned ruleset and change journal. Facts, citations,
quotations, and structure are revalidated after accepted changes.
