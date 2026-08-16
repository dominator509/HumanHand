---
id: EP-019
title: Pre-SLM Integration, Migration, and Readiness
status: completed
owner: codex
created: 2026-08-12
updated: 2026-08-15
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

- [x] M1
- [x] M2
- [x] M3
- [x] M4

## Surprises & Discoveries

- A fresh worktree initially had only runtime dependencies, so the first pre-SLM E2E
  invocation fell through to a global pytest and could not import `humanhand`. Running
  the documented `sh scripts/install.sh` restored the locked development environment;
  the rerun passed 399 tests with 12 intentional skips.
- The integrated lifecycle fixture used the valid month-first date
  `August 30, 2026`, but the deterministic source-evidence grammar recognized only ISO,
  numeric, and day-first month-name dates. The missing span also hid a second defect:
  accepted length-changing lexical edits persisted stale protected-span offsets.
- The final loop exposed a Ruff lint/format expression-shape conflict. Naming the slice
  kept both checks enabled and made the source stable under both tools.

## Decision Log

- Extended the existing deterministic date grammar for month-first English dates rather
  than adding a parser dependency or changing the public evidence contract.
- Rebased protected-span offsets from accepted lexical changes before persistence,
  failed closed on overlap or text mismatch, and saved the spans in the same transaction
  as revision content and approval.
- Retained `.github/workflows/ep019-format.yml`: its target branch still exists on the
  remote, so it is live branch-specific automation rather than orphaned configuration.
- Limited the audit fix to the integration service, evidence extractor, their regression
  tests, and this required ExecPlan record; no SLM, release, publish, or deployment work
  was authorized.

## Outcomes & Retrospective

Completed the Codex audit/fix boundary with six end-to-end debug passes. The final
post-fix pre-SLM suite passed 399 tests with 12 intentional skips, and the canonical
`sh scripts/loop.sh` boundary completed the full verifier, wheel build, isolated install,
and installed CLI checks with `build: complete`. The five legacy CLI commands remain
available, live/external calls remain gated, and work stops here before EP-020 or any SLM
implementation.
