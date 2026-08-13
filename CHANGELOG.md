# Changelog

All notable changes to Human Hand are documented in this file.

## [1.0.0] — Unreleased

### Added
- Foundation package structure with `pyproject.toml` and uv dependency management.
- Source skeleton: `src/humanhand/` with CLI (`cli/`) and infra (`infra/`) packages.
- Typer CLI application with `--help`, `--version`, and `health` commands.
- Configuration dataclass with environment variable loading and validation.
- Baseline unit tests (8 tests), E2E CLI tests (6 tests), and smoke tests (3 tests).
- CI workflow for Windows and Ubuntu with Python 3.11.
- Ruff lint/format, mypy strict typechecking, pytest, bandit, and pip-audit tooling.
- Build pipeline producing wheel and sdist artifacts.
- Documentation baseline: README, CHANGELOG, ARCHITECTURE, and environment docs.
- Core domain model: style fingerprints, factual anchors, metadata scrub rules, and deterministic decisions.
- Domain API surface: `StyleFingerprint`, `fact_preservation_score`, `has_drift`, `scrub_metadata`.
- Persistence layer: SQLite cache for detector scores with no-text safeguards, file I/O helpers, configuration management.
- Service layer: use-case orchestration for rewrite, verify, diff-facts, scrub, and health.
- LLM integration adapter with configurable provider/model, timeout, and retry support.
- Detector adapter system with local heuristic fallback and provider abstraction.
- CLI UX polish: `--json` output mode on all commands, `--no-color` support, `NO_COLOR` env var compliance, `--print` flag for rewrite.
- Privacy enforcement: generated prose never on stdout without `--print` flag.
- Security hardening: secret redaction in logs and error messages, no-text logging policy (lengths and sha256 prefixes only, never raw text), endpoint safety validation (rejects insecure HTTP unless `HUMANHAND_ALLOW_INSECURE=1` for localhost/127.0.0.1/::1), logging redaction on all output paths.
- Expanded test suite: from 623 to 794 total tests (792 passing, 2 gated skips), 95.28% coverage, enforced 85% coverage threshold via `fail_under`.
- Observability: structured logging with JSON output, operation counters (attempts, successes, failures, duration), health endpoint hardening with component status reporting.
- Health endpoint validity now matches the same local endpoint safety rules enforced by the runtime LLM client.
- Loopback HTTP now requires explicit `HUMANHAND_ALLOW_INSECURE=1`, and non-loopback HTTP is rejected even when that flag is set.
- Rewrite no longer invents a default LLM model name; live rewrite now requires an explicit `HUMANHAND_LLM_MODEL`, and health reports `llm_configured=true` only when both URL and model are present.
- Rewrite now surfaces missing input-file and output-path overlap errors before live LLM config errors when no user text needs to be read.
- Deployment preparation: build config hardening, release workflow steps in DEPLOYMENT.md, documentation baseline complete.
- Console-script smoke validation via `uv run humanhand` for `--version`, `--help`, `health`, `verify`, `diff-facts`, and `scrub`.
- `pyproject.toml` metadata: Python classifiers, keywords, project URLs.

## 2026-08-12 - Pre-SLM Bootstrap

- Added the user-supplied Pre-SLM implementation blueprint and resumable bootstrap prompt.
- Added the Pre-SLM program manifest, ADRs, specifications, ordered ExecPlans, and
  documentation-only future SLM handoff contract.
- Kept SLM training/runtime, model downloads, detector optimization, and publication out
  of scope; EP-011 is the active control-plane plan.
