---
id: EP-017
title: Deterministic Lexical Finalization and Human Review
status: complete
owner: claude
created: 2026-08-12
updated: 2026-08-13
---

# EP-017: Deterministic Lexical Finalization

## Purpose / Big Picture

Add conservative deterministic lexical proposals and human review without an SLM or
detector-score objective.

## Scope

Sense-aware rules, multiword expressions, inflection/collocation handling, protected
spans, glossary/style precedence, change journals, review commands, and revalidation.

## Non-goals

Blanket synonym spinning, semantic micro-repair, detector optimization, or automatic
acceptance of ambiguous changes.

## Context and Orientation

Follow SPEC-014, ADR-007, protected/project facts from EP-015, and style profiles from
EP-014.

## Files to Read First

Authority stack, SPEC-014, ADR-007, domain/application modules, lexical resource policy,
fact/style validators, and blueprint lexical sections.

## Files to Change

Lexical domain/application/infra/CLI modules, schemas/rulesets, synthetic fixtures,
unit/integration/E2E tests, docs/scripts, and this plan.

## Interfaces and Contracts

Precedence is explicit; ambiguity is no-op; every change has a stable id/reason/ruleset;
accepted changes revalidate facts, citations, protected spans, and structure.

## Milestones

### M1 - Rule and context model

Goal: add versioned rules, senses, contexts, and protected-span checks. Validation:
`sh scripts/test-unit.sh`. Expected: unit tests pass. Recovery: no-op on uncertainty.

### M2 - Proposal pipeline

Goal: add deterministic changes and review journal. Validation: `sh scripts/test-integration.sh`.
Expected: pipeline tests pass. Recovery: reject questionable proposals.

### M3 - CLI and compatibility

Goal: expose finalize commands and preserve old workflow. Validation: `sh scripts/test-e2e.sh`.
Expected: E2E tests pass. Recovery: keep finalization opt-in.

### M4 - Boundary

Goal: full validation and handoff. Validation: `sh scripts/verify.sh`. Expected:
`verify: ok`. Recovery: bounded retry with exact evidence.

## Concrete Steps

Implement milestones in order, keep resources licensed/local, update the plan, and write
state last.

## Validation and Acceptance

Equal inputs/rulesets yield equal journals; protected facts and structure are unchanged;
ambiguous changes remain review-required; no detector score is consumed.

## Idempotence and Recovery

Rulesets are versioned and changes replayable. Never mutate the source or immutable style
artifact in place.

## Progress

- [x] M1
- [x] M2
- [x] M3
- [x] M4

## Surprises & Discoveries

- Partial-merge code performed lexicon I/O in the domain layer and the CLI
  called a proposal function without its required context and span inputs.
- Candidate generation omitted preference/glossary-only surfaces, multiword
  precedence, punctuation-safe offsets, and common silent-e inflections.
- The review CLI expected a nonexistent mutable journal API; accepted-change
  fact/citation revalidation was not represented explicitly.

## Decision Log

- Load bundled lexicons only through infra and validate resource payloads
  before constructing immutable domain rules.
- Resolve multiword candidates first, treat equal-precedence conflicting senses
  as ambiguity/no-op, preserve punctuation offsets, and fail on document hash
  drift before applying changes.
- Persist append-only review history, compact latest decisions into the domain
  journal for validation, and do not mutate source documents from accept/reject.
- Provide count-only fact/citation drift findings alongside structure
  revalidation so later application paths can fail closed without logging text.
- Extend `COMMANDS.md` with scoped pytest and selected-file Ruff-fix diagnostics
  used by the anti-fixation workflow; no runtime interface changed.

## Outcomes & Retrospective

Complete. Lexical proposals and review journals replay deterministically,
protected spans and ambiguity gates are enforced, and explicit facts,
citations, and structure revalidation contracts are covered. Full verification
passes with 1948 tests passed, 15 skipped, 86.35% coverage, and `verify: ok`.
