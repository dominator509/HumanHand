---
id: EP-004
title: API or Service Layer
status: completed
owner: agent
created: 2026-07-05
updated: 2026-07-06
---

# EP-004: API or Service Layer

## Purpose / Big Picture

Implement Human Hand's application services, OpenAI-compatible LLM client, detector provider interfaces, local heuristic verifier, and Typer CLI command contracts. This is the equivalent of an API layer for a CLI-only product.

## Scope

- Application use cases for rewrite, verify, diff-facts, scrub, health.
- LLM client with OpenAI-compatible base URL, timeout, retry, HTTPS enforcement, schema validation, and redaction-safe errors.
- Detector client interface and provider adapters for local heuristic plus documented stubs/adapters for GPTZero, Originality.ai, Copyleaks, Winston AI, Turnitin AI without inventing undocumented endpoints.
- CLI commands and contract tests.
- Mocked HTTP integration tests.

## Non-goals

- Web server, HTTP routes, SDK, GUI/TUI.
- Live LLM/detector calls by default.
- CLI polish beyond command correctness; detailed UX polish is EP-005.
- Publishing/release.

## Context and Orientation

EP-002 and EP-003 must be complete. Domain and infra helpers exist. This plan connects them through application services and CLI contracts.

## Files to Read First

- `ARCHITECTURE.md`
- `COMMANDS.md`
- `.agent/specs/SPEC-003-api-contracts.md`
- `.agent/specs/SPEC-006-error-handling.md`
- `SECURITY.md`
- `OBSERVABILITY.md`
- Existing application/infra/cli files

## Files to Change

Expected files:

- `src/humanhand/application/__init__.py`
- `src/humanhand/application/ports.py`
- `src/humanhand/application/services.py`
- `src/humanhand/infra/llm.py`
- `src/humanhand/infra/http.py`
- `src/humanhand/infra/detectors/__init__.py`
- `src/humanhand/infra/detectors/base.py`
- `src/humanhand/infra/detectors/local.py`
- `src/humanhand/infra/detectors/gptzero.py`
- `src/humanhand/infra/detectors/originality.py`
- `src/humanhand/infra/detectors/copyleaks.py`
- `src/humanhand/infra/detectors/winston.py`
- `src/humanhand/infra/detectors/turnitin.py`
- `src/humanhand/cli/app.py`
- `src/humanhand/cli/output.py`
- `tests/unit/application/test_services.py`
- `tests/integration/test_llm_client.py`
- `tests/integration/test_detectors.py`
- `tests/e2e/test_cli_commands.py`
- `tests/smoke/test_cli_smoke.py`
- `.agent/execplans/EP-004-api-or-service-layer.md`
- `.agent/state/last-result.env`

## Interfaces and Contracts

- Application service methods: `rewrite`, `verify`, `diff_facts`, `scrub`, `health`.
- LLM client port returns validated rewrite text and metadata-free response object.
- Detector client port returns provider/model/score/label/details text-free result.
- CLI commands exactly as SPEC-003 defines.
- No generated prose to stdout unless `--print`.

## Milestones

### M1 — Define application services and ports

- Goal: Create orchestration layer without concrete side effects.
- Files to read: `ARCHITECTURE.md`, existing domain/infra helpers.
- Files to change: `src/humanhand/application/ports.py`, `src/humanhand/application/services.py`, `tests/unit/application/test_services.py`.
- Exact edits expected: Define Protocols for LLM, detector, file reader/writer, cache, logger; implement use-case orchestration with fake ports in tests.
- Validation command: `sh scripts/test-unit.sh`
- Expected result: `unit tests: ok`
- Recovery: If protocols cause import cycles, move shared result types to application-local module and update imports minimally.

### M2 — Implement OpenAI-compatible LLM client

- Goal: Support configured OpenAI-compatible chat completions safely.
- Files to read: `SECURITY.md`, `ENVIRONMENT.md`, `SPEC-003`.
- Files to change: `src/humanhand/infra/http.py`, `src/humanhand/infra/llm.py`, `tests/integration/test_llm_client.py`.
- Exact edits expected: Endpoint validation, HTTPS enforcement, timeout default, retry cap, schema response parsing, fallback prompt parse only behind config, redacted errors, no logging bodies.
- Validation command: `sh scripts/test-integration.sh`
- Expected result: `integration tests: ok`
- Recovery: If OpenAI SDK API mismatch occurs, use `httpx` against OpenAI-compatible `/chat/completions` with documented ADR/Decision Log; do not invent SDK calls.

### M3 — Implement detector clients and local fallback

- Goal: Provide verification path without paid keys while keeping provider architecture extensible.
- Files to read: `SPEC-003`, `ASSUMPTIONS.md`, provider docs if already present in repository.
- Files to change: detector files under `src/humanhand/infra/detectors/`, `tests/integration/test_detectors.py`.
- Exact edits expected: Local heuristic fallback returns deterministic score; provider adapters validate required keys and mocked response schemas; unknown/undocumented provider endpoints fail clearly rather than invented live calls.
- Validation command: `sh scripts/test-integration.sh`
- Expected result: `integration tests: ok`
- Recovery: If provider API details are unavailable, implement a disabled adapter with explicit `ProviderUnavailableError`, tests for clear failure, and record the limitation.

### M4 — Implement CLI commands

- Goal: Expose documented command contracts through Typer.
- Files to read: `SPEC-003`, `SPEC-004`, existing CLI skeleton.
- Files to change: `src/humanhand/cli/app.py`, `src/humanhand/cli/output.py`, `tests/e2e/test_cli_commands.py`.
- Exact edits expected: Add `rewrite`, `verify`, `diff-facts`, `scrub`, `health`; handle `--json`, `--print`, `--no-color`; map errors to exit codes; ensure stdout/stderr separation.
- Validation command: `sh scripts/test-e2e.sh`
- Expected result: `e2e tests: ok`
- Recovery: If Typer behavior differs, adjust tests to stable documented Typer behavior without weakening contracts.

### M5 — Full service-layer verification

- Goal: Prove mocked CLI/service paths pass local verification.
- Files to read: changed files and tests.
- Files to change: this ExecPlan only unless fixes needed.
- Exact edits expected: Update progress and decisions; ensure smoke includes mocked/local paths.
- Validation command: `sh scripts/verify.sh`
- Expected result: `verify: ok`
- Recovery: Use bounded retry; live network must remain skipped unless explicitly enabled.

## Concrete Steps

1. Run preflight and confirm previous plans complete.
2. Implement services/ports, LLM client, detectors, CLI commands, verification.
3. Add contract tests before or with implementation.
4. Keep provider live behavior gated.
5. Review diff and write last-result file.

## Validation and Acceptance

- Required CLI commands exist.
- Mocked LLM/detector integration tests pass.
- Local heuristic verify works without keys.
- No web/API server introduced.
- stdout/stderr and JSON contracts pass.
- Full verify passes.

## Idempotence and Recovery

If commands already exist, preserve names and flags unless spec requires correction. If provider APIs are unknown, keep adapter disabled with clear error instead of inventing endpoints.

## Progress

- [x] M1 — Define application services and ports.
- [x] M2 — Implement OpenAI-compatible LLM client.
- [x] M3 — Implement detector clients and local fallback.
- [x] M4 — Implement CLI commands.
- [x] M5 — Full service-layer verification.

## Surprises & Discoveries

- Typer command function names become CLI command names unless explicitly overridden with `@app.command(name="...")`. Renamed functions with `_cmd` suffix required explicit `name=` parameters to avoid colliding with imported service functions (`health`, `rewrite`, `verify`, etc.).
- The first EP-004 completion left a regression where the local detector's insufficient-text payload used a freeform `"error"` string inside `raw_score_json`. The detector-score cache correctly rejected that payload as unsafe text-shaped data, which meant `verify` could fail on short text when caching was enabled.
- The first EP-004 completion also left the rewrite repair loop in a fail-open state: `RepairDecision.FAIL` was treated like `ACCEPT`, and the repair-budget counter was off by one, so a drifted candidate could still be written after the budget was exhausted.
- The first EP-004 completion also left the CLI observability contract incomplete: command loggers were still no-op stubs, so stderr JSONL events were not being emitted even though the service layer already shaped log fields and the spec required them.
- LLM client uses `httpx` directly rather than the `openai` SDK for fine-grained retry/timeout control and to avoid SDK-level logging of request bodies.
- Detector stubs for paid providers raise `ProviderUnavailableError` since API documentation is not available; this is safe and expected per the spec.

## Decision Log

- 2026-07-05: Treat CLI commands as the external API contract. Reason: product is CLI-only. Consequence: SPEC-003 tests CLI/service behavior instead of HTTP routes.
- 2026-07-06: Use `httpx` directly instead of the `openai` SDK for LLM calls. Reason: fine-grained control over retries, timeouts, error handling, and privacy (no SDK-level body logging). Consequence: response schema validation is done manually; the openai SDK remains in pyproject.toml but is not imported by LLM client code.
- 2026-07-06: Detector provider stubs (gptzero, originality, copyleaks, winston, turnitin) raise `ProviderUnavailableError` because API documentation is unavailable. Reason: per EP-004 and SECURITY.md, do not invent undocumented endpoints. Consequence: only the local heuristic detector works without API docs; paid providers can be implemented later when documentation is available.
- 2026-07-06: CLI health command was kept with its original `health` command name using explicit `@app.command(name="health")`. The function was renamed to `health_cmd` to avoid collision with the imported `health()` service function.
- 2026-07-06: M2 and M3 were implemented in parallel using background subagents, reducing wall-clock time. Each agent independently validated its own milestone before handing back.
- 2026-07-06: Codex audit changed the local detector insufficient-text payload from a freeform diagnostic string to a compact `status_code` record. Reason: EP-003 cache privacy rules reject text-shaped `raw_score_json`, and `verify` must remain safe with cache enabled. Consequence: short-text local-verifier results now cache cleanly without weakening the cache validator.
- 2026-07-06: Codex audit introduced `RewriteQualityError` and made `rewrite()` fail closed when repair is exhausted. Reason: SPEC-003 lists fact-drift repair failure as a required error state, and the prior loop could still write drifted output. Consequence: rewrite failures now surface as CLI schema errors instead of silently emitting bad files.
- 2026-07-06: Codex audit replaced the CLI's no-op logger with structured stderr JSONL logging and expanded `health --json` to report config validity and local command/config context. Reason: OBSERVABILITY.md and SPEC-003 require stderr JSONL events and a richer local health surface. Consequence: command contracts now emit parseable logs on success/error paths, and health JSON exposes config/cache/platform/command availability without calling the network.
- 2026-07-06: `.agent/state/continuation.md` was updated during the audit even though it was not in the original Files to Change list. Reason: the user explicitly requested state-file updates between ExecPlans. Consequence: the Claude handoff state now reflects the audited, verified EP-004 result.

## Outcomes & Retrospective

EP-004 is complete with all 5 milestones validated and a Codex audit pass applied. Key outcomes:

- **Application services**: `rewrite`, `verify`, `diff_facts_service`, `scrub_service`, `health` orchestrate use cases through protocol-based dependency injection, keeping the application layer free of concrete infra imports.
- **LLM client**: `OpenAiLlmClient` wraps httpx with HTTPS enforcement, 3x retry on 5xx/network errors, no retry on 4xx, schema validation, and privacy-safe error messages.
- **Detector clients**: `LocalDetector` provides deterministic heuristic scoring (bigram repetition, sentence variance, personal pronouns, AI phrases, word length). Five provider stubs raise clear `ProviderUnavailableError` messages. Factory function `create_detector()` maps provider names to implementations.
- **CLI commands**: All 5 required commands (`rewrite`, `verify`, `diff-facts`, `scrub`, `health`) are implemented with `--json`, `--print`, `--no-color` flags, stdout/stderr separation, and stable exit codes.
- **Audit hardening**: rewrite now stops before writing when fact-preservation repair fails, short-text local-detector outputs stay compatible with the text-free cache contract, and CLI commands emit parseable stderr JSONL logs with richer `health --json` diagnostics.
- **Test coverage**: 121 unit, 92 integration, 45 E2E, and 16 smoke tests pass. All mocked/local paths work. No live network calls in default tests.
