# Production Readiness

## Definition of Production Readiness

Human Hand is production-ready when all ExecPlans EP-000 through EP-010 are complete, all specs are satisfied, `sh scripts/verify.sh` exits 0, `sh scripts/production-readiness-check.sh` exits 0, `sh scripts/loop.sh` prints `build: complete`, the wheel installs cleanly, post-install smoke tests pass, privacy/security checks pass, and remaining risks are documented with explicit acceptance.

## Functional Readiness

- `humanhand rewrite` reads source/style, preserves facts, matches style, scrubs metadata, writes UTF-8 LF output, and does not print generated prose without `--print`.
- `humanhand verify` returns detector or local heuristic scoring without requiring paid accounts by default.
- `humanhand diff-facts` identifies omissions, additions, contradictions, and preserved anchors.
- `humanhand scrub --audit` audits metadata markers without modifying input.
- `humanhand health --json`, `--help`, and `--version` work.
- Non-goals remain excluded.

## Test Readiness

- Lint passes.
- Format check passes.
- Typecheck passes.
- Unit tests pass.
- Integration tests pass.
- E2E tests pass without live network by default.
- Build passes.
- Security check passes.
- Dependency audit is reviewed.
- Smoke tests pass under 30 seconds on mocks.
- Coverage is at least 85% after EP-007.
- Live tests are gated and skipped unless explicitly enabled.

## Security Readiness

- No secrets in repository, logs, artifacts, or fixtures.
- `.env` ignored.
- Redaction filters tested.
- User text never logged or cached.
- Output scrub before write tested.
- Strict UTF-8 and BOM rejection tested.
- Insecure endpoints rejected unless explicitly allowed.
- LLM/detector schemas validated.
- Bandit and pip-audit pass or findings are documented and accepted.

## Privacy Readiness

- No telemetry, phone-home, remote metrics, or cloud database.
- Third-party endpoint privacy implications documented.
- Local endpoint option documented.
- Cache stores detector score metadata only.
- Tests inspect cache for no text.
- README states users are responsible for legal/ethical use.

## Performance Readiness

- Smoke under 30 seconds.
- `--help` and `--version` first byte target documented and tested where practical.
- Default input cap 200,000 characters enforced.
- External timeout default 30 seconds.
- Retry cap of 3 attempts enforced.
- Logging overhead target assessed in EP-008/EP-010.

## Accessibility Readiness

- CLI output is predictable and screen-reader friendly.
- stdout and stderr are separated.
- JSON mode prints JSON-only stdout.
- `--no-color` and `NO_COLOR` honored.
- No spinners.
- Empty input errors are one-line and actionable.

## Observability Readiness

- Structured JSONL logs to stderr.
- Required fields implemented.
- Redaction tests pass.
- Local counters emitted.
- Health command implemented.
- No remote telemetry.

## Deployment Readiness

- Wheel and sdist build.
- Wheel installs in clean Python 3.11 env.
- Console script `humanhand` works.
- README install steps validated.
- GitHub Actions CI matrix exists.
- Manual release workflow exists and does not auto-publish.

## Rollback Readiness

- Previous wheel reinstall documented.
- Config rollback documented.
- Cache deletion documented.
- Release rollback/yank requires maintainer decision.
- Rollback smoke tests documented.

## Data Readiness

- No primary database.
- Cache schema versioned.
- No user text in cache.
- Cache can be deleted safely.
- Input files read-only.
- Output writes only to requested path.

## Documentation Readiness

- README covers install, commands, privacy, endpoint configuration, detector fallback, and ethical responsibility.
- CHANGELOG exists.
- Docs here are updated.
- Specs match behavior.
- ExecPlans are complete.
- Release notes prepared.

## Support Readiness

- Operations runbook exists.
- Incident response checklist exists.
- Troubleshooting docs avoid collecting real user text.
- Maintainer approval gates documented.

## Final Launch Gate

EP-010 must record:

- Commands run and results.
- Artifact names and hashes if available.
- Changed files review.
- Security/privacy review result.
- Performance review result.
- Remaining risks.
- Maintainer approval status for release/publish.

## Checklist

- [x] EP-000 through EP-010 complete.
- [x] `sh scripts/verify.sh` passes.
- [x] `sh scripts/production-readiness-check.sh` passes.
- [x] `sh scripts/loop.sh` prints `build: complete`.
- [x] Wheel/sdist built.
- [x] Clean install smoke passes.
- [x] No secrets or user text leaks.
- [x] README/CHANGELOG/release notes updated.
- [x] Rollback drill documented.
- [x] Final Decision Log entry added.
