# Validation Checklist

Run commands from repository root.

- [ ] Preflight: `sh scripts/preflight.sh` -> `preflight: ok`.
- [ ] Install: `sh scripts/install.sh` -> `install: ok`.
- [ ] Lint: `sh scripts/lint.sh` -> `lint: ok`.
- [ ] Format check: `sh scripts/format-check.sh` -> `format check: ok`.
- [ ] Typecheck: `sh scripts/typecheck.sh` -> `typecheck: ok`.
- [ ] Unit tests: `sh scripts/test-unit.sh` -> `unit tests: ok`.
- [ ] Integration tests: `sh scripts/test-integration.sh` -> `integration tests: ok`.
- [ ] E2E tests: `sh scripts/test-e2e.sh` -> `e2e tests: ok`.
- [ ] Build: `sh scripts/build.sh` -> `build: ok`.
- [ ] Security: `sh scripts/security-check.sh` -> `security check: ok`.
- [ ] Dependency audit: `sh scripts/dependency-audit.sh` -> `dependency audit: ok`.
- [ ] Smoke: `sh scripts/smoke-test.sh` -> `smoke test: ok`.
- [ ] Full verify: `sh scripts/verify.sh` -> `verify: ok`.
- [ ] Production readiness when applicable: `sh scripts/production-readiness-check.sh` -> `production readiness: ok`.
- [ ] Loop status when applicable: `sh scripts/loop.sh` -> `build: complete`.
