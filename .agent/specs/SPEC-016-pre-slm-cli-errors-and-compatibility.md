# SPEC-016: Pre-SLM CLI Errors and Compatibility

## Purpose

Keep the existing CLI predictable while adding pre-SLM command families and stable
machine-readable errors.

## Data Contracts

Errors contain a versioned `code`, safe `message`, `retryable` flag, optional finding
references, and no secrets or user text. JSON results use stable schema versions.

## Invariants

`health`, `rewrite`, `verify`, `diff-facts`, and `scrub` retain their names, flags,
stdout/stderr rules, exit semantics, and privacy guarantees unless a migration is
explicitly documented.

## Inputs and Outputs

CLI inputs are validated paths, options, project ids, and explicit policies. Outputs
are concise status/errors or JSON objects; document text is opt-in only.

## Privacy Rules

Errors redact paths where required, never print prompts/responses/keys, and never emit
generated prose in JSON mode.

## Failure Behavior

Unknown command, invalid option, unsafe path, missing configuration, unsupported format,
blocked network, and review-required states map to deterministic codes.

## CLI Behavior

Register new sub-apps only in their implementing ExecPlan. All applicable commands
support `--json` and `--no-color`; help text documents local-only and live gates.

## JSON Result Schema

Every command result includes `schema_version`, `status`, and either `data` or
`error`, with stable code values and no mixed human prose.

## Backward Compatibility

Compatibility facades remain for `StyleFingerprint`, fact diff, and current result
types for one release where practical.

## Test Requirements

Test help, global/local flags, JSON-only stdout, error codes, exit codes, no-color,
legacy commands, and no generated prose without explicit print behavior.

## Explicit Non-goals

Moving business logic into Typer, changing public flags without a plan, or adding a
model runtime.

## Acceptance Criteria

Old commands pass existing tests, new errors are schema-valid and redacted, and new
command surfaces remain isolated to their active plan.
