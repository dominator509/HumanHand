# Contributing

## Setup

1. Read `AGENTS.md`, `COMMANDS.md`, and `.agent/PLANS.md`.
2. Install required tools from `ENVIRONMENT.md`.
3. Run `sh scripts/preflight.sh`.
4. Execute the active ExecPlan only.
5. Use uv for development commands.

## Branch Rules

- One branch/session per ExecPlan.
- Do not mix unrelated ExecPlans.
- Do not implement directly from `ROADMAP.md`.
- Do not include `.env`, `.cache/`, virtual environments, build artifacts, secrets, or real user text.

## Coding Standards

- Python 3.11.
- Absolute imports rooted at `humanhand`.
- Domain layer must be pure.
- CLI layer parses and wires only.
- Infra layer owns I/O, network, cache, config, and logging.
- Type annotations required for public functions.
- No global mutable state in domain.
- No `sys.path` manipulation in `src/`.

## Test Requirements

- Add tests with every behavior change.
- Unit tests first for domain logic.
- Integration tests for files/cache/HTTP.
- E2E tests for CLI contracts.
- Live tests must be gated.
- Run required validation from the active ExecPlan.

## Documentation Requirements

Update docs when changing:

- CLI commands or flags.
- Env vars or config.
- Output format.
- Log fields.
- Cache schema.
- Security/privacy behavior.
- Release or deployment behavior.

## Commit Guidance

This blueprint does not require a specific commit format. Commits should be small, explain the ExecPlan, and avoid mixing unrelated changes. Coding agents must not commit unless explicitly asked by the user.

## Pull Request Checklist

- [ ] Active ExecPlan complete.
- [ ] Specs updated if behavior changed.
- [ ] Tests added/updated.
- [ ] `sh scripts/verify.sh` passes.
- [ ] Security/privacy checks pass.
- [ ] `git diff --name-only` reviewed against Files to Change.
- [ ] Extra changed files justified.
- [ ] No secrets or user text.
- [ ] Docs updated.

## Code Review Checklist

- Domain purity preserved.
- No scope drift.
- CLI contracts stable.
- Output scrub guaranteed before write.
- Logs/cache contain no user text.
- External calls have timeout/retry/schema validation.
- Tests cover failure modes.
- Production-readiness implications documented.

## Agent-Specific Contribution Rules

- Continue by default.
- Stop only under STOP conditions.
- Use only commands from `COMMANDS.md`.
- Do not invent APIs or env vars.
- Apply bounded retry.
- Update ExecPlan progress as work proceeds.
- Write `.agent/state/last-result.env` as final file operation.
- Final response must include changed files, commands/results, decisions, risks, and acceptance status.

## Pre-SLM Contributions

Pre-SLM work follows EP-011 through EP-019 in order. Add or update a specification and
ADR before introducing a new persistence, privacy, parser, exporter, research, or
lexical contract. Keep source/style lanes separate, keep the public artifact boundary
clean, and do not add any model/training/runtime path before the final gate.
