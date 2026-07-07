# Security Guidance

## Security Goals

- Protect user text from accidental logging, caching, telemetry, or external submission.
- Protect secrets from repository, logs, stdout, stderr, cache, fixtures, and artifacts.
- Ensure output is plain UTF-8 text with no hidden metadata or provenance markers.
- Prevent accidental destructive writes to input files.
- Ensure external endpoint use is explicit, HTTPS-safe by default, retried safely, and schema validated.

## Threat Model Summary

| Threat | Mitigation |
|---|---|
| User text appears in logs or cache | Redaction filters, tests, cache schema constraints, no raw response persistence. |
| API key leaks | `.env` ignored, env-only secrets, redaction, secret scan, no sample keys. |
| LLM response contains hidden metadata | Response schema validation and metadata scrub before write. |
| Fact drift or hallucination | Domain fact diff and repair loop, `diff-facts`, tests. |
| Insecure endpoint exfiltration | Reject HTTP unless `HUMANHAND_ALLOW_INSECURE=1` is set for localhost/127.0.0.1/::1 only. |
| Detector/LLM API schema drift | Strict schema validation and clear errors. |
| Input overwrite | File I/O rejects output path equal to input path. |
| Supply-chain vulnerability | Lock file, Bandit, pip-audit, CI security checks. |

## Authentication Rules

Authentication is out of scope. Human Hand is a single-user local CLI with no accounts, roles, sessions, or server-side auth. API keys for LLM/detector providers are not user accounts inside Human Hand; they are external service credentials read from environment or ignored `.env`.

## Authorization Rules

Authorization is out of scope because there is no multi-user server. Remaining permission rules:

- Never overwrite input files.
- Write only to `--out` or documented default output path.
- Cache file should be `0600` where supported.
- Do not read files except explicit CLI inputs, config files documented in `ENVIRONMENT.md`, and local cache when enabled.

## Input Validation Rules

- Decode files as strict UTF-8.
- Reject BOM.
- Reject empty source/style inputs with a friendly one-line error.
- Enforce `HUMANHAND_MAX_CHARS`, default 200000.
- Validate path existence and read permissions for inputs.
- Validate output path is not an input path.
- Validate endpoint URL, model, provider, and detector names against config contracts.

## Output Encoding Rules

- Output text must be UTF-8 without BOM.
- Normalize newlines to LF.
- Strip trailing whitespace per line.
- Ensure exactly one trailing newline.
- Strip metadata-like markers before write.
- Do not include JSON wrappers, provenance headers, model identifiers, telemetry fields, or hidden tags in generated prose.

## Secret Management Rules

- Secrets are read only from environment variables or ignored `.env`.
- `.env` must be listed in `.gitignore`.
- Never commit sample keys.
- Redact values matching secret patterns in logs/errors.
- Do not include secrets in test fixtures.
- Do not print secrets in JSON output.

## Dependency Security Rules

- Add dependencies only when necessary and documented.
- Lock dependencies with uv.
- Run `sh scripts/dependency-audit.sh` before completion of security and production-readiness plans.
- Run `sh scripts/security-check.sh` before completion of EP-006 and later.
- Do not vendor detector SDKs unless license and source are verified through an ADR.

## Logging Redaction Rules

- Logs are JSONL to stderr only.
- Never log source text, style samples, prompts, generated output, raw LLM responses, or raw detector responses that contain text.
- Allowed text-derived fields: character length, byte length, SHA-256 prefix, and boolean flags.
- Redact env var values and credential-like substrings.
- Error messages must be useful without containing user text.

## Data Protection Rules

- No telemetry.
- No phone-home behavior.
- No cloud database.
- No persistent user-text history.
- Optional cache stores only detector score metadata.
- Third-party endpoints receive text only when user configures them for the invoked command.
- README and CLI help must document this privacy implication.

## Production Data Rules

- User input files are production data.
- Treat accidental overwrite or disclosure as a security incident.
- Use temporary files only in tests or atomic write helpers that do not expose text to logs.
- Do not store production text in test fixtures.

## Safe Migration Rules

No primary database migrations exist. Cache schema changes must:

- Never add user text columns.
- Include schema version.
- Be backward-compatible where practical.
- Support safe rollback by deleting cache.
- Have integration tests for existing cache files.

## API Security Rules

There is no HTTP API. External HTTP clients must:

- Use HTTPS unless explicitly allowed.
- Timeout by default after 30 seconds.
- Retry up to 3 times on 5xx/network errors only.
- Validate schemas.
- Redact request/response details in logs.

## CSRF/CORS/Session Rules

Not applicable. Human Hand has no browser session, cookies, CSRF surface, or CORS surface.

## Rate Limiting

No server-side rate limiting. External clients should avoid retry storms through capped retries and exponential backoff.

## File Upload Rules

Not applicable as a server feature. CLI file input rules are strict UTF-8, explicit paths only, no overwrite, and no hidden persistence.

## Security Checklist

- `.env` ignored.
- Secrets redacted.
- No user text in logs/cache/tests.
- UTF-8 strict and BOM rejected.
- Output scrubbed before write.
- Input files not overwritten.
- HTTP unsafe endpoint rejected by default.
- LLM/detector responses schema validated.
- Bandit passes.
- pip-audit reviewed.
- Secret scan passes.

## Security STOP Conditions

Stop when:

- A live key/account is required and missing.
- A command may expose user text to an unconfigured external endpoint.
- A proposed change would store user text persistently outside the requested output file.
- A proposed change would weaken redaction, endpoint validation, schema validation, or output scrub guarantees.
- A production release/publish action is requested without explicit permission.
