# SPEC-003: CLI and Service Contracts

## Status

Accepted blueprint specification.

## Owner

Blueprint / Maintainer.

## Linked Roadmap Phase

Phase 3: API or service layer.

## Linked ExecPlans

EP-004, EP-005, EP-008, EP-009.

## User-Visible Goal

Users interact with Human Hand through stable CLI commands and optional env/config. There is no HTTP API.

## Non-Goals

- HTTP routes.
- Webhooks.
- Public SDK beyond internal contracts.
- Server auth.
- Streaming UI.

## Terms

- Command contract: CLI name, arguments, flags, stdout/stderr behavior, exit code, and output schema.
- Service method: Application use case invoked by CLI.
- JSON mode: JSON-only stdout with logs still on stderr.

## Required Behavior

Required commands:

- `humanhand rewrite --source <path|-> --style <path> --out <path> [--json] [--print] [--no-color]`.
- `humanhand verify <output> [--provider <provider>] [--json] [--no-color]`.
- `humanhand diff-facts <ai-source> <output> [--json] [--no-color]`.
- `humanhand scrub <file> [--out <path>] [--audit] [--json] [--no-color]`.
- `humanhand health [--json] [--no-color]`.
- `humanhand --help`.
- `humanhand --version`.

Application service methods should mirror these commands: rewrite, verify, diff_facts, scrub, health.

## Inputs

- CLI args and flags.
- Env/config values.
- Input file contents.
- Provider responses via infra adapters.

## Outputs

- Exit code 0 for success.
- Nonzero exit code for errors.
- Human-readable stdout or JSON-only stdout.
- Logs/counters to stderr only.
- Output file for rewrite/scrub write paths.

## Error States

- Invalid command/flag.
- Missing required path.
- File read/write errors.
- Config validation errors.
- LLM/detector unavailable.
- Schema validation errors.
- Fact drift repair failure.
- Unsafe endpoint.

## Data Rules

- CLI must not print generated prose unless `--print` is passed.
- JSON output must not include full source/style/prompt text.
- JSON output for `diff-facts` may include factual anchor summaries derived from user text only because the command's purpose is to show differences to the user; logs must not include those anchors.

## Security Rules

- No secrets in stdout/stderr.
- No user text in stderr logs.
- External calls require explicit config.
- Detector providers require env keys unless local fallback.

## Accessibility Rules

- Predictable command output.
- No spinners.
- `--no-color` honored.
- Color off by default on Windows unless terminal supports it.
- Friendly one-line errors.

## Performance Rules

- `--help` and `--version` first byte under 100 ms target.
- External calls timeout after 30 seconds by default.
- Retry cap 3.

## Observability Rules

- Each command logs start/end/error events to stderr JSONL.
- Required fields from SPEC-007.

## Required Tests

- Typer CliRunner command contract tests.
- Service unit tests with fake ports.
- Mocked HTTP integration tests for LLM and detectors.
- JSON mode tests.
- stdout/stderr separation tests.
- Exit code tests.
- No prose-to-stdout without `--print` test.

## Acceptance Criteria

- Required commands exist and are documented.
- Contract tests pass.
- Live calls are gated.
- No HTTP API files/routes are introduced.
