# Observability

## Logging Strategy

Human Hand emits structured JSONL logs to stderr only. Human-facing results go to stdout. Generated prose is never printed to stdout unless the user passes an explicit `--print` flag.

Logs support local debugging without telemetry. There are no remote metrics, dashboards, distributed traces, or phone-home behavior.

## Structured Log Fields

Required fields when applicable:

| Field | Type | Rule |
|---|---|---|
| `timestamp` | string | ISO-8601 UTC timestamp. |
| `level` | string | `debug`, `info`, `warning`, `error`. |
| `event` | string | Stable event name such as `rewrite.start`. |
| `message` | string | Redacted human-readable summary; no user text. |
| `elapsed_ms` | number/null | Duration for completed operation. |
| `model` | string/null | Model name from config, no secrets. |
| `endpoint_host` | string/null | Host only, no path/query/key. |
| `input_length` | number/null | Character count only. |
| `output_length` | number/null | Character count only. |
| `sha256_prefix` | string/null | Short prefix of hash; no full text. |
| `cache_hit` | boolean/null | Detector cache hit/miss when applicable. |
| `attempt` | number/null | External call attempt number. |
| `retry_reason` | string/null | Redacted reason, such as `network_error` or `http_503`. |

## Redaction Rules

- Never log source text, style samples, prompts, generated output, raw LLM response text, raw detector response text, or secrets.
- Redact common key formats and env var values.
- Strip URL credentials and query strings before logging endpoint host.
- Do not log file contents.
- Tests must assert redaction on representative events.

## Metrics

No remote metrics. Local counters may be emitted to stderr at command end as JSONL events. Allowed counters:

- `rewrite_attempts`.
- `repair_attempts`.
- `detector_calls`.
- `cache_hits`.
- `cache_misses`.
- `retry_count`.
- `duration_ms`.
- `input_chars` and `output_chars`.

Counters must not include text.

## Traces

No distributed tracing. For local debugging, use correlated event names and elapsed times within one command run. Do not add trace exporters.

## Health Checks

`humanhand health --json` is the health surface. It must not call external endpoints by default. It must validate local config shape, cache path, Python/platform, and command availability.

## Uptime Checks

Not applicable. There is no hosted service.

## Dashboards

Not applicable. No dashboards or remote telemetry. Maintainers may inspect CI logs and release smoke outputs only.

## Alerts

No runtime alerts. CI failures, security audit failures, and reported issues are the alert channels.

## Service-Level Indicators

For local production readiness:

- Command success rate in CI smoke tests.
- Mock smoke duration.
- Test coverage.
- Security/audit status.
- Redaction test status.
- Packaging install success.

## Service-Level Objectives

- Mock smoke test under 30 seconds.
- `--help` and `--version` first stdout byte within 100 ms under normal local conditions.
- Zero known user-text logging/cache leaks.
- Zero committed secrets.

## Debugging Production Issues

1. Ask for command, version, redacted logs, platform, and config shape.
2. Do not ask for real user text.
3. Reproduce with synthetic fixtures.
4. Use event names, elapsed times, endpoint host, attempts, retry reason, and hashes to isolate issue.
5. Add regression tests for fixes.

## Observability Acceptance Criteria

- JSONL logs parse successfully.
- Required fields appear for rewrite, verify, detector, cache, retry, and error paths.
- stdout/stderr separation is tested.
- Redaction tests prove no user text or secrets appear.
- Health command works without secrets or network.
- No remote telemetry code exists.
