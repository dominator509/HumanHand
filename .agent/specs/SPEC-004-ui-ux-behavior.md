# SPEC-004: CLI UX Behavior

## Status

Accepted blueprint specification.

## Owner

Blueprint / Maintainer.

## Linked Roadmap Phase

Phase 4: UI or client layer.

## Linked ExecPlans

EP-005, EP-007, EP-009.

## User-Visible Goal

Users receive predictable, accessible, machine-friendly CLI behavior with clear success, empty, loading/status, and error states.

## Non-Goals

- GUI.
- Web UI.
- TUI.
- Real-time streaming UI.
- Spinners.
- Interactive prompts during unattended execution.

## Terms

- Human-facing stdout: user result text.
- Logs: JSONL stderr only.
- Status message: short progress line on stderr without user text.
- JSON mode: JSON-only stdout.

## Required Behavior

- `--help` and `--version` are fast and do not load heavy clients.
- `--json` prints valid JSON only on stdout.
- `--no-color` disables color.
- `NO_COLOR` disables color.
- Color defaults off on Windows unless appropriate terminal support is detected.
- No spinners; use short status messages on stderr.
- Empty input produces a friendly one-line error.
- Generated prose is not printed to stdout unless `--print` is passed.
- Rewrite success prints output path and summary, not text, unless `--print`.
- Verify prints provider, score, label, cache hit, and explanation appropriate to provider/fallback.
- Diff-facts prints a concise drift summary and detailed JSON in `--json` mode.
- Scrub audit prints metadata findings without modifying input.

## Inputs

- CLI flags/args.
- Terminal capabilities.
- `NO_COLOR` env var.
- Command result objects.

## Outputs

- Plain stdout for human results.
- JSON stdout for `--json`.
- JSONL stderr logs/status.
- Stable exit codes.

## Error States

- Empty input.
- Invalid path.
- Missing config.
- Provider unavailable.
- Fact drift failure.
- Output path unsafe.

## Data Rules

- Do not print source/style/prompt in errors.
- `diff-facts` and `scrub --audit` may show user-facing snippets/findings because that is the explicit purpose; logs must still avoid user text.

## Security Rules

- Secrets redacted.
- Endpoint host only in logs.
- No generated output to stdout without `--print`.

## Accessibility Rules

- No color-only communication.
- No spinner animations.
- Text labels before values.
- Machine-friendly JSON mode.
- Screen-reader-friendly error text.

## Performance Rules

- Help/version first stdout byte within 100 ms target.
- No network or config-heavy initialization for help/version.

## Observability Rules

- Status/progress to stderr only.
- Logs remain JSONL when logging is enabled.

## Required Tests

- CLI help/version speed smoke where practical.
- `--json` stdout parse tests.
- stdout/stderr separation tests.
- `--no-color` and `NO_COLOR` tests.
- Empty input error tests.
- No generated prose without `--print` test.
- Audit does not modify input test.

## Acceptance Criteria

- CLI acceptance tests pass.
- No GUI/TUI/web files introduced.
- CLI output is predictable and accessible.
