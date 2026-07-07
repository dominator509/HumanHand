# SPEC-007: Observability

## Status

Accepted blueprint specification.

## Owner

Blueprint / Maintainer.

## Linked Roadmap Phase

Phase 7: Observability and operations.

## Linked ExecPlans

EP-008, EP-010.

## User-Visible Goal

Users and maintainers can diagnose local CLI issues with safe structured logs, counters, and health output without telemetry or sensitive text leakage.

## Non-Goals

- Remote metrics.
- Dashboards.
- Distributed tracing.
- Phone-home.
- Hosted alerts.
- Logging user text.

## Terms

- JSONL log: one JSON object per stderr line.
- Local counter: aggregate event emitted at command end.
- Health command: local configuration/runtime diagnostic command.

## Required Behavior

- Logs to stderr only.
- Human results to stdout only.
- Required log fields implemented where applicable.
- Redaction applied to secrets and text-like fields.
- Local counters emitted for command runs.
- `humanhand health --json` validates config shape and endpoint safety without network by default.
- `humanhand health --json` reports `llm_configured=true` only when live rewrite has both an endpoint URL and a model configured.
- No remote telemetry code.

## Inputs

- Command lifecycle events.
- Config values.
- Retry outcomes.
- Cache hit/miss.
- Timing values.

## Outputs

- JSONL stderr logs.
- JSON health output.
- Local counter events.

## Error States

- Log serialization failure.
- Redaction failure.
- Invalid health config.
- Cache path unavailable.

## Data Rules

- Logs/counters contain no source/style/prompt/output/provider text.
- Hash prefixes and lengths are allowed.
- Endpoint host allowed; path/query disallowed.

## Security Rules

- Redaction before serialization.
- Secret scan covers logging fixtures.
- Tests assert user text absence.

## Accessibility Rules

- Health output supports JSON for machines.
- Human health output is predictable and concise.

## Performance Rules

- Logging overhead target under 5% of run time.
- Health command should not perform external network calls by default.

## Observability Rules

This spec defines observability rules. Changes require docs/tests update.

## Required Tests

- JSONL parse tests.
- Required field tests.
- Redaction tests.
- stdout/stderr separation tests.
- Health command tests.
- No telemetry import/config tests where practical.

## Acceptance Criteria

- Observability tests pass.
- Logs are safe and useful.
- Health command works offline.
- No remote telemetry exists.
