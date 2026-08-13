---
id: EP-015
title: Fact Integrity V2, Project Brain, and Context Broker
status: planned
owner: claude
created: 2026-08-12
updated: 2026-08-12
---

# EP-015: Fact Integrity V2, Project Brain, and Context Broker

## Purpose / Big Picture

Add protected facts, claims, entities, source evidence, local project state, revisions,
approvals, and deterministic context capsules without semantic embeddings or a model.

## Scope

Fact Integrity V2 contracts, project directory layout, schema/migrations, encrypted
fields, optimistic revisions, context broker, and optional Obsidian projection.

## Non-goals

Hidden global history, cloud sync, embeddings, SLM context injection, or style-fact
promotion into project facts.

## Context and Orientation

Follow SPEC-012, ADR-001, ADR-005, source packages from EP-013, and the style profile
from EP-014.

## Files to Read First

Authority stack, SPEC-012, ADR-001/005, current facts/cache/files/config modules, project
docs, and blueprint project/context sections.

## Files to Change

Fact/project/context domain/application/store/CLI modules, SQL schemas/migrations,
Obsidian projection, tests/fixtures, docs, and this plan.

## Interfaces and Contracts

Claims have modality, negation, attribution, evidence, status, and coverage. Stale
revision tokens cannot overwrite accepted state. Capsules are deterministic and inspectable.

## Milestones

### M1 - Protected fact and project contracts

Goal: add V2 types, local layout, and revision semantics. Validation: `sh scripts/test-unit.sh`.
Expected: unit tests pass. Recovery: preserve existing fact facade.

### M2 - Store and migrations

Goal: add versioned local schema, rollback, and encrypted-field ports. Validation:
`sh scripts/test-integration.sh`. Expected: migration/store tests pass. Recovery: use a
disposable selected project directory and record environment blockers.

### M3 - Context and Obsidian projection

Goal: add deterministic capsules and explicit user-triggered projection. Validation:
`sh scripts/test-e2e.sh`. Expected: E2E tests pass. Recovery: projection remains optional
and non-authoritative.

### M4 - Boundary

Goal: full validation and handoff. Validation: `sh scripts/verify.sh`. Expected:
`verify: ok`. Recovery: stop on the third same-root blocker.

## Concrete Steps

Implement M1-M4 in order, update migration/docs evidence, review untracked files, and
write state last.

## Validation and Acceptance

Protected facts survive changes, unknown coverage is explicit, stale writes fail,
migrations are safe, capsules are deterministic, and Obsidian output omits private ids.

## Idempotence and Recovery

Migrations are versioned and rollbackable. Never delete user project data; use disposable
test directories and documented retention behavior.

## Progress

- [ ] M1
- [ ] M2
- [ ] M3
- [ ] M4

## Surprises & Discoveries

Record schema, encryption, and environment findings.

## Decision Log

Record storage, migration, key-provider, and projection decisions.

## Outcomes & Retrospective

Complete at the boundary with migration evidence and remaining risks.
