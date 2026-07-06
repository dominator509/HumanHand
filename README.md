# Human Hand

Human Hand is a Windows-first, privacy-preserving Python 3.11 CLI for rewriting AI-assisted source text into a supplied human writing style while preserving facts, stripping metadata, and supporting verification workflows.

AI generated drafts, rewritten into fully human writing without meta provenance leakage.

The repository is being built one ExecPlan at a time from the control plane in `.agent/`. EP-001 foundation is complete: the package installs, the CLI works, and all baseline validations pass.

## Goals

- Rewrite AI-assisted drafts into a target human style without losing facts.
- Keep user text local by default.
- Avoid telemetry, hosted services, background workers, and hidden persistence.
- Support verification paths for detector scoring, fact drift, and metadata cleanliness.
- Stay safe for coding-agent implementation through strict ExecPlans, specs, and validation gates.

## Current Status

- EP-001 foundation, EP-002 core domain, and EP-003 data/persistence are complete.
- `humanhand --help`, `humanhand --version`, and `humanhand health --json` are functional.
- `humanhand.domain` plus the new persistence layer now provide style fingerprints, fact diffing, metadata scrub, strict file I/O, cache configuration, and SQLite detector-score caching with no-text safeguards.
- Next: EP-004 API or service layer.

## Architecture Summary

Human Hand is intentionally a single-process CLI application. There is no web server, GUI, TUI, authentication layer, cloud database, telemetry pipeline, or hosted deployment target.

Planned layers:

- `src/humanhand/cli/`: Typer CLI definitions, stdout/stderr separation, JSON mode, and user-facing errors.
- `src/humanhand/application/`: Use-case orchestration for rewrite, verify, diff-facts, scrub, and health.
- `src/humanhand/domain/`: Pure business logic for style fingerprints, factual anchors, metadata scrub rules, and deterministic decisions.
- `src/humanhand/infra/`: Side effects including config, file I/O, HTTP integrations, detector adapters, cache, and structured logging.
- `tests/`: Unit, integration, E2E, and smoke coverage with live-network tests gated by environment variables.

Key invariants from the architecture:

- CLI-only and local-first.
- No user text in logs, cache, fixtures, or telemetry.
- Strict UTF-8 input handling and byte-clean UTF-8 output.
- Domain layer stays pure and free of I/O, CLI, logging, network, and environment imports.
- External LLM and detector integrations must stay behind validated infra adapters.

## Privacy And Safety

- User text must never be logged.
- Secrets must come from environment or ignored local config only.
- Output files must be metadata-free and written only to explicit output paths.
- Optional paid or remote services must never be required for local development or default test runs.
- Users remain responsible for the legal, ethical, academic, and professional use of generated or rewritten content.

## Repository Workflow

The repository is governed by:

- `AGENTS.md`
- `COMMANDS.md`
- `.agent/PLANS.md`
- `.agent/EXECUTION_RULES.md`
- the currently active ExecPlan in `.agent/execplans/`

The default local coding loop is:

1. Claude Code CLI performs the bulk implementation for one active ExecPlan.
2. Required validation runs at each milestone.
3. Codex audits and fixes issues before the next ExecPlan begins.

## Local Development

1. Use Python 3.11.
2. Use `uv` for development dependency management.
3. Read `AGENTS.md`, `COMMANDS.md`, and the active ExecPlan before editing.
4. Run `sh scripts/preflight.sh`.
5. Use the commands documented in `COMMANDS.md` for install, lint, typecheck, tests, build, and verification.

## Documentation Map

- [PROJECT_BRIEF.md](PROJECT_BRIEF.md): problem statement, target users, goals, and production definition
- [ARCHITECTURE.md](ARCHITECTURE.md): layer boundaries, runtime flow, data rules, and invariants
- [ENVIRONMENT.md](ENVIRONMENT.md): required tools, environment variables, and setup rules
- [TESTING.md](TESTING.md): test pyramid, gating rules, and validation matrix
- [DEPLOYMENT.md](DEPLOYMENT.md): artifact install and release candidate flow
- [RELEASE.md](RELEASE.md): release checklist and approval boundaries
- [REPO_BRIEF.md](REPO_BRIEF.md): compact Obsidian/Serena/Codex/Claude repo orientation

## Git And GitHub

This repository is intended to work cleanly with local Git plus a GitHub remote named `origin`, so Codex sidebar commit/push actions have a normal repository to operate on. Local-only tool state such as caches, transient agent state, and workspace-specific Obsidian/Serena files is excluded via `.gitignore`.
