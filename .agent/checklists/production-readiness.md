# Production Readiness Checklist

- [ ] Functionality: rewrite, verify, diff-facts, scrub, health, help, version work.
- [ ] Tests: lint, format, typecheck, unit, integration, E2E, build, security, audit, smoke, verify pass.
- [ ] Security: secrets absent, redaction tested, endpoint safety tested, schema validation tested.
- [ ] Privacy: no telemetry, no user text logs/cache, third-party endpoint implications documented.
- [ ] Performance: smoke under 30 seconds, input cap, timeout, retry cap tested.
- [ ] Accessibility: JSON mode, no-color, no spinners, screen-reader-friendly output tested.
- [ ] Observability: JSONL logs, counters, health command, no remote telemetry.
- [ ] Deployment: wheel/sdist build, clean install smoke, manual release workflow.
- [ ] Rollback: previous wheel reinstall, config restore, cache deletion documented.
- [ ] Backups: no primary DB; cache does not need backup.
- [ ] Docs: README, CHANGELOG, release, rollback, operations updated.
- [ ] Support: incident response and troubleshooting documented.
- [ ] `sh scripts/production-readiness-check.sh` passes.
- [ ] `sh scripts/loop.sh` prints `build: complete`.
