---
id: EP-019
title: Pre-SLM Integration, Migration, and Readiness
status: planned
owner: claude
created: 2026-08-12
updated: 2026-08-12
---

# EP-019: Pre-SLM Integration and Readiness

## Purpose / Big Picture

Integrate the complete deterministic Pre-SLM workflow, preserve backward compatibility,
and produce an honest local production-readiness gate.

## Scope

Clean source/style import, authorship approval, style evidence, facts/project state,
context preview, existing rewrite compatibility, lexical review, public export/audit,
Beacon reporting, migrations, docs, packaging, scripts, CI, rollback, and readiness.

## Non-goals

Any SLM, training/runtime code, model download, automatic publication, release tag,
hosted deployment, or license selection.

## Context and Orientation

All prior pre-SLM plans must be complete and audited. Follow SPEC-009 through SPEC-017,
all ADRs, and `SLM_HANDOFF_CONTRACT.md`.

## Files to Read First

Authority stack, all pre-SLM specs/ADRs/plans, current production-readiness/release/
rollback docs, scripts, CI, packaging, and compatibility tests.

## Files to Change

Integration services/CLI, migrations, all required validation scripts, CI, packaging,
docs, smoke/integration/E2E tests, readiness report, and this plan.

## Interfaces and Contracts

Every stage is deterministic or human-approved; public artifacts are independently
audited; old commands remain functional; the readiness report cannot hide blocked gates.

## Milestones

### M1 - End-to-end deterministic workflow

Goal: wire import through review/export/audit while preserving old commands. Validation:
`sh scripts/test-pre-slm-e2e.sh`. Expected: `pre-SLM e2e tests: ok`. Recovery: isolate
the failing boundary and keep legacy flow available.

### M2 - Validation and packaging

Goal: register focused scripts, CI, wheel/smoke/security/dependency gates. Validation:
`sh scripts/verify.sh`. Expected: `verify: ok`. Recovery: use the repository anti-fixation
rule and keep live gates explicit.

### M3 - Production readiness

Goal: complete readiness, rollback, and release evidence. Validation:
`sh scripts/production-readiness-check.sh`. Expected: `production readiness: ok`.
Recovery: document maintainer/external blockers; never fake-green.

### M4 - Final boundary

Goal: verify loop, diff/status, and forbidden-path policy. Validation: `sh scripts/loop.sh`.
Expected: `build: complete`. Recovery: stop before any publish/tag/deploy action.

## Concrete Steps

Implement stages in order, update every linked doc/spec, run each required command,
review tracked and untracked changes, and write state last.

## Validation and Acceptance

All pre-SLM acceptance gates pass; old commands remain available; no private text leaks;
public artifacts audit clean; live calls remain gated; no forbidden SLM path exists.

## Idempotence and Recovery

Migrations and exports are rollbackable. Use disposable fixtures/projects, never delete
user data, and keep release/publish actions explicitly outside this plan.

## Progress

- [ ] M1
- [ ] M2
- [ ] M3
- [ ] M4

## Surprises & Discoveries

Record final compatibility, packaging, CI, and external-gate evidence.

## Decision Log

Record integration, migration, dependency, release, and risk-acceptance decisions.

## Outcomes & Retrospective

Complete only when the readiness report is honest, all prior plans are audited, and the
repository is explicitly stopped before SLM work.
