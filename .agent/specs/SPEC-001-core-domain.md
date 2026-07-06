# SPEC-001: Core Domain

## Status

Accepted blueprint specification.

## Owner

Blueprint / Maintainer.

## Linked Roadmap Phase

Phase 1: Core domain.

## Linked ExecPlans

EP-002, with related validation in EP-004 and EP-007.

## User-Visible Goal

Human Hand rewrites text in the supplied human style while preserving factual content and removing metadata-like artifacts.

## Non-Goals

- Network calls, file I/O, cache access, logging, CLI parsing, detector HTTP clients, LLM SDK usage, or paid provider logic in domain.
- Guaranteeing legal/academic acceptability.
- Training or fine-tuning models.

## Terms

- Style fingerprint: Structured representation of voice, syntax, punctuation, vocabulary, paragraph shape, idioms, and formatting tendencies.
- Fact anchor: Extracted factual item such as named entity, number, date, claim, relation, citation-like marker, or quoted phrase.
- Drift: Omission, contradiction, or unsupported addition relative to source facts.
- Metadata marker: BOM, provenance header, JSON wrapper, model tag, detector tag, telemetry-like field, or hidden marker.
- Repair decision: Deterministic decision to accept output, request repair, or fail.

## Required Behavior

- Build style fingerprint from style sample using deterministic pure functions.
- Extract fact anchors from source and output.
- Compare fact anchors and produce drift report with omissions, additions, contradictions, and preservation score.
- Build prompt contracts that require style matching, fact preservation, plain text output, no metadata, and no hidden wrappers.
- Scrub metadata-like markers from candidate output before writing.
- Decide repair loop state based on drift and scrub results.
- Respect deterministic seed where randomness is needed; prefer deterministic algorithms.

## Inputs

- Source text string.
- Style sample text string.
- Candidate output text string.
- Optional thresholds and seed.

## Outputs

- `StyleFingerprint` value object.
- `FactDiffReport` value object.
- `ScrubReport` value object.
- Prompt payload or message contract value object.
- `RepairDecision` value object.
- Clean output text string.

## Error States

- Empty source/style/candidate.
- Input exceeds configured cap.
- Non-string or invalid types at pure boundary.
- Unscrubbable metadata if output cannot be made clean without losing content.
- Fact drift above acceptable threshold.

## Data Rules

- Domain functions do not persist data.
- Domain may compute hashes but must not log.
- Domain results must not include full prompts in objects intended for logging.

## Security Rules

- Domain scrubber must remove metadata markers before infra writes output.
- Domain must not include secrets or env values.
- Domain must not include source/style text in error messages intended for logs.

## Accessibility Rules

Not applicable to domain logic.

## Performance Rules

- Domain processing should handle 200,000 characters without excessive memory growth.
- Prefer linear or near-linear text scans.

## Observability Rules

- Domain emits no logs.
- Application/infra may log lengths and hash prefixes derived from domain inputs.

## Required Tests

- Style fingerprint unit tests for vocabulary, punctuation, paragraph shape, idiom, and formatting tendencies.
- Fact extraction/diff tests for numbers, dates, names, claims, omitted facts, added facts, contradictions.
- Scrub tests for BOM, JSON wrappers, model markers, metadata headers, trailing whitespace, CRLF normalization, exactly one newline.
- Prompt contract tests asserting plain text/no metadata/fact preservation instructions.
- Repair decision tests for accept, repair, and fail states.
- Import-boundary test proving domain does not import infra/cli/http libraries.

## Acceptance Criteria

- Domain tests pass.
- Domain has no I/O/network/env/logging dependencies.
- Output scrub is deterministic.
- Fact diff report is machine-friendly and used by CLI/application paths.
- No user text is embedded in log-oriented errors.
