# Testing Strategy

## Test Pyramid

Human Hand uses a local-first pyramid:

1. Many unit tests for pure domain logic and config validation.
2. Focused integration tests for file I/O, cache, mocked HTTP, and CLI wiring.
3. Small E2E/acceptance tests through Typer `CliRunner` and subprocess smoke tests.
4. Gated live E2E tests for configured LLM/detector endpoints only when explicitly enabled.

## Unit Test Rules

- Unit tests live in `tests/unit/`.
- Unit tests must never hit network, read secrets, depend on real home directories, or require paid accounts.
- Domain unit tests must import only domain modules and standard library helpers unless testing application ports.
- Every domain rule must have tests for success, invalid input, and boundary cases.
- Metadata scrub tests must include BOM, hidden JSON wrappers, provenance headers, model tags, trailing whitespace, CRLF normalization, and exactly one trailing newline.
- Fact diff tests must include preserved facts, omitted facts, contradicted facts, added facts, numbers, dates, named entities, and quotation-like text.

## Integration Test Rules

- Integration tests live in `tests/integration/`.
- Use temporary directories for files and cache.
- Use respx/httpx or equivalent mocks for HTTP.
- Verify retry behavior with 5xx/network errors and no retry for 4xx/schema errors.
- Verify cache stores no text by inspecting SQLite rows.
- Verify endpoint safety rejects insecure HTTP unless explicitly allowed.

## E2E Test Rules

- E2E tests live in `tests/e2e/`.
- Default E2E tests must use local mocks/fakes and complete without secrets.
- Live tests must be marked and skipped unless `HUMANHAND_RUN_LIVE_E2E=1`.
- Live tests must fail clearly when required endpoint/key/model is missing.
- E2E tests must cover `rewrite`, `verify`, `diff-facts`, `scrub`, `health`, `--help`, and `--version` after those commands exist.

## Contract Tests

- CLI contract tests assert command names, flags, stdout/stderr separation, JSON-only stdout in `--json` mode, exit codes, and no generated prose on stdout without `--print`.
- LLM contract tests assert request shape, schema-mode response parsing, fallback prompt-parse behavior when enabled, timeout, retry, and redaction.
- Detector contract tests assert provider selection, response schema validation, cache key construction, fallback heuristic result shape, and no user text persistence.

## Smoke Test Rules

- Smoke tests live in `tests/smoke/`.
- `sh scripts/smoke-test.sh` must complete under 30 seconds on mocks.
- Smoke tests must run without external network or secrets.
- Smoke tests must assert `humanhand --help`, `humanhand --version`, and at least one mocked rewrite/verify path after EP-004.

## Regression Test Rules

Add a regression test whenever fixing a bug that affects:

- Fact preservation.
- Metadata cleanup.
- UTF-8/BOM handling.
- Output newline behavior.
- Logging redaction.
- Cache text leakage.
- Endpoint security.
- Detector/LLM schema validation.
- CLI stdout/stderr contracts.

## Performance Test Rules

- Mock smoke test must be under 30 seconds.
- At least 95% of mock smoke runs should complete under 30 seconds in CI-class environments.
- `--help` and `--version` must emit first stdout byte within 100 ms in normal local conditions.
- Input cap defaults to 200,000 characters; tests must cover cap enforcement without allocating excessive memory.
- Logging overhead target is under 5% of run time; test with a simple benchmark or timing assertion in EP-008/EP-010 when stable.

## Accessibility Test Rules

Human Hand has no GUI. CLI accessibility requirements are:

- Screen-reader-friendly, predictable text.
- No spinners.
- Color off by default on Windows unless supported.
- `--no-color` honored.
- JSON mode prints JSON-only stdout.
- Empty input produces a friendly one-line error.

CLI tests must cover these behaviors after EP-005.

## Security Test Rules

- Run `sh scripts/security-check.sh`.
- Run `sh scripts/dependency-audit.sh`.
- Include tests for no secrets in logs, no user text in logs/cache, no insecure endpoint unless allowed, strict UTF-8 rejection, BOM rejection, and safe output path behavior.
- Unit tests must include redaction filter patterns for common key formats without storing real keys.

## Test Data Rules

- Fixtures must be synthetic and short.
- No real user data.
- No copyrighted third-party text beyond trivial fair-use snippets; prefer original invented samples.
- No sample API keys or realistic secrets.
- Fixtures must not include raw LLM/detector responses containing user text.

## Mocking Rules

- Mock at the external boundary, not inside domain logic.
- Mock HTTP with respx/httpx or provider adapter fakes.
- Mock time/randomness with injected values or deterministic seed.
- Do not mock the scrubber or fact diff in rewrite acceptance tests; those are core guarantees.

## Fixture Rules

- Use pytest fixtures for temporary files, fake configs, fake LLM clients, fake detector clients, and cache paths.
- Keep fixtures local to the tests that need them unless reused across three or more files.
- Fixture names must describe behavior, not implementation shortcuts.

## Required Tests per Feature

Each feature must include:

- Unit tests for pure logic.
- Integration tests for side effects.
- CLI/contract tests for user-visible behavior.
- Privacy/logging tests for text and secret redaction.
- Failure-mode tests for invalid input and unavailable external services.
- Regression tests for any bug fixed during the ExecPlan.

## Validation Matrix

| Area | Command |
|---|---|
| Lint | `sh scripts/lint.sh` |
| Format | `sh scripts/format-check.sh` |
| Typecheck | `sh scripts/typecheck.sh` |
| Unit | `sh scripts/test-unit.sh` |
| Integration | `sh scripts/test-integration.sh` |
| E2E | `sh scripts/test-e2e.sh` |
| Build | `sh scripts/build.sh` |
| Security | `sh scripts/security-check.sh` |
| Audit | `sh scripts/dependency-audit.sh` |
| Smoke | `sh scripts/smoke-test.sh` |
| Full | `sh scripts/verify.sh` |

## Definition of Test Done

Testing is done for an ExecPlan when all required tests pass, new behavior has regression coverage, tests do not rely on live network unless gated, coverage requirements for the phase are met, and no test fixture/log/cache contains user text or secrets.

## Pre-SLM Test Boundary

The Pre-SLM test pyramid adds deterministic replay, source/style lane isolation,
malicious-container and parser-limit fixtures, authorship review, protected-span and
revision checks, public-artifact package audits, privacy-mode tests, lexical ambiguity
no-op tests, and Beacon policy-firewall tests. All new live research or scanner calls
remain explicitly gated; synthetic/public fixtures are required by default.
