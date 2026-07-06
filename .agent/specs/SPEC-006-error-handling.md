# SPEC-006: Error Handling

## Status

Accepted blueprint specification.

## Owner

Blueprint / Maintainer.

## Linked Roadmap Phase

All phases.

## Linked ExecPlans

EP-002 through EP-010.

## User-Visible Goal

Users receive clear, stable, safe errors that explain what failed without leaking source text, style samples, generated output, prompts, responses, or secrets.

## Non-Goals

- Full stack traces in normal CLI output.
- Logging user text for diagnostics.
- Retrying non-retryable failures.
- Interactive approval prompts.

## Terms

- User-facing error: stdout/stderr message intended for CLI user.
- Log error: JSONL stderr event for diagnostics.
- Retryable failure: network error or 5xx response from external endpoint.
- Non-retryable failure: validation error, auth error, schema error, unsafe endpoint, invalid input.

## Required Behavior

- Stable error categories: `input_error`, `config_error`, `io_error`, `external_error`, `schema_error`, `fact_drift_error`, `security_error`, `internal_error`.
- Friendly one-line errors by default.
- JSON error object in `--json` mode.
- Exit codes nonzero for errors.
- Retries up to 3 only for network/5xx.
- Exponential backoff with cap.
- Redacted logs for all failures.
- Bounded retry for coding agents during validation failures.

## Inputs

- Exceptions from domain/application/infra.
- External HTTP statuses/errors.
- CLI parse failures.

## Outputs

- User-facing message.
- JSON error object in `--json` mode.
- Redacted log event.
- Exit code.

## Error States

- Empty input.
- UTF-8/BOM error.
- Input too large.
- Missing config.
- Unsafe endpoint.
- External timeout/retry exhausted.
- Schema validation error.
- Detector unavailable.
- Fact drift unresolved.
- Cache corrupt/unavailable.

## Data Rules

- Error objects must not contain user text except explicit user-facing diff/audit result fields.
- Logs must never contain user text.
- Include hash prefix/length instead of text where helpful.

## Security Rules

- Secrets always redacted.
- Do not log HTTP bodies.
- Do not include API keys in URLs or messages.

## Accessibility Rules

- Errors are short, direct, and avoid color-only meaning.
- Suggest one next action when safe.

## Performance Rules

- Retry cap enforced.
- Timeout default 30 seconds.
- No infinite loops.

## Observability Rules

- Log `event`, `level`, `message`, `retry_reason`, `attempt`, `elapsed_ms`, and endpoint host where applicable.

## Required Tests

- Error mapping tests.
- JSON mode error tests.
- Redaction tests.
- Retry and non-retry tests.
- Exit code tests.
- Empty input and BOM tests.

## Acceptance Criteria

- All known errors map to safe messages.
- No stack traces in normal CLI output.
- No text/secrets in logs.
- Retry behavior is bounded and tested.
