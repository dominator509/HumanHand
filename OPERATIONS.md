# Operations Runbook

## Local Operations

Human Hand runs as a local CLI. Operational work is primarily support for installation, configuration, safe file handling, and troubleshooting external endpoint failures.

Common commands:

- `humanhand --help`
- `humanhand --version`
- `humanhand health --json`
- `humanhand rewrite --source <source> --style <style> --out <out>`
- `humanhand verify <output>`
- `humanhand diff-facts <source> <output>`
- `humanhand scrub --audit <file>`

## Staging Operations

There is no hosted staging environment. Use a clean local or CI environment:

1. Install the built wheel.
2. Run post-install smoke tests.
3. Use synthetic fixtures only.
4. Verify no network calls occur unless explicitly configured.

## Production Operations

Production means user-installed local usage. Maintainers support releases, docs, issue triage, security advisories, and rollback guidance. Maintainers do not operate a hosted service or access user data.

## Health Checks

`humanhand health --json` should report:

- CLI version.
- Python version.
- Platform.
- Config validity without printing secrets.
- Whether cache directory is writable when enabled.
- Whether configured endpoint is syntactically valid.
- Detector provider availability by configuration, not by live call unless a future explicit flag permits it.

Health must not read user text or call external services by default.

## Common Failure Modes

| Failure | Likely Cause | Safe Response |
|---|---|---|
| UTF-8 decode error | Input is not strict UTF-8 or contains BOM. | Convert file to UTF-8 without BOM and retry. |
| Empty input error | Source or style file is empty. | Provide non-empty text. |
| Input too large | Exceeds `HUMANHAND_MAX_CHARS`. | Split input or raise configured cap knowingly. |
| Endpoint rejected as insecure | HTTP base URL without allow flag. | Use HTTPS or set `HUMANHAND_ALLOW_INSECURE=1` for local server only. |
| Missing model/key | Live LLM/detector path configured without required env. | Set env vars or use local fallback where supported. |
| Schema validation error | Provider response changed or incompatible endpoint. | Capture redacted error, update adapter tests, do not log response text. |
| Cache permission error | Cache directory not writable. | Disable cache or choose writable cache directory. |
| Fact drift detected | LLM rewrite omitted/added/contradicted anchors. | Use repair loop or inspect diff result manually. |

## Troubleshooting

- Run `humanhand health --json` first.
- Run with synthetic files to isolate endpoint/config from text issues.
- Inspect stderr JSONL logs for redacted event names, timings, endpoint host, attempts, and retry reasons.
- Do not ask users to paste sensitive source text into issues. Use synthetic reproductions.
- If logs contain user text or secrets, treat as incident.

## Database Backup/Restore

No primary database. Optional cache contains no user text and does not need backup. Restore means deleting or replacing `.cache/humanhand/cache.db`.

## Scheduled Jobs

None. No background workers, cron jobs, daemons, or remote telemetry.

## Incident Triage

Security/privacy incidents include:

- Secret committed or printed.
- User text logged, cached, or included in artifacts.
- Output includes hidden metadata/provenance markers.
- CLI overwrites input files.
- External call occurs without user configuration.

Triage steps:

1. Reproduce with synthetic input if possible.
2. Stop release/publish actions.
3. Preserve redacted evidence.
4. Fix through an ExecPlan or emergency patch plan.
5. Add regression tests.
6. Document impact and mitigation.

## Escalation Rules

- Maintainer approval is required for release rollback, PyPI yanking, security advisory publication, and live provider credential use.
- Legal/academic-integrity questions are outside product operation; direct users to their institution or counsel.

## Maintenance Windows

Not applicable for hosted operations. For releases, use manual release windows chosen by maintainers after EP-010 passes.

## Operational Safety Rules

- Never request real user text for debugging when synthetic fixtures can reproduce the issue.
- Never run live tests with user text.
- Never publish artifacts before production readiness and maintainer approval.
- Never delete user files as part of support guidance except optional cache deletion.

## Pre-SLM Operations

Operate only on the user-selected project directory and explicit retention policy.
Obsidian projections are user-triggered and non-authoritative. Beacon observations are
read-only until a human approves a quarantined proposal; no automatic merge, publish,
deploy, detector loop, or private-document upload is permitted.
