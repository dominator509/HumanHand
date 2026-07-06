---
id: EP-007
title: Testing Hardening
status: not_started
owner: agent
created: 2026-07-05
updated: 2026-07-05
---

# EP-007: Testing Hardening

## Purpose / Big Picture

Harden test coverage, reliability, regressions, CI validation, gated live E2E behavior, smoke/performance checks, and coverage thresholds so `sh scripts/verify.sh` is a trustworthy quality gate.

## Scope

- Unit/integration/E2E coverage review.
- Regression tests for critical flows.
- Failure-mode tests.
- Coverage threshold at or above 85%.
- Flaky test policy.
- CI matrix for Windows and Ubuntu.
- Gated live E2E tests.
- Smoke duration under 30 seconds.

## Non-goals

- New product features.
- Live network by default.
- Broad refactors.
- Performance benchmarking beyond required smoke/threshold checks.

## Context and Orientation

EP-001 through EP-006 should be complete. This plan improves confidence without changing product scope.

## Files to Read First

- `TESTING.md`
- `COMMANDS.md`
- `.github/workflows/ci.yml`
- Existing `tests/`
- Existing `pyproject.toml`
- `scripts/verify.sh`

## Files to Change

Expected files:

- `pyproject.toml`
- `.github/workflows/ci.yml`
- `tests/unit/`
- `tests/integration/`
- `tests/e2e/`
- `tests/smoke/`
- `tests/fixtures/` with synthetic text only.
- `scripts/test-e2e.sh` if marker gating needs correction.
- `scripts/verify.sh` if sequencing needs correction.
- `TESTING.md` if policy changes.
- `.agent/execplans/EP-007-testing-hardening.md`
- `.agent/state/last-result.env`

## Interfaces and Contracts

- `sh scripts/verify.sh` is the full local quality gate.
- Live tests skip unless `HUMANHAND_RUN_LIVE_E2E=1`.
- Coverage threshold is configured in pytest/coverage settings.
- Tests must not contain real user data or secrets.

## Milestones

### M1 — Audit test coverage and gaps

- Goal: Identify missing critical coverage.
- Files to read: `tests/`, `TESTING.md`, specs.
- Files to change: this ExecPlan Surprises & Discoveries, maybe `TESTING.md` if policy gap found.
- Exact edits expected: Record gap list for rewrite, verify, diff-facts, scrub, config, redaction, cache, endpoint, CLI JSON, errors.
- Validation command: `sh scripts/test-unit.sh`
- Expected result: `unit tests: ok`
- Recovery: If existing tests fail before changes, fix baseline only if within scope; otherwise STOP with evidence.

### M2 — Add regression and failure-mode tests

- Goal: Cover critical regressions and invalid inputs.
- Files to read: existing source/tests.
- Files to change: `tests/unit/`, `tests/integration/`, `tests/e2e/`, `tests/fixtures/`.
- Exact edits expected: Synthetic fixtures; tests for fact drift, scrub, UTF-8/BOM, unsafe path, no text logs/cache, retry, schema, CLI errors.
- Validation command: `sh scripts/test-unit.sh`
- Expected result: `unit tests: ok`
- Recovery: If fixture text resembles copyrighted/real data, replace with invented synthetic text.

### M3 — Harden integration and E2E gating

- Goal: Ensure no live calls by default and acceptance paths pass.
- Files to read: `scripts/test-e2e.sh`, pytest markers, CI workflow.
- Files to change: `pyproject.toml`, `tests/e2e/`, `tests/integration/`, `scripts/test-e2e.sh` if needed.
- Exact edits expected: Define markers `live`, `live_e2e`; skip live tests unless env set; mocked E2E paths remain default.
- Validation command: `sh scripts/test-e2e.sh`
- Expected result: `e2e tests: ok`
- Recovery: If marker selection skips all E2E tests, add non-live acceptance tests; do not enable live by default.

### M4 — Configure coverage and smoke performance

- Goal: Enforce coverage and smoke duration.
- Files to read: `pyproject.toml`, `tests/smoke/`, `scripts/smoke-test.sh`.
- Files to change: `pyproject.toml`, `tests/smoke/`, `scripts/smoke-test.sh` if needed.
- Exact edits expected: Set coverage >=85%; smoke asserts under 30 seconds on mocks; help/version performance check if practical.
- Validation command: `sh scripts/smoke-test.sh`
- Expected result: `smoke test: ok`
- Recovery: If timing is flaky, assert generous threshold only for complete smoke duration and record help/version timing as measured not hard fail unless stable.

### M5 — CI and full verify hardening

- Goal: Make CI run the same validation gates on Windows/Ubuntu.
- Files to read: `.github/workflows/ci.yml`, `COMMANDS.md`.
- Files to change: `.github/workflows/ci.yml`, `scripts/verify.sh` if sequencing stale.
- Exact edits expected: Matrix for Windows and Ubuntu, Python 3.11, uv install/cache, run install and verify; no live env vars by default.
- Validation command: `sh scripts/verify.sh`
- Expected result: `verify: ok`
- Recovery: If local OS cannot validate Windows path behavior, rely on pathlib tests and record CI matrix as final verifier.

## Concrete Steps

1. Run preflight.
2. Audit gaps.
3. Add tests before code fixes where possible.
4. Fix implementation only when tests expose real gaps within scope.
5. Run full verify and diff review.
6. Write last-result file last.

## Validation and Acceptance

- Coverage >=85%.
- Unit/integration/E2E/smoke tests pass.
- Live tests gated and skipped by default.
- CI matrix exists and runs verify.
- Smoke under 30 seconds.
- `sh scripts/verify.sh` passes.

## Idempotence and Recovery

Adding tests is safe to rerun. If tests reveal bugs outside this plan, fix only critical correctness/security issues needed for the tests; otherwise document and STOP if scope would expand.

## Progress

- [ ] M1 — Audit test coverage and gaps.
- [ ] M2 — Add regression and failure-mode tests.
- [ ] M3 — Harden integration and E2E gating.
- [ ] M4 — Configure coverage and smoke performance.
- [ ] M5 — CI and full verify hardening.

## Surprises & Discoveries

- None yet.

## Decision Log

- 2026-07-05: Coverage target set at >=85%. Reason: production-readiness input. Consequence: scripts/CI must fail below threshold after this plan.

## Outcomes & Retrospective

Not started.
