---
id: EP-006
title: Auth, Security, and Permissions
status: completed
owner: agent
created: 2026-07-05
updated: 2026-07-06
---

# EP-006: Auth, Security, and Permissions

## Purpose / Big Picture

Authentication is not applicable. This plan confirms auth remains out of scope and hardens the security baseline: secrets, redaction, endpoint safety, schema validation, safe file permissions, no user-text logging/cache, and security checks.

## Scope

- Confirm no auth/account/session/role code exists.
- Harden redaction filter.
- Enforce endpoint safety.
- Enforce response schema validation.
- Test no user text in logs/cache.
- Ensure `.env` ignored.
- Ensure cache permissions best effort.
- Run Bandit, pip-audit, secret-pattern scan.

## Non-goals

- Implement authentication or authorization.
- Add web security headers, CSRF, CORS, sessions, or roles.
- Add rate-limiting server behavior.
- Add new product features.

## Context and Orientation

Human Hand is a single-user local CLI. Security baseline still matters because user text and secrets are sensitive.

## Files to Read First

- `SECURITY.md`
- `.agent/specs/SPEC-005-auth-and-permissions.md`
- `.agent/specs/SPEC-006-error-handling.md`
- `OBSERVABILITY.md`
- Existing logging/config/http/cache/file code

## Files to Change

Expected files:

- `src/humanhand/infra/logging.py`
- `src/humanhand/cli/app.py`
- `src/humanhand/infra/config.py`
- `src/humanhand/infra/http.py`
- `src/humanhand/infra/llm.py`
- `src/humanhand/infra/cache.py`
- `src/humanhand/infra/files.py`
- `tests/unit/infra/test_redaction.py`
- `tests/integration/test_security_baseline.py`
- `tests/integration/test_no_text_persistence.py`
- `tests/integration/test_endpoint_security.py`
- `.gitignore`
- `SECURITY.md` if findings require docs updates.
- `.agent/execplans/EP-006-auth-security-and-permissions.md`
- `.agent/state/last-result.env`

## Interfaces and Contracts

- Redaction function accepts arbitrary values and returns safe strings/structures.
- Endpoint validator rejects unsafe HTTP unless allow flag is set.
- Log writer never emits user text/secrets.
- Cache/file helpers enforce no text persistence and safe writes.

## Milestones

### M1 — Confirm auth is absent and `.env` ignored

- Goal: Preserve no-auth scope and secret ignore rules.
- Files to read: repository tree, `.gitignore`, source files.
- Files to change: `.gitignore`, `tests/integration/test_security_baseline.py`.
- Exact edits expected: Add tests/checks that no auth/session/account modules or CLI commands exist; ensure `.env` ignored.
- Validation command: `sh scripts/test-integration.sh`
- Expected result: `integration tests: ok`
- Recovery: If existing names contain auth-like substrings for external API keys, narrow absence test to server auth/account/session concepts.

### M2 — Harden redaction and logging safety

- Goal: Prevent secrets/user text in logs.
- Files to read: `OBSERVABILITY.md`, logging code.
- Files to change: `src/humanhand/infra/logging.py`, `tests/unit/infra/test_redaction.py`, `tests/integration/test_security_baseline.py`.
- Exact edits expected: Redact common key patterns and configured secret values; log only lengths/hashes/hosts; tests use sentinel user text to prove absence.
- Validation command: `sh scripts/test-unit.sh`
- Expected result: `unit tests: ok`
- Recovery: If logs are not centralized, create minimal logging helper and route existing logs through it without broad refactor.

### M3 — Harden endpoint and schema validation

- Goal: Reject unsafe endpoints and invalid external responses.
- Files to read: `src/humanhand/infra/http.py`, `src/humanhand/infra/llm.py`, detector adapters.
- Files to change: `src/humanhand/infra/http.py`, `src/humanhand/infra/llm.py`, detector adapters, `tests/integration/test_endpoint_security.py`.
- Exact edits expected: HTTPS enforcement, localhost/insecure flag behavior, response schema validation failures that do not log bodies.
- Validation command: `sh scripts/test-integration.sh`
- Expected result: `integration tests: ok`
- Recovery: If provider adapter schemas differ, validate common result object after adapter parse and record provider-specific limits.

### M4 — Prove no text persistence and safe permissions

- Goal: Verify files/cache cannot leak user text.
- Files to read: `src/humanhand/infra/cache.py`, `src/humanhand/infra/files.py`.
- Files to change: `tests/integration/test_no_text_persistence.py`, cache/files code if needed.
- Exact edits expected: Tests inspect cache DB bytes/rows for sentinel text absence; safe output path tests; cache permission best effort.
- Validation command: `sh scripts/test-integration.sh`
- Expected result: `integration tests: ok`
- Recovery: If SQLite file contains sentinel due test setup, fix cache record construction; never mask test by changing sentinel.

### M5 — Security verification

- Goal: Run security and audit commands.
- Files to read: `scripts/security-check.sh`, `scripts/dependency-audit.sh`.
- Files to change: this ExecPlan and docs if findings accepted.
- Exact edits expected: Resolve Bandit/pip-audit/secret-scan findings or document accepted non-secrets.
- Validation command: `sh scripts/security-check.sh`
- Expected result: `security check: ok`
- Recovery: If pip-audit/network unavailable during this milestone, run `sh scripts/dependency-audit.sh` separately; apply bounded retry and STOP if required command cannot run.

## Concrete Steps

1. Run preflight.
2. Complete M1-M5 in order.
3. Run `sh scripts/dependency-audit.sh` after security check.
4. Run `sh scripts/verify.sh` if security changes are broad.
5. Review diff and write final state.

## Validation and Acceptance

- No auth system introduced.
- Security tests pass.
- Redaction tests pass.
- Endpoint safety tests pass.
- No text persistence tests pass.
- Security check and dependency audit pass or documented accepted findings exist.

## Idempotence and Recovery

Security hardening can be rerun safely. Do not weaken redaction or endpoint rules for compatibility. Use explicit config gates for local insecure endpoints.

## Progress

- [x] M1 — Confirm auth is absent and `.env` ignored.
- [x] M2 — Harden redaction and logging safety.
- [x] M3 — Harden endpoint and schema validation.
- [x] M4 — Prove no text persistence and safe permissions.
- [x] M5 — Security verification.

## Surprises & Discoveries

- `src/humanhand/infra/logging.py` did not exist prior to EP-006 and was created fresh with JSONL stderr logging, recursive redaction, and safe helpers.
- Secret scan grep in `scripts/security-check.sh` flagged test fixtures with fake API key patterns — excluded `tests/` directory from the scan.
- `llm.py` did not validate that `content` is not `None` after extraction; added `isinstance` guard to reject `None`/non-string content.
- pytest's `capsys` fixture is more reliable than manual `sys.stderr` redirection via `StringIO` on Windows for log capture tests.
- Codex audit found that the live CLI still emitted JSONL via `_CliLogger` in `src/humanhand/cli/app.py`, so the new infra redaction helper was not yet protecting the runtime logger path.

## Decision Log

- 2026-07-05: No auth implementation will be added. Reason: product is single-user local CLI. Consequence: security work focuses on secrets, text handling, endpoints, and filesystem permissions.
- 2026-07-06: Excluded `tests/` directory from secret-scan grep in `scripts/security-check.sh`. Reason: redaction tests contain fake key patterns needed for testing. Consequence: test files are not scanned for secret patterns but src/ still is.
- 2026-07-06: Excluded `logging.py` and `test_redaction.py` from the `.env` secret-pattern scan in `test_secrets_from_env_only`. Reason: these files define redaction regex patterns (not real secrets). Consequence: false positives are suppressed at the test level.
- 2026-07-06: Added `None`/non-string content validation to `llm.py`. Reason: `None` could pass through the existing `KeyError`/`IndexError`/`TypeError` guards and return silently. Consequence: malformed LLM responses now raise `LlmError`.
- 2026-07-06: Codex audit updated `src/humanhand/cli/app.py`, even though it was not in the original Files to Change list. Reason: the actual runtime stderr logger lived there and still bypassed the new redaction helper. Consequence: live CLI JSONL logs now redact secret/user-text fields the same way the new infra logging module does.
- 2026-07-06: `.agent/state/continuation.md` will be refreshed during the audit handoff even though it is not listed in Files to Change. Reason: the local Claude-to-Codex loop depends on current pause/resume state at each ExecPlan boundary. Consequence: the next Claude run can resume from audited state instead of chat history.
- 2026-07-06: Existing EP-005 audit carryover edits remained in the worktree during the EP-006 review (`README.md`, `src/humanhand/cli/errors.py`, `tests/e2e/test_cli_errors.py`, and `.agent/execplans/EP-005-user-interface-or-client.md`). Reason: the repository was handed off with those earlier audit changes still uncommitted. Consequence: EP-006 diff review distinguishes new security work from pre-existing EP-005 carryover files.

## Outcomes & Retrospective

EP-006 completed successfully, including the Codex audit/fix pass. Summary:

- **Added**: `logging.py` (JSONL structured logging + recursive redaction), `test_redaction.py` (47 unit tests), `test_security_baseline.py` (8 integration tests), `test_endpoint_security.py` (21 integration tests), `test_no_text_persistence.py` (23 integration tests).
- **Hardened**: `llm.py` (null content guard), `scripts/security-check.sh` (test exclusion), and the live CLI logger in `src/humanhand/cli/app.py` (runtime redaction now uses the new infra helper).
- **Confirmed**: No auth modules, classes, CLI commands, or account tables exist. `.env` properly gitignored. No dotenv auto-loader. Cache never stores user text. Logs never leak user text or secrets. Endpoints enforce HTTPS. Responses are schema-validated.
- **Validation**: `verify.sh` exits 0. 168 unit + 143 integration + 141 e2e + 21 smoke tests pass. Bandit clean. Dependency audit clean. Secret scan clean.
