---
id: EP-008
title: Observability and Operations
status: not_started
owner: agent
created: 2026-07-05
updated: 2026-07-07
---

# EP-008: Observability and Operations

## Purpose / Big Picture

Add local observability and operational readiness: structured JSONL logs, redaction, local counters, health command completion, operational runbooks, and tests proving no telemetry or text leakage.

## Scope

- Structured JSONL logger to stderr.
- Required log fields.
- Redaction filter integration.
- Local counters emitted at command end.
- Health command with config/cache/platform checks and no network by default.
- Operations docs/runbooks updates.
- Observability tests.

## Non-goals

- Remote metrics, dashboards, traces, alerts, OpenTelemetry exporters, hosted uptime checks.
- New product features.
- Changing CLI contracts except observability output on stderr.

## Context and Orientation

EP-007 should provide strong tests. This plan completes observability behavior required for production readiness.

## Files to Read First

- `OBSERVABILITY.md`
- `.agent/specs/SPEC-007-observability.md`
- `OPERATIONS.md`
- `src/humanhand/infra/logging.py`
- `src/humanhand/cli/app.py`
- Existing observability/security tests

## Files to Change

Expected files:

- `src/humanhand/infra/logging.py`
- `src/humanhand/infra/metrics.py` or `counters.py` if needed.
- `src/humanhand/infra/config.py`
- `src/humanhand/application/services.py`
- `src/humanhand/cli/app.py`
- `src/humanhand/cli/output.py`
- `tests/unit/infra/test_logging.py`
- `tests/integration/test_observability.py`
- `tests/e2e/test_health_command.py`
- `OBSERVABILITY.md`
- `OPERATIONS.md`
- `.agent/execplans/EP-008-observability-and-operations.md`
- `.agent/state/last-result.env`

## Interfaces and Contracts

- Logger emits JSONL dictionaries to stderr.
- Required fields from SPEC-007.
- Counter collector is command-scoped.
- Health command returns JSON-safe diagnostics without network or secrets.

## Milestones

### M1 — Implement structured logging fields

- Goal: Emit parseable JSONL logs with required fields.
- Files to read: `SPEC-007`, existing logging code.
- Files to change: `src/humanhand/infra/logging.py`, `tests/unit/infra/test_logging.py`.
- Exact edits expected: JSON serialization, field normalization, timestamp, event/level/message, lengths/hash prefixes, endpoint host, attempt/retry/cache fields.
- Validation command: `sh scripts/test-unit.sh`
- Expected result: `unit tests: ok`
- Recovery: If log field availability varies, allow null for unavailable fields and document rule.

### M2 — Integrate redaction and no-text log tests

- Goal: Prove logs contain no text/secrets.
- Files to read: `SECURITY.md`, redaction tests.
- Files to change: `src/humanhand/infra/logging.py`, `tests/integration/test_observability.py`.
- Exact edits expected: Route command/external/cache events through logger; tests use sentinel source/style/output/secrets and assert absence in stderr.
- Validation command: `sh scripts/test-integration.sh`
- Expected result: `integration tests: ok`
- Recovery: If CLI writes non-JSON status lines, decide whether status is separate from logs; document and test both without user text.

### M3 — Add local counters

- Goal: Emit end-of-run counters without telemetry.
- Files to read: `OBSERVABILITY.md`.
- Files to change: counter module if needed, application/CLI wiring, tests.
- Exact edits expected: Command-scoped counters for attempts, retries, cache hits/misses, durations, lengths; stderr only.
- Validation command: `sh scripts/test-integration.sh`
- Expected result: `integration tests: ok`
- Recovery: If counters complicate service signatures, inject a lightweight collector with default no-op behavior.

### M4 — Complete health command and docs

- Goal: Provide local health diagnostics and operational docs.
- Files to read: `OPERATIONS.md`, `ENVIRONMENT.md`.
- Files to change: `src/humanhand/application/services.py`, `src/humanhand/cli/app.py`, `tests/e2e/test_health_command.py`, `OPERATIONS.md`, `OBSERVABILITY.md`.
- Exact edits expected: Health reports version, Python/platform, config shape, cache path writable, endpoint URL shape, provider config presence, no network/secrets.
- Validation command: `sh scripts/test-e2e.sh`
- Expected result: `e2e tests: ok`
- Recovery: If platform checks are OS-dependent, assert stable keys and types rather than exact values.

### M5 — Observability full verification

- Goal: Verify observability and operations are production-ready.
- Files to read: changed tests/docs.
- Files to change: this ExecPlan only unless fixes needed.
- Exact edits expected: Update Progress/Decision Log.
- Validation command: `sh scripts/verify.sh`
- Expected result: `verify: ok`
- Recovery: Use bounded retry; do not add remote telemetry to satisfy observability.

## Concrete Steps

1. Run preflight.
2. Implement logging, redaction, counters, health, docs in order.
3. Keep stdout/stderr contracts intact.
4. Run full verify.
5. Write final state file.

## Validation and Acceptance

- JSONL logs parse.
- Required fields present or null by rule.
- No user text/secrets in logs/counters.
- Health command works offline.
- Operations docs updated.
- Full verify passes.

## Idempotence and Recovery

Logging integration can be rerun safely. If duplicate events appear, centralize emission at application boundaries; do not remove required fields.

## Progress

- [x] M1 — Implement structured logging fields.
- [x] M2 — Integrate redaction and no-text log tests.
- [x] M3 — Add local counters.
- [x] M4 — Complete health command and docs.
- [x] M5 — Observability full verification.

## Surprises & Discoveries

- Much of EP-008 was already partially implemented by EP-006 (logging.py with JSONL, redaction, safe helpers) and the Codex audit (logger wired through CLI).
- OPERATIONS.md and OBSERVABILITY.md were already complete from the blueprint phase; only minor clarifications needed.
- Health command already existed but lacked `cache_dir_writable` and `endpoint_url_valid` fields required by OPERATIONS.md.
- Local counters were entirely absent before EP-008 and created from scratch with a whitelist-validated `Counters` class.
- The three ultracode agents collectively added 138 tests across counters, health e2e, logging fields, and observability integration.
- The original EP-008 validation suite still passed even though `command.counters` events were not actually emitted by CLI command paths; the Codex audit exposed that gap and added runtime plus regression coverage for it.
- Emitting counter events on every exit regressed the existing stderr error-tail contract, so the audit kept counter emission on successful command completions only.

## Decision Log

- 2026-07-05: Observability is local-only. Reason: product forbids telemetry. Consequence: no dashboards/traces/exporters are implemented.
- 2026-07-07: Counter names are validated against a whitelist of 9 allowed names from OBSERVABILITY.md. Reason: prevents accidental text leakage through unknown counter names. Consequence: unknown counter names raise ValueError.
- 2026-07-07: Health command `cache_dir_writable` is None when cache is disabled. Reason: distinguishes "not writable" from "not applicable." Consequence: consumers must handle tri-state boolean.
- 2026-07-07: Health command `endpoint_url_valid` uses syntactic URL parsing only. Reason: health must not make network calls. Consequence: only checks URL shape, not connectivity.
- 2026-07-07: CLI emits `command.counters` only after successful command completion. Reason: preserves the existing stderr error-tail contract while still satisfying EP-008 counter emission for completed runs. Consequence: failed commands do not emit counter events.
- 2026-07-07: `verify.start` logs `input_length` from the real file-read path. Reason: counter events should reflect the analyzed character count even on Windows newline normalization. Consequence: verify counter assertions and runtime telemetry stay aligned.
- 2026-07-07: Updated `.agent/state/continuation.md` in addition to planned files. Reason: AGENTS.md defines it as the optional pause handoff note for the Claude/Codex loop. Consequence: the next Claude prompt can stay small and cache-stable without relying on chat history.

## Outcomes & Retrospective

EP-008 completed successfully. Summary:

- **Added**: `counters.py` (whitelist-validated counter collector), `test_counters.py` (28 tests), `test_logging.py` (33 tests), `test_observability.py` (39 tests), `test_health_command.py` (38 tests).
- **Hardened**: Health command now reports `cache_dir_writable` and `endpoint_url_valid` per OPERATIONS.md.
- **Audit fix**: CLI command paths now emit `command.counters` JSONL events on successful completion, and observability integration coverage now proves health, scrub, and verify cache hit/miss counter behavior.
- **Confirmed**: JSONL logs parse, required fields present, no user text/secrets in logs/counters, health works offline, no telemetry imports exist.
- **Validation**: `verify.sh` exits 0. 765 tests passing (2 skipped). Coverage 95.12% enforced against 85% threshold.
