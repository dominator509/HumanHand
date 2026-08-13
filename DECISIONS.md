# Architecture Decision Log

All lasting architecture decisions must be recorded here or in individual ADR files created from `.agent/templates/adr-template.md`. Coding agents must not make lasting architecture changes silently.

## Decision Table

| ADR | Date | Status | Owner | Decision | Linked Files |
|---|---:|---|---|---|---|
| ADR-0001 | 2026-07-05 | Accepted | Blueprint | Use Python 3.11 with `src/humanhand` package layout. | `ARCHITECTURE.md`, `ENVIRONMENT.md` |
| ADR-0002 | 2026-07-05 | Accepted | Blueprint | Use uv for development and pip-installed wheels for users. | `COMMANDS.md`, `DEPLOYMENT.md` |
| ADR-0003 | 2026-07-05 | Accepted | Blueprint | Provide Typer CLI only; no web server, GUI, TUI, SDK, or hosted API. | `SPEC-003`, `SPEC-004` |
| ADR-0004 | 2026-07-05 | Accepted | Blueprint | Keep domain layer pure and put all I/O/network/cache/logging in infra. | `ARCHITECTURE.md` |
| ADR-0005 | 2026-07-05 | Accepted | Blueprint | No primary database; optional SQLite cache stores detector score metadata only. | `SPEC-002`, `ARCHITECTURE.md` |
| ADR-0006 | 2026-07-05 | Accepted | Blueprint | Logs are structured JSONL to stderr only with no user text. | `OBSERVABILITY.md`, `SPEC-007` |
| ADR-0007 | 2026-07-05 | Accepted | Blueprint | Live LLM and detector tests are gated by `HUMANHAND_RUN_LIVE_E2E=1`. | `TESTING.md`, `COMMANDS.md` |
| ADR-0008 | 2026-07-05 | Accepted | Blueprint | Implementation must proceed through active ExecPlans, never directly from roadmap. | `AGENTS.md`, `.agent/PLANS.md` |

## ADR Index

Initial decisions are recorded in the table above. When implementation creates a decision with significant tradeoffs, add a new ADR file under `.agent/decisions/` or append a fully formed section here. If `.agent/decisions/` does not exist yet, create it only when the active ExecPlan permits documentation changes.

## Initial ADR Entries

### ADR-0001: Python 3.11 `src/` Layout

- Context: The product is a Python wheel installable as `humanhand` and requires Python 3.11.
- Decision: Use `src/humanhand` as the package root with absolute imports rooted at `humanhand`.
- Alternatives: Flat package layout; namespace package. Flat layout increases accidental local import risk.
- Consequences: Tests must install/run package through uv; scripts and mypy target `src` and `tests`.

### ADR-0002: uv Development, pip User Install

- Context: Development requires reproducible agent workflows; users install wheels.
- Decision: Use uv for dev commands and lock management; build wheels/sdists for pip install.
- Alternatives: Poetry, Hatch, pip-tools. These conflict with the provided package-manager constraint.
- Consequences: Scripts call uv and preflight requires uv.

### ADR-0003: CLI-Only Interface

- Context: Product scope excludes web UI, GUI, TUI, and HTTP API.
- Decision: Implement Typer CLI commands as the only user interaction surface.
- Alternatives: Web app or SDK. Both are non-goals.
- Consequences: API specs define CLI/service contracts rather than HTTP routes.

### ADR-0004: Pure Domain Boundary

- Context: Fact/style/scrub logic must be testable and safe.
- Decision: Domain contains no I/O, network, env, cache, or CLI imports.
- Alternatives: Put all logic in CLI or infra. That would make privacy and testing harder.
- Consequences: Application ports mediate side effects.

### ADR-0005: Optional Detector Cache Only

- Context: Product forbids primary database and persistent user-text storage.
- Decision: Optional SQLite cache stores detector score metadata keyed by hash/provider/model/schema only.
- Alternatives: Store prompts or full responses. Forbidden by privacy constraints.
- Consequences: Cache can be deleted to rollback; no migrations framework.

## Rules for Adding New Decisions

- Add an ADR when a decision affects architecture, dependencies, public CLI behavior, env vars, data schema, security posture, release process, or future maintenance.
- Include context, decision, alternatives considered, consequences, status, date, and owner.
- Link the ADR from this file.
- Update relevant specs and ExecPlans in the same change.
- Do not use ADRs to justify scope drift.

## ADR Template Reference

Use `.agent/templates/adr-template.md`.

## Pre-SLM ADR Index

The user-approved Pre-SLM architecture is recorded in:

- [ADR-001](.agent/adrs/ADR-001-persistent-local-project-state.md): selected local project state.
- [ADR-002](.agent/adrs/ADR-002-dual-clean-room-ingress-and-public-artifact-egress.md): dual ingress and public egress.
- [ADR-003](.agent/adrs/ADR-003-style-evidence-multi-representation-vault.md): exact style evidence.
- [ADR-004](.agent/adrs/ADR-004-controlled-parser-worker-processes.md): bounded parser workers.
- [ADR-005](.agent/adrs/ADR-005-application-layer-encryption-and-key-providers.md): encryption/key providers.
- [ADR-006](.agent/adrs/ADR-006-research-beacon-policy-firewall.md): Beacon policy firewall.
- [ADR-007](.agent/adrs/ADR-007-deterministic-lexical-normalization.md): lexical finalization.
- [ADR-008](.agent/adrs/ADR-008-slm-deferred-and-future-writer-contract.md): SLM deferred boundary.
