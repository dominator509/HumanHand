---
id: EP-017
title: Deterministic Lexical Finalization and Human Review
status: planned
owner: claude
created: 2026-08-12
updated: 2026-08-12
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

- [ ] M1
- [ ] M2
- [ ] M3
- [ ] M4

## Surprises & Discoveries

Record lexical coverage, license, and ambiguity findings.

## Decision Log

Record rule precedence, resource, and review decisions.

## Outcomes & Retrospective

Complete at the boundary with deterministic replay and review evidence.
