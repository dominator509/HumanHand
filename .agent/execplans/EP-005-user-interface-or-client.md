---
id: EP-005
title: User Interface or Client
status: completed
owner: agent
created: 2026-07-05
updated: 2026-07-06
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

- [x] M1 — Implement JSON and text renderers.
- [x] M2 — Implement color/no-color and accessibility behavior.
- [x] M3 — Polish empty/error states.
- [x] M4 — Update smoke and docs.
- [x] M5 — Full CLI UX verification.

## Surprises & Discoveries

- Typer's CliRunner uses a non-TTY stdout, so ANSI color codes are naturally suppressed in tests even without `--no-color`. Color tests validate structural acceptance (flag/env var accepted) rather than ANSI presence/absence in CliRunner output.
- The `NO_COLOR` env var is checked by the output renderers but must also be checkable at the CLI level. Added to `_color_enabled()` in output.py which is called by all color helper functions.
- Smoke test count went from 16 to 21 — all well within the 30-second target (2.54s).
- The first EP-005 completion added `src/humanhand/cli/errors.py`, but the CLI still bypassed that catalog on most exception paths and printed raw exception strings instead. That left error wording less stable than the plan claimed and could leak absolute file paths in user-facing errors.
- The first EP-005 completion also did not enforce the `output path unsafe` error state for CLI write paths. `rewrite` and `scrub` needed explicit `--out` versus input-path guards plus write-side `FileIOError` mapping to keep the CLI contract aligned with SPEC-004/SPEC-006.
- README drifted behind the actual control plane: it omitted EP-004 from the completed status list and incorrectly said the next implementation seam was EP-004 instead of EP-006.

## Decision Log

- 2026-07-05: Treat CLI as nearest equivalent client/UI layer. Reason: project has no GUI/web/TUI. Consequence: accessibility requirements are CLI-focused.
- 2026-07-06: Default color to off on Windows unless ANSI-capable terminal detected. Reason: Windows console host does not support ANSI by default. Consequence: color is conservative by default; users with Windows Terminal or ConEmu may need to set `TERM=xterm-256color` to get color output.
- 2026-07-06: Created `cli/errors.py` as a centralized error message catalog. Reason: consistent, screen-reader-friendly, one-line error messages across all commands. Consequence: adding new error states requires updating the catalog; tests can reference catalog keys.
- 2026-07-06: Fan-out strategy for EP-005: core code changes (M1-M3) done inline, E2E tests and docs/smoke done in parallel subagents. Reason: maximized parallelism for the iterative test-writing and doc-update phases while keeping tight control on the small core changes.
- 2026-07-06: Codex audit routed CLI exception handling through the centralized error catalog instead of printing raw exception strings. Reason: EP-005 promised stable one-line errors and no raw system paths in user-facing output. Consequence: text and JSON error messages now stay sanitized and deterministic across read/config/provider/write failures.
- 2026-07-06: Codex audit added CLI-level `--out` versus input-path guards for `rewrite` and `scrub`, and mapped write-side `FileIOError` paths back into stable I/O errors. Reason: `output path unsafe` is an explicit EP-005 error state and previously could slip through on write paths. Consequence: the CLI now rejects self-overwrite attempts before file writes occur.
- 2026-07-06: `.agent/state/continuation.md` was updated during the audit even though it is not listed in Files to Change. Reason: the user requested the standard Claude-to-Codex handoff loop, which requires refreshed pause/resume state between ExecPlans. Consequence: the next EP-006 handoff starts from an audited state file, not a chat recap.

## Outcomes & Retrospective

EP-005 is complete with all 5 milestones validated and the Codex audit pass applied. Key outcomes:

- **Color/accessibility**: `--no-color` flag and `NO_COLOR` env var honored across all commands. Color helpers (`bold`, `red`, `green`, `yellow`, `dim`) available for all renderers. Windows-conservative default (color off unless ANSI terminal detected).
- **JSON mode**: All 5 commands produce valid JSON with stable schemas in `--json` mode. JSON error shape is `{"status": "error", "message": "...", "exit_code": N}`. No extra text on stdout in JSON mode.
- **Error polish**: Centralized error catalog is now actually used by CLI exception paths. All common failure modes (empty input, missing file, BOM, unknown provider, config error, unsafe output path) produce clear one-line messages. Absolute file paths are no longer echoed back in user-facing text/JSON errors.
- **Documentation**: README.md now reflects EP-004 and EP-005 as complete, points the next seam at EP-006, and uses sanitized error examples that match the CLI’s real behavior.
- **Test coverage**: 121 unit, 92 integration, 141 E2E, and 21 smoke tests all pass. `verify.sh` exits 0.
