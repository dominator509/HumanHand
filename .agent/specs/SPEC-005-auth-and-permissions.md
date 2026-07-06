# SPEC-005: Auth, Permissions, and Security Baseline

## Status

Accepted blueprint specification.

## Owner

Blueprint / Maintainer.

## Linked Roadmap Phase

Phase 5: Auth, permissions, and security.

## Linked ExecPlans

EP-006, EP-008, EP-010.

## User-Visible Goal

Human Hand runs locally without accounts while protecting user files, secrets, outputs, logs, cache, and endpoint configuration.

## Non-Goals

- Authentication.
- Authorization roles.
- Accounts.
- Sessions.
- Tokens issued by Human Hand.
- Server-side permissions.
- CSRF/CORS/session management.

## Terms

- External credential: API key/token for user-configured LLM or detector provider.
- Permission boundary: Local filesystem read/write behavior and cache permissions.
- Security baseline: Required controls despite no auth.

## Required Behavior

- No auth code or account model.
- API keys read from env/.env only.
- `.env` ignored.
- Input files read only.
- Output path cannot equal input path.
- Cache file permission best effort `0600`.
- HTTP endpoints rejected unless allowed.
- Secrets redacted in logs/errors.
- User text not logged/cached.
- Security commands pass.

## Inputs

- Env vars.
- CLI paths.
- Config file path if implemented.
- External endpoint URLs.

## Outputs

- Redacted errors/logs.
- Safe output files.
- Cache metadata only.

## Error States

- Missing API key for provider.
- Unsafe endpoint.
- Unsafe output path.
- Secret-looking value detected in artifact/log test.
- User text found in cache/log test.

## Data Rules

- No user text in logs/cache/artifacts/fixtures.
- No secrets in repo or output.
- Cache deletion is safe.

## Security Rules

- Redaction tests required.
- Secret scan required.
- Bandit and pip-audit required.
- Schema validation required for external responses.

## Accessibility Rules

Security errors must be concise and actionable.

## Performance Rules

Security checks should be part of verification and not require network except dependency audit as configured by pip-audit. If audit cannot run due network/tool limitation, record and follow STOP/recovery rules.

## Observability Rules

Security events logged as redacted JSONL. Do not include secret values, request bodies, file contents, or provider text.

## Required Tests

- No auth routes/classes/session state tests by absence/structure where practical.
- Secret redaction tests.
- User text logging tests.
- Endpoint safety tests.
- Safe output path tests.
- Cache no-text and permissions tests.
- Schema validation failure tests.

## Acceptance Criteria

- Auth remains out of scope.
- Security baseline tests pass.
- Security scripts pass or documented accepted findings exist.
- No secrets/user text leaks are present.
