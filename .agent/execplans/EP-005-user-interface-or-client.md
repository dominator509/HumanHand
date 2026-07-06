---
id: EP-005
title: User Interface or Client
status: not_started
owner: agent
created: 2026-07-05
updated: 2026-07-05
---

# EP-005: User Interface or Client

## Purpose / Big Picture

Not applicable as GUI/web UI. Human Hand's user interaction layer is the CLI client. This plan polishes CLI UX, machine-friendly output, accessibility, empty/error states, status messages, and no-color behavior.

## Scope

- CLI result rendering.
- JSON-only stdout mode.
- No-color and Windows color behavior.
- Empty input and common error messages.
- Status/progress messages to stderr without user text.
- Help text and docs alignment.
- E2E/acceptance tests.

## Non-goals

- GUI, web UI, TUI, streaming UI, spinners.
- New core rewrite behavior.
- New detector providers.
- Auth or accounts.

## Context and Orientation

EP-004 command contracts exist. This plan refines user-visible behavior without changing underlying domain guarantees.

## Files to Read First

- `.agent/specs/SPEC-004-ui-ux-behavior.md`
- `.agent/specs/SPEC-006-error-handling.md`
- `ARCHITECTURE.md`
- `src/humanhand/cli/app.py`
- `src/humanhand/cli/output.py`
- Existing CLI tests

## Files to Change

Expected files:

- `src/humanhand/cli/app.py`
- `src/humanhand/cli/output.py`
- `src/humanhand/cli/errors.py` if needed.
- `tests/e2e/test_cli_ux.py`
- `tests/e2e/test_cli_json.py`
- `tests/e2e/test_cli_errors.py`
- `tests/smoke/test_cli_smoke.py`
- `README.md`
- `.agent/execplans/EP-005-user-interface-or-client.md`
- `.agent/state/last-result.env`

## Interfaces and Contracts

- `--json` stdout is valid JSON only.
- `--no-color` disables color.
- `NO_COLOR` disables color.
- Generated prose appears on stdout only with `--print`.
- Status and logs go to stderr.
- Exit codes are stable for success vs known errors.

## Milestones

### M1 — Implement JSON and text renderers

- Goal: Centralize CLI output formatting.
- Files to read: `SPEC-004`, `src/humanhand/cli/output.py`.
- Files to change: `src/humanhand/cli/output.py`, `tests/e2e/test_cli_json.py`.
- Exact edits expected: Render success/error objects in text or JSON; JSON mode writes no extra text; no user text in logs.
- Validation command: `sh scripts/test-e2e.sh`
- Expected result: `e2e tests: ok`
- Recovery: If Typer captures stderr/stdout unexpectedly, use CliRunner isolation and assert streams separately.

### M2 — Implement color/no-color and accessibility behavior

- Goal: Make output screen-reader and terminal friendly.
- Files to read: `SPEC-004`, `ENVIRONMENT.md`.
- Files to change: `src/humanhand/cli/output.py`, `src/humanhand/cli/app.py`, `tests/e2e/test_cli_ux.py`.
- Exact edits expected: Honor `--no-color` and `NO_COLOR`; default color off on Windows unless supported; no color-only meaning; no spinners.
- Validation command: `sh scripts/test-e2e.sh`
- Expected result: `e2e tests: ok`
- Recovery: If terminal detection is flaky, default to no color and record decision.

### M3 — Polish empty/error states

- Goal: Provide clear safe messages for common failures.
- Files to read: `SPEC-006`, `SECURITY.md`.
- Files to change: `src/humanhand/cli/app.py`, `src/humanhand/cli/errors.py` if needed, `tests/e2e/test_cli_errors.py`.
- Exact edits expected: Friendly one-line errors for empty input, missing files, BOM, unsafe path, missing config, provider unavailable; JSON error shape in `--json`; no source/style text in messages.
- Validation command: `sh scripts/test-e2e.sh`
- Expected result: `e2e tests: ok`
- Recovery: If error mapping duplicates application logic, move mapping to CLI helper only; do not change domain exceptions broadly.

### M4 — Update smoke and docs

- Goal: Align docs and smoke tests with polished CLI behavior.
- Files to read: `README.md`, `COMMANDS.md`.
- Files to change: `tests/smoke/test_cli_smoke.py`, `README.md`.
- Exact edits expected: Document commands, privacy, no generated stdout unless `--print`, JSON/no-color examples, local fallback.
- Validation command: `sh scripts/smoke-test.sh`
- Expected result: `smoke test: ok`
- Recovery: If smoke exceeds 30 seconds, reduce fixture size and avoid live calls.

### M5 — Full CLI UX verification

- Goal: Prove CLI UX meets spec.
- Files to read: changed tests and docs.
- Files to change: this ExecPlan only unless fixes needed.
- Exact edits expected: Update Progress/Decision Log.
- Validation command: `sh scripts/verify.sh`
- Expected result: `verify: ok`
- Recovery: Use bounded retry; do not relax stdout/stderr or JSON-only requirements.

## Concrete Steps

1. Run preflight.
2. Implement renderers, color, errors, docs/smoke in order.
3. Keep changes in CLI/tests/docs only.
4. Review diff and write final state file.

## Validation and Acceptance

- JSON-only stdout tests pass.
- No-color tests pass.
- Empty/error state tests pass.
- Generated prose hidden unless `--print`.
- Smoke under 30 seconds.
- Full verify passes.

## Idempotence and Recovery

If CLI helpers already exist, extend them rather than duplicate renderers. Prefer default no-color if terminal behavior is uncertain.

## Progress

- [ ] M1 — Implement JSON and text renderers.
- [ ] M2 — Implement color/no-color and accessibility behavior.
- [ ] M3 — Polish empty/error states.
- [ ] M4 — Update smoke and docs.
- [ ] M5 — Full CLI UX verification.

## Surprises & Discoveries

- None yet.

## Decision Log

- 2026-07-05: Treat CLI as nearest equivalent client/UI layer. Reason: project has no GUI/web/TUI. Consequence: accessibility requirements are CLI-focused.

## Outcomes & Retrospective

Not started.
