# SPEC-014: Deterministic Lexical Finalization

## Purpose

Apply conservative terminology and style lexical preferences without a model or
detector-score objective.

## Data Contracts

Contracts include `LexicalRule`, `LexicalContext`, `LexicalChange`, `RulesetVersion`,
and `ReviewDecision`, with source offsets, precedence, confidence, and reason.

## Invariants

Precedence is protected span, user preference, project glossary, register evidence,
domain glossary, curated rule, licensed local resource, then no change. Multiword
expressions precede tokens; ambiguity is a deterministic no-op.

## Inputs and Outputs

Inputs are approved working documents, style profiles, protected spans, and local
glossaries. Outputs are proposals, accepted revisions, and a deterministic change
journal.

## Privacy Rules

No detector score, remote corpus, or external model response is an input. Rulesets and
private profile references remain outside public artifacts.

## Failure Behavior

Ambiguous sense, unsupported inflection, protected overlap, fact/structure drift, or
missing human approval leaves the candidate unchanged and emits a review finding.

## CLI Behavior

Implement `finalize lexical`, `review`, `accept`, and `reject`. Non-trivial changes
require explicit human review.

## JSON Result Schema

Results contain `schema_version`, `run_id`, `ruleset_hash`, ordered changes, review
state, and validation findings. Generated prose is not printed by default.

## Backward Compatibility

Existing rewrite/fact-diff outputs remain available. The lexical stage is additive until
an explicit migration makes it part of the default workflow.

## Test Requirements

Test senses, inflections, collocations, protected spans, ambiguity no-op, determinism,
facts/citations/structure, review decisions, and detector-independence.

## Explicit Non-goals

Synonym spinning, semantic micro-repair, detector optimization, and automatic acceptance
of questionable changes.

## Acceptance Criteria

Equal inputs and rulesets yield equal journals, protected content is unchanged, and
uncertain changes remain human-reviewable rather than silently applied.
