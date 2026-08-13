---
id: EP-014
title: Style Fidelity Vault and Style Evidence Profile
status: planned
owner: claude
created: 2026-08-12
updated: 2026-08-12
---

# EP-014: Style Fidelity Vault

## Purpose / Big Picture

Preserve exact style evidence and produce deterministic analytical profiles only from
approved authorship spans.

## Scope

Immutable original vault, exact surface, authorship/exclusion review, advanced metrics,
register profiles, invariants, exemplars, coverage, comparison, and compatibility
projection to `StyleFingerprint`.

## Non-goals

Automatic authorship inference, output generation, detector optimization, and mutation
of immutable evidence.

## Context and Orientation

Follow SPEC-011, ADR-003, and the source/style packages from EP-013.

## Files to Read First

Authority stack, SPEC-011, ADR-003, style domain/application/store code, existing
`style.py` and tests, security/privacy docs, and blueprint style sections.

## Files to Change

Style domain/application/store/CLI modules, encryption boundary if already available,
fixtures/tests, docs, and this plan.

## Interfaces and Contracts

`StyleEvidencePackage` separates original, exact surface, analysis, authorship,
exemplars, invariants, and coverage. Only approved authentic/user-revision spans enter
the default profile.

## Milestones

### M1 - Evidence and authorship model

Goal: add immutable/exact/authorship contracts. Validation: `sh scripts/test-unit.sh`.
Expected: unit tests pass. Recovery: keep unresolved spans review-required.

### M2 - Metrics and coverage

Goal: add deterministic metrics, invariants, exemplars, and comparison. Validation:
`sh scripts/test-integration.sh`. Expected: round trips and coverage tests pass.

### M3 - Review CLI and compatibility

Goal: expose style review/profile/coverage/invariants and deterministic legacy projection.
Validation: `sh scripts/test-e2e.sh`. Expected: E2E tests pass. Recovery: preserve
`StyleFingerprint` behavior.

### M4 - Boundary

Goal: full validation and handoff. Validation: `sh scripts/verify.sh`. Expected:
`verify: ok`. Recovery: bounded retry with evidence.

## Concrete Steps

Implement milestones in order, document coverage limitations, and write state last.

## Validation and Acceptance

Exact supported evidence is preserved; complete status is never claimed with unresolved
authorship/coverage; style facts never enter project facts; profile replay is stable.

## Idempotence and Recovery

Use immutable artifact ids and versioned rulesets. Never run legacy scrub over the vault.

## Progress

- [ ] M1
- [ ] M2
- [ ] M3
- [ ] M4

## Surprises & Discoveries

Record metric coverage and sample-sufficiency findings.

## Decision Log

Record profile, storage, dependency, and compatibility decisions.

## Outcomes & Retrospective

Complete at the boundary with evidence coverage and residual-risk status.
