---
id: EP-010
title: Production Readiness
status: not_started
owner: agent
created: 2026-07-05
updated: 2026-07-05
---

# EP-010: Production Readiness

## Purpose / Big Picture

Bring Human Hand to production readiness by running final verification, security/privacy/performance/accessibility/observability reviews, deployment dry run, rollback drill, documentation review, launch checklist, and final gate documentation.

## Scope

- Full verification.
- Production-readiness check.
- Security and dependency audit review.
- Privacy/no-text review.
- Performance smoke review.
- CLI accessibility review.
- Observability/health review.
- Wheel build/install dry run.
- Rollback drill documentation.
- Final launch gate report.

## Non-goals

- Publishing to PyPI.
- Creating release tag.
- Hosted deployment.
- Adding new features.
- Broad refactors.

## Context and Orientation

EP-000 through EP-009 must be complete. This plan verifies readiness and documents launch status. It may fix small gaps discovered by checks, but should not add product scope.

## Files to Read First

- `PRODUCTION_READINESS.md`
- `RELEASE.md`
- `ROLLBACK.md`
- `DEPLOYMENT.md`
- `OPERATIONS.md`
- `SECURITY.md`
- `OBSERVABILITY.md`
- All specs under `.agent/specs/`
- `COMMANDS.md`
- Active test and CI files

## Files to Change

Expected files:

- `PRODUCTION_READINESS.md`
- `README.md`
- `CHANGELOG.md`
- `RELEASE.md`
- `ROLLBACK.md`
- `DEPLOYMENT.md`
- `OPERATIONS.md`
- `OBSERVABILITY.md`
- `SECURITY.md` if review findings require updates.
- `scripts/production-readiness-check.sh`
- `scripts/loop.sh`
- Tests/source only for small readiness defects discovered by validation.
- `.agent/execplans/EP-010-production-readiness.md`
- `.agent/state/last-result.env`

## Interfaces and Contracts

- `sh scripts/verify.sh` must pass.
- `sh scripts/production-readiness-check.sh` must pass.
- `sh scripts/loop.sh` must print `build: complete`.
- Final report records launch gate result and remaining risks.

## Milestones

### M1 — Full verification baseline

- Goal: Establish all local checks pass before readiness review.
- Files to read: `COMMANDS.md`, scripts, failing outputs if any.
- Files to change: only files needed for small validation fixes and this ExecPlan.
- Exact edits expected: Run verify; fix any small in-scope failures; document failures and fixes.
- Validation command: `sh scripts/verify.sh`
- Expected result: `verify: ok`
- Recovery: Use bounded retry. On third same-root validation failure, change approach or STOP with evidence.

### M2 — Security and privacy review

- Goal: Prove no secrets/user text leaks and security controls pass.
- Files to read: `SECURITY.md`, `TESTING.md`, tests, logs/cache tests.
- Files to change: docs/tests/source only for small findings.
- Exact edits expected: Run security and audit commands; inspect secret scan; verify no text cache/log tests; update docs for accepted findings.
- Validation command: `sh scripts/security-check.sh`
- Expected result: `security check: ok`
- Recovery: If dependency audit separately fails, run `sh scripts/dependency-audit.sh`; fix or record accepted finding with maintainer action needed.

### M3 — Performance, accessibility, and observability review

- Goal: Confirm CLI performance/UX/logging readiness.
- Files to read: `PRODUCTION_READINESS.md`, `OBSERVABILITY.md`, `SPEC-004`, `SPEC-007`.
- Files to change: docs/tests/source for small findings.
- Exact edits expected: Verify smoke under 30 seconds, JSON/no-color tests, help/version target where practical, health/log/counter behavior.
- Validation command: `sh scripts/smoke-test.sh`
- Expected result: `smoke test: ok`
- Recovery: If timing is flaky, use measured evidence and avoid broad optimization; document remaining risk if target cannot be machine-enforced.

### M4 — Deployment dry run and rollback drill

- Goal: Prove artifact build/install and rollback path.
- Files to read: `DEPLOYMENT.md`, `RELEASE.md`, `ROLLBACK.md`.
- Files to change: docs and scripts if gaps found.
- Exact edits expected: Build artifacts, document clean install smoke, document previous-wheel reinstall/config/cache rollback drill; no publish/tag.
- Validation command: `sh scripts/build.sh`
- Expected result: `build: ok`
- Recovery: If clean install cannot be performed locally, record exact blocker and recommended default; do not publish.

### M5 — Production readiness gate

- Goal: Run final readiness command and set loop status.
- Files to read: `scripts/production-readiness-check.sh`, `scripts/loop.sh`, `PRODUCTION_READINESS.md`.
- Files to change: `scripts/production-readiness-check.sh`, `scripts/loop.sh`, docs, this ExecPlan.
- Exact edits expected: Ensure readiness script checks verify/build/smoke/docs and prints success; ensure loop prints `build: complete` only when readiness passes.
- Validation command: `sh scripts/production-readiness-check.sh`
- Expected result: `production readiness: ok`
- Recovery: Do not make readiness script pass by skipping required checks. Fix underlying issues or STOP.

### M6 — Final diff and launch report

- Goal: Complete final review and record launch status.
- Files to read: all changed files.
- Files to change: this ExecPlan, `.agent/state/last-result.env`.
- Exact edits expected: Run diff review; update Outcomes & Retrospective with launch gate, remaining risks, approvals status; write final env file.
- Validation command: `sh scripts/loop.sh`
- Expected result: `build: complete`
- Recovery: If loop fails, inspect readiness script output; fix only readiness gate issues.

## Concrete Steps

1. Run preflight.
2. Confirm EP-000 through EP-009 complete.
3. Complete M1-M6 in order.
4. Do not publish or tag.
5. Run `git diff --name-only`.
6. Write `.agent/state/last-result.env` last.

## Validation and Acceptance

- `sh scripts/verify.sh` passes.
- `sh scripts/security-check.sh` passes.
- `sh scripts/dependency-audit.sh` passes or accepted findings documented.
- `sh scripts/smoke-test.sh` passes.
- `sh scripts/build.sh` passes.
- `sh scripts/production-readiness-check.sh` passes.
- `sh scripts/loop.sh` prints `build: complete`.
- Launch gate report complete.
- No publish/tag/deployment performed.

## Idempotence and Recovery

Production readiness checks can be rerun. Do not weaken readiness scripts. If a check cannot be run due environment limitation, document exact limitation and STOP unless spec allows manual evidence.

## Progress

- [ ] M1 — Full verification baseline.
- [ ] M2 — Security and privacy review.
- [ ] M3 — Performance, accessibility, and observability review.
- [ ] M4 — Deployment dry run and rollback drill.
- [ ] M5 — Production readiness gate.
- [ ] M6 — Final diff and launch report.

## Surprises & Discoveries

- None yet.

## Decision Log

- 2026-07-05: Production readiness does not equal publish. Reason: release/publish requires maintainer approval. Consequence: this plan can verify artifacts but must not tag or publish.

## Outcomes & Retrospective

Not started.
