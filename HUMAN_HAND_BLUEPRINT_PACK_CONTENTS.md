FILE: PROJECT_BRIEF.md

```text
# Project Brief: Human Hand

## Project Name

Human Hand

## Problem Statement

Human Hand is a Windows-first, open-source, single-user Python CLI application that rewrites an AI-assisted source text file into prose that preserves the source facts while matching a supplied human writing sample. The product must be privacy-preserving, deterministic by default, reproducible on Windows 10/11, and safe for coding-agent implementation through ordered ExecPlans.

The primary risk is not building a text transformer. The primary risk is building one that silently drifts facts, leaks user text, writes hidden metadata, logs secrets, depends on unavailable paid services, or lets implementation agents invent behavior. This blueprint prevents those risks through strict repository rules, specs, commands, validation gates, and production-readiness checklists.

## Target Users

- Technical writers and authors who draft with AI assistance and want final prose in their own style.
- Students and academics who need to rewrite AI-assisted drafts into their own voice while remaining responsible for their ethical and institutional obligations.
- Local Windows 10+ PC users who want a privacy-first writing workflow without telemetry or cloud storage.
- Developers and power users comfortable with command-line tools.
- Users who may connect the CLI to OpenAI, Azure OpenAI-compatible endpoints, OpenRouter, llama.cpp server, vLLM, Ollama-compatible endpoints, LM Studio, or similar OpenAI-compatible model servers.

## Primary User Outcomes

- Provide an AI-written source file or stdin and a human-written style sample file.
- Receive a rewritten plain UTF-8 output file in the target style.
- Preserve source facts with no hallucination, omission, drift, or information loss.
- Strip metadata, provenance markers, hidden JSON, BOMs, model tags, and telemetry fields from outputs.
- Run `humanhand verify <output>` with configured detector providers or a local heuristic fallback.
- Run `humanhand diff-facts <ai-source> <output>` to detect factual drift.
- Run `humanhand scrub --audit <file>` to audit or clean metadata-like markers.
- Install on a clean Windows 10/11 machine with `pip install humanhand` or `pip install dist/humanhand-*.whl`.
- Keep user text out of logs and persistent storage.

## Business Goals

- Open-source, no paywall, no telemetry, and no hosted SaaS requirement.
- Maintainable by coding agents through `.agent/execplans/`.
- Extensible detector integration architecture without requiring paid detector accounts for local development.
- Manual release workflow with no automatic PyPI publish without maintainer approval.

## Technical Goals

- Python 3.11, Typer CLI, uv development workflow, wheel and source distribution.
- Single-process CLI runtime; no web server, background worker, GUI, TUI, authentication, roles, sessions, or cloud database.
- Pure domain layer with no I/O, network, CLI, or infra imports.
- Infra layer owns file I/O, HTTP, detector clients, optional SQLite detector-score cache, and redaction-safe logging.
- Strict UTF-8 input, no BOM, LF output, no metadata, exactly one trailing newline.
- Deterministic-by-default behavior with optional `HUMANHAND_SEED`.
- External network calls gated by configuration, timeout, retries, schema validation, HTTPS enforcement, and redaction.

## Out of Scope

- Web UI, GUI, TUI, HTTP API, public hosted service, or multi-user deployment.
- Authentication, authorization roles, accounts, sessions, server-side permissions, or server storage.
- Persistent user-text history, cloud database, telemetry, remote metrics, dashboards, traces, or phone-home behavior.
- Automated submission to academic or professional platforms.
- Fine-tuning model weights inside this repository.
- Auto-publishing to PyPI from CI.
- New features outside the active ExecPlan.
- Implementation directly from `ROADMAP.md`.

## Success Metrics

- `scripts/verify.sh` exits 0 on Windows and Ubuntu CI after EP-007.
- `scripts/production-readiness-check.sh` exits 0 after EP-010.
- Unit, integration, E2E, smoke, security, dependency audit, lint, format, typecheck, and build checks pass.
- Test coverage is at least 85% after EP-007.
- Mock smoke test completes under 30 seconds; at least 95% of mock runs complete under 30 seconds.
- `humanhand --help` and `humanhand --version` produce the first stdout byte within 100 ms in normal local conditions.
- No test, fixture, log, cache row, or committed file contains real user text, prompts, LLM responses, detector responses with source text, or secrets.
- Detector cache stores only score metadata keyed by text hash/provider/model/schema version.

## Production Readiness Definition

Production readiness means all ExecPlans EP-000 through EP-010 are complete, all linked specs are satisfied, `scripts/verify.sh` exits 0, `scripts/production-readiness-check.sh` exits 0, `scripts/loop.sh` prints `build: complete`, packaging artifacts install cleanly, post-install smoke tests pass, security/privacy gates pass, rollback instructions are documented, and all remaining risks are either resolved or explicitly accepted in the active ExecPlan and release notes.
```

FILE: ASSUMPTIONS.md

```text
# Assumptions

These assumptions were made while generating the blueprint pack. Coding agents must verify them from repository files before relying on them. If an assumption is wrong, update this file, the active ExecPlan Decision Log, and any affected specs before editing implementation files.

| ID | Assumption | Reason | Risk if Wrong | How to Verify | Blocks Implementation? |
|---|---|---|---|---|---|
| A-001 | The repository is greenfield except for this blueprint pack. | Input says selected status is Greenfield repository. | Existing code could be overwritten or ignored. | Run `find . -maxdepth 3 -type f | sort` during EP-000 or EP-001. | No, unless existing user code conflicts. |
| A-002 | Python package import root will be `humanhand` under `src/humanhand`. | Required wheel name is `humanhand`; src layout reduces import ambiguity. | Imports or packaging metadata may differ. | Inspect `pyproject.toml` after EP-001. | No. Update architecture if changed. |
| A-003 | Development package manager is uv; end-user install uses pip. | Provided stack requires uv for development and pip for wheel install. | Commands may fail on machines without uv. | Run `uv --version` in preflight. | Yes for development workflows; install uv before continuing. |
| A-004 | CLI framework is Typer. | Provided frontend requires Typer-based CLI. | CLI tests and command contracts would not match. | Inspect dependencies and `src/humanhand/cli/app.py` after EP-001/EP-004. | Yes if a different CLI framework is chosen without an ADR. |
| A-005 | OpenAI-compatible LLM calls can be implemented with the OpenAI Python SDK plus `base_url`, or with `httpx` if compatibility requires it. | Input calls for OpenAI-compatible endpoints and OpenAI Python SDK. | SDK API changes could break code. | Verify SDK docs/version from locked dependencies and tests before use. | No; choose the smallest verified client path and document it. |
| A-006 | Optional detector providers are disabled unless their API keys are present. | Paid detector APIs are optional and tests must pass without keys. | Accidental live calls or failing local tests. | Run tests with no detector env vars; verify mocks. | Yes if local fallback is missing. |
| A-007 | Local heuristic verification is acceptable as a fallback score, not a guarantee of detector accuracy. | Product requires fallback when paid keys are absent. | Users may overtrust heuristic results. | README and CLI output must label heuristic mode clearly. | No. |
| A-008 | No primary database is required. SQLite is optional cache only. | Input forbids primary database and allows optional local SQLite cache. | Overbuilding migrations or persistent user data. | Inspect `src/humanhand/infra/cache.py` and specs. | No. |
| A-009 | Cache directory default is `.cache/humanhand/cache.db` relative to repository/current working directory for development, overrideable by env/config. | Input names `.cache/humanhand/cache.db`. | User may expect OS user cache directory. | Confirm in SPEC-002 and ENVIRONMENT before implementation. | No, but changing requires ADR. |
| A-010 | Scripts are POSIX `sh` for agent consistency, even on Windows. | Required scripts must start with `#!/usr/bin/env sh`. | Windows users may lack a POSIX shell. | Document Git Bash/WSL/CI usage; keep Python commands behind scripts. | No. |
| A-011 | `.env` may be loaded for local development, but must be ignored and never committed. | Input says env/config and `.env` ignored. | Secrets could leak if `.env` is tracked. | Verify `.gitignore` in EP-001. | Yes if `.env` is tracked. |
| A-012 | Live E2E tests are skipped unless `HUMANHAND_RUN_LIVE_E2E=1`. | Input explicitly gates live tests. | CI may hit real network or fail without keys. | Inspect pytest markers and CI env. | Yes if live tests run by default. |
| A-013 | `HUMANHAND_MAX_CHARS` defaults to 200000. | Input specifies default cap. | Large input performance or memory behavior could differ. | Verify config tests. | No. |
| A-014 | User text includes source text, style sample, prompt content, generated output, and raw LLM/detector responses. | Privacy requirements include all user-provided and generated prose. | Sensitive text could be logged or cached. | Security tests and redaction tests. | Yes if logging/caching stores text. |
| A-015 | Turnitin AI detector integration may not provide a public self-serve API for all users; implementation must be pluggable and optionally unavailable. | Detector availability can vary by commercial account. | Agents may invent unsupported API endpoints. | Verify provider docs and only implement documented or mocked adapter contracts. | No; unavailable providers must fail clearly or remain stubbed behind tests. |
| A-016 | MCP connectivity is future integration scope, not a first-release runtime requirement. | Input lists MCP connectivity without concrete contracts. | Agents could overbuild an MCP server/client. | Keep MCP as documented future extension unless an ExecPlan defines it. | No. |
| A-017 | Human Hand does not guarantee academic-integrity compliance; users bear responsibility. | Input requires legal and ethical responsibility statement. | Misleading user messaging. | README, CLI help, and docs must include the disclaimer. | No. |
```

FILE: AGENTS.md

```text
# AGENTS.md

## 1. Mission

Coding agents exist to implement Human Hand from this repository, one ExecPlan at a time, with minimal drift, no hallucinated APIs, no unsafe data handling, and no vague approval gates. Human Hand is a Windows-first, privacy-preserving Python 3.11 CLI that rewrites AI-assisted source text into a supplied human style while preserving facts, stripping metadata, and supporting verification.

Do not ask the user for next steps. Proceed autonomously through the active ExecPlan unless a STOP condition applies.

## 2. Source-of-Truth Priority

When instructions conflict, apply this order:

1. Current user instruction in the active session.
2. `AGENTS.md`.
3. The active ExecPlan in `.agent/execplans/`.
4. Existing repository code and tests.
5. `ARCHITECTURE.md`.
6. Relevant spec in `.agent/specs/`.
7. `ROADMAP.md`.

`ROADMAP.md` is strategic only. Do not implement directly from it.

## 3. Required Workflow

For every implementation session:

1. Read `AGENTS.md`.
2. Read `COMMANDS.md`.
3. Read `.agent/PLANS.md`.
4. Read `.agent/EXECUTION_RULES.md`.
5. Read the active ExecPlan completely.
6. Read all files listed in the active ExecPlan under Files to Read First.
7. Run `sh scripts/preflight.sh` from repository root.
8. Complete milestones in the order listed.
9. Validate after every milestone using the command named in that milestone.
10. Update the active ExecPlan Progress checkbox, Surprises & Discoveries, Decision Log, and Outcomes & Retrospective as work proceeds.
11. Continue autonomously until the ExecPlan is complete or a STOP condition applies.
12. Run the final validation commands required by the ExecPlan.
13. Run `git diff --name-only` and compare changed files with Files to Change.
14. Justify any extra changed file in the ExecPlan Decision Log.
15. Write `.agent/state/last-result.env` as the final file operation of the session.
16. Provide the required final response.

## 4. STOP Conditions

Stop only when one of these applies:

- A required secret, credential, paid service account, detector account, or external endpoint is missing and the active ExecPlan requires a live call that cannot be mocked or skipped.
- The next action may destroy, overwrite, delete, corrupt, migrate, publish, disclose, or irreversibly alter user data, production data, release artifacts, secrets, git history, or external services.
- The task requires legal, security, financial, academic-integrity, or compliance judgment not already specified in this repository.
- A materially different user-visible behavior choice is required and cannot be resolved by the active spec, architecture, or smallest reversible implementation.
- Required validation commands cannot run after documented recovery attempts using the anti-fixation rule.
- Production deployment, PyPI publishing, release tagging, or irreversible migration is requested without explicit maintainer permission.
- Repository contents materially contradict the active ExecPlan and continuing would overwrite existing user work.

When stopping, report exact blocker, evidence from file or terminal output, smallest decision needed, and recommended default.

## 5. Anti-Drift Rules

- Work only on the active ExecPlan.
- Do not jump to another ExecPlan.
- Do not implement directly from `ROADMAP.md`.
- Do not add features outside the active ExecPlan.
- Do not perform broad refactors, dependency swaps, file reorganizations, styling rewrites, or unrelated cleanup.
- Do not change public CLI flags, environment variables, cache schema, output format, log fields, or package APIs unless the active ExecPlan explicitly says to.
- Do not print generated prose to stdout unless an explicit `--print` flag is used.
- Do not write to input files. Only write to `--out` or a documented default output path.
- Any extra changed file must be justified in the active ExecPlan Decision Log.

## 6. Anti-Hallucination Rules

- Do not invent package APIs, command names, environment variables, database tables, CLI flags, routes, config keys, detector endpoints, model names, or file paths.
- Confirm names by reading repository files before using them.
- Use only commands listed in `COMMANDS.md`.
- If a command is missing or stale, update `COMMANDS.md` first with evidence from repository files, then use it.
- Before adding a dependency, inspect existing dependencies and prove the functionality cannot be built with existing tools.
- When creating a new public contract, add or update the relevant spec and tests in the same ExecPlan if the plan permits it.
- Record assumptions in the active ExecPlan Decision Log and `ASSUMPTIONS.md` when they affect implementation.

## 7. Anti-Fixation Rules

For each failing validation command:

1. First failure: read the exact error, identify the likely cause, and make the smallest targeted fix.
2. Second same-root failure: run or create a narrower diagnostic that isolates the failure; avoid broad rewrites.
3. Third same-root failure: stop the current approach, record failed hypotheses in Surprises & Discoveries, choose a simpler implementation path if safe, and continue. If no safe simpler path exists, use a STOP condition.

Never patch blindly around the same error indefinitely.

## 8. Dependency Rules

- Use Python 3.11.
- Use uv for development dependency management.
- End-user install must work through pip from a built wheel.
- Domain code must not import Typer, httpx, OpenAI SDK, sqlite3, pathlib file I/O helpers, logging infra, or CLI modules.
- Infra code may import HTTP, OpenAI-compatible SDKs, sqlite3, file I/O, config, logging, and domain/application ports.
- CLI code may parse arguments and wire services but must not contain core business logic.
- No circular imports.
- No `sys.path` manipulation in `src/`.
- No dependency may be added without updating `pyproject.toml`, lock files, relevant docs, and Decision Log.

## 9. File Creation Rules

- Use repository-local files only.
- Create files exactly where the active ExecPlan lists them.
- Use absolute imports rooted at `humanhand` for Python implementation.
- Keep generated output byte-clean UTF-8, LF newlines, no BOM, no hidden metadata, and exactly one trailing newline.
- Create `.agent/state/last-result.env` as the final file operation of each agent session.
- Do not commit `.env`, `.cache/`, virtual environments, build artifacts except documented release artifacts, or detector/LLM responses containing user text.

## 10. Testing Rules

- Unit tests must never hit real network.
- Integration tests must mock external HTTP with respx/httpx or equivalent.
- Live E2E tests must be skipped unless `HUMANHAND_RUN_LIVE_E2E=1`.
- Every feature must have tests for success, invalid input, privacy/logging, and relevant failure modes.
- Run the milestone validation command after each milestone.
- Run full verification before completing an ExecPlan when required.
- Do not weaken tests to make implementation pass unless the active spec is wrong; record and justify any test change.

## 11. Documentation Update Rules

- Update the active ExecPlan as work proceeds.
- Update specs when behavior contracts change.
- Update `COMMANDS.md` before using new commands.
- Update `ARCHITECTURE.md` when layer boundaries, imports, data flow, or integrations change.
- Update `ENVIRONMENT.md` when env vars or config behavior changes.
- Update `SECURITY.md`, `OBSERVABILITY.md`, or `OPERATIONS.md` when their rules change.
- Add ADRs for architectural decisions with lasting consequences.

## 12. Security Rules

- Never commit secrets or sample API keys.
- Read API keys only from environment or ignored `.env` files.
- Always redact secrets in logs and errors.
- Never log user text, prompts, style samples, AI source text, generated output, or raw LLM/detector responses.
- Logs may include only lengths, sha256 prefixes, provider/model names, endpoint host, timing, attempts, cache hit state, and redacted errors.
- Reject UTF-8 BOM input.
- Reject insecure HTTP endpoints unless `HUMANHAND_ALLOW_INSECURE=1`.
- Validate all LLM and detector responses against schemas before use.
- Store only detector score metadata in cache; never store text.
- Run Bandit, pip-audit, and secret-pattern scans before production readiness.

## 13. Production Data Rules

- Human Hand has no production database and no hosted production runtime.
- User files are production data from the user's perspective.
- Never overwrite user input files.
- Never delete user files.
- Never submit text to a third-party endpoint unless the user configured that endpoint for the command.
- Optional cache must be compact, local, and free of user text.
- Cache file permissions should be `0600` where supported.

## 14. Definition of Done

An ExecPlan is done only when:

- All milestones are complete in order.
- All acceptance criteria pass.
- Required validation commands pass.
- The active ExecPlan Progress, Decision Log, Surprises & Discoveries, and Outcomes & Retrospective are updated.
- `git diff --name-only` was reviewed against Files to Change.
- Extra changed files are justified in the Decision Log.
- No secrets, user text logs, hidden metadata, or out-of-scope features were introduced.
- `.agent/state/last-result.env` was written as the final file operation.

## 15. Final Response Requirements

The final response for an execution session must include:

- ExecPlan id and final status.
- Milestones completed.
- Files changed.
- Commands run and results.
- Acceptance criteria status.
- Decisions made.
- Assumptions confirmed or changed.
- Remaining risks.
- Production-readiness status where applicable.
- Confirmation that `.agent/state/last-result.env` was written.
```

FILE: COMMANDS.md

```text
# COMMANDS.md

Coding agents must not invent commands. If a command is missing, update this file first with evidence from the repository.

## Working Directory Rule

Run all commands from the repository root. The repository root is the directory containing `AGENTS.md`, `COMMANDS.md`, and `scripts/`.

## Package Manager Rule

Use `uv` for development. End users install the built wheel with `pip`. Do not replace uv with pipenv, poetry, hatch, npm, pnpm, conda, or custom shell wrappers unless an active ExecPlan and ADR explicitly require it.

## Allowed Commands

| Purpose | Command | Expected Success Output |
|---|---|---|
| Preflight | `sh scripts/preflight.sh` | `preflight: ok` |
| Install dependencies | `sh scripts/install.sh` | `install: ok` |
| Lint | `sh scripts/lint.sh` | `lint: ok` |
| Format check | `sh scripts/format-check.sh` | `format check: ok` |
| Typecheck | `sh scripts/typecheck.sh` | `typecheck: ok` |
| Unit tests | `sh scripts/test-unit.sh` | `unit tests: ok` |
| Integration tests | `sh scripts/test-integration.sh` | `integration tests: ok` |
| E2E/acceptance tests | `sh scripts/test-e2e.sh` | `e2e tests: ok` |
| Build wheel/sdist | `sh scripts/build.sh` | `build: ok` |
| Security check | `sh scripts/security-check.sh` | `security check: ok` |
| Dependency audit | `sh scripts/dependency-audit.sh` | `dependency audit: ok` |
| Smoke test | `sh scripts/smoke-test.sh` | `smoke test: ok` |
| Full verification | `sh scripts/verify.sh` | `verify: ok` |
| Production readiness | `sh scripts/production-readiness-check.sh` | `production readiness: ok` |
| Agent loop status | `sh scripts/loop.sh` | `build: complete` after production readiness |
| Show changed files | `git diff --name-only` | List of changed files only |
| Show full diff | `git diff -- .` | Human-reviewable diff |
| Local CLI help | `uv run humanhand --help` | Typer help text on stdout |
| Local CLI version | `uv run humanhand --version` | Version text on stdout |
| Local rewrite command | `uv run humanhand rewrite --source <source.txt> --style <style.txt> --out <output.txt>` | Status on stderr; output file created |
| Local verify command | `uv run humanhand verify <output.txt>` | Human-likelihood result on stdout |
| Local fact diff command | `uv run humanhand diff-facts <source.txt> <output.txt>` | Drift result on stdout |
| Local scrub audit command | `uv run humanhand scrub --audit <file.txt>` | Metadata audit result on stdout |
| Local cache setup | No standalone setup. Cache is created lazily by `humanhand verify` when enabled. | Not applicable |
| Migrations | No migration command. Cache schema is created/updated lazily and must be backward-compatible. | Not applicable |

## Command Availability by Phase

- Before EP-001, `sh scripts/preflight.sh` must pass after this blueprint pack is placed in the repository. Other scripts may fail clearly because `pyproject.toml` does not exist yet.
- After EP-001, install, lint, format check, typecheck, unit tests, build, and basic smoke commands must pass.
- After EP-004, CLI command smoke tests must pass on mocked/local fallback paths.
- After EP-007, `sh scripts/verify.sh` must pass.
- After EP-010, `sh scripts/production-readiness-check.sh` and `sh scripts/loop.sh` must pass.

## Environment-Gated Commands

| Purpose | Command | Gate |
|---|---|---|
| Live LLM E2E | `HUMANHAND_RUN_LIVE_E2E=1 sh scripts/test-e2e.sh` | Requires explicit user-provided endpoint/model/key or local compatible server. |
| Insecure local HTTP endpoint | `HUMANHAND_ALLOW_INSECURE=1 ...` | Allowed only for local development endpoints such as localhost. |
| Detector live E2E | `HUMANHAND_RUN_LIVE_E2E=1 HUMANHAND_DETECTOR_PROVIDER=<provider> ...` | Requires explicit provider key and account. |

## Forbidden Commands

Do not run these unless the current user explicitly authorizes them in the same session and the active ExecPlan allows them:

- `git reset --hard`, `git clean -fdx`, or destructive git history rewrites.
- `rm -rf` against repository directories, user directories, cache directories, or output paths not created by the current test.
- `twine upload`, `uv publish`, PyPI publishing, GitHub release creation, or release tagging.
- Commands that submit user text to external services without explicit endpoint configuration.
- Commands that alter global Python, system package managers, registry settings, or system-level certificate stores.
- Commands not listed in this file.

## Recovery Instructions

When a command fails:

1. Copy the exact command and failure summary into the active ExecPlan Surprises & Discoveries.
2. Apply the anti-fixation rule from `AGENTS.md`.
3. Do not switch to a different command unless this file is updated first with repository evidence.
4. Do not weaken validation to pass.
5. If the command is stale because repository structure changed, update this file, scripts, and the active ExecPlan Decision Log in the same change.
```

FILE: ARCHITECTURE.md

```text
# Architecture

## Purpose

This document defines the intended architecture for Human Hand and the concrete boundaries coding agents must preserve. It is a control document, not an aspirational overview. If implementation needs to violate one of these rules, add an ADR and update the active ExecPlan before editing code.

## System Overview

Human Hand is a single-process Python 3.11 CLI. It reads source text and style sample text, builds a style-and-fact-preserving rewrite request, optionally calls a configured OpenAI-compatible LLM endpoint, scrubs metadata, writes byte-clean UTF-8 output, and provides verification commands for detector scoring, fact drift, and metadata cleanliness.

There is no web server, no GUI, no TUI, no authentication, no cloud database, no background worker, no telemetry, and no remote metrics.

## Intended Repository Map

| Path | Purpose |
|---|---|
| `src/humanhand/__init__.py` | Package metadata exports only. |
| `src/humanhand/__main__.py` | Module entrypoint delegating to CLI app. |
| `src/humanhand/cli/app.py` | Typer app, command definitions, argument parsing, stdout/stderr separation. |
| `src/humanhand/cli/output.py` | CLI result rendering, JSON mode, no-color behavior. |
| `src/humanhand/application/` | Use-case orchestration and ports. No direct file or network I/O except through injected infra interfaces. |
| `src/humanhand/domain/` | Pure business logic: style fingerprinting, fact extraction/diff scoring, metadata scrub rules, prompt building, repair-loop decisions. |
| `src/humanhand/infra/config.py` | Env/config loading and validation. |
| `src/humanhand/infra/files.py` | Strict UTF-8 read/write, BOM rejection, LF normalization, safe output paths. |
| `src/humanhand/infra/llm.py` | OpenAI-compatible client, schema response validation, retries/timeouts, HTTPS enforcement. |
| `src/humanhand/infra/detectors/` | Detector provider adapters and local heuristic fallback. |
| `src/humanhand/infra/cache.py` | Optional SQLite detector-score cache; stores no text. |
| `src/humanhand/infra/logging.py` | Structured JSONL logs to stderr, redaction, counters. |
| `tests/unit/` | Pure and fast unit tests, no network. |
| `tests/integration/` | Integration tests with mocked HTTP and temporary filesystem. |
| `tests/e2e/` | CLI acceptance tests; live tests gated. |
| `tests/smoke/` | Fast smoke tests under 30 seconds on mocks. |
| `.agent/` | Agent control plane, specs, ExecPlans, prompts, checklists, templates. |
| `scripts/` | Only allowed validation/build commands. |
| `.github/workflows/` | CI and manual release workflows after EP-001/EP-009. |

## Layer Responsibilities

### Domain Layer

- Owns pure transformations and deterministic decisions.
- Accepts and returns strings, dataclasses, enums, and plain Python structures.
- May use only standard-library pure modules such as `dataclasses`, `hashlib`, `re`, `difflib`, `json`, `math`, `statistics`, and `typing`.
- Must not read or write files, call network, access environment variables, log, import Typer/httpx/OpenAI/sqlite3, or depend on wall-clock time except through injected values.

### Application Layer

- Owns use-case orchestration: rewrite, verify, diff-facts, scrub, health.
- Defines ports/protocols for LLM client, detector client, cache, file reader/writer, and logger.
- May import domain modules and typing abstractions.
- Must not call concrete HTTP clients, sqlite3, or Typer directly.

### Infra Layer

- Owns all side effects: files, environment, HTTP, retries, timeouts, cache, logging, detector provider implementations.
- May implement application ports.
- Must validate external responses before returning data to application/domain.
- Must not contain core style/fact/scrub business rules except mechanical encoding and transport validation.

### CLI Layer

- Owns Typer app, command names, flags, stdout/stderr separation, JSON mode, exit codes, and user-facing errors.
- Wires config, infra clients, and application use cases.
- Must not implement core business rules directly.

## Dependency Rules

- `humanhand.cli` may import `humanhand.application`, `humanhand.infra`, and `humanhand.domain` only for type/result rendering when necessary.
- `humanhand.application` may import `humanhand.domain` and application-local ports.
- `humanhand.domain` must not import `humanhand.application`, `humanhand.infra`, or `humanhand.cli`.
- `humanhand.infra` may import `humanhand.application` ports and `humanhand.domain` data objects only when implementing side-effect boundaries.
- Tests may import any layer but must respect no-real-network rules.
- No circular imports.
- No `sys.path` manipulation in `src/`.
- Use absolute imports rooted at `humanhand`.

## Runtime Flow

### Rewrite Command

1. CLI parses `humanhand rewrite --source <path|-> --style <path> --out <path> [--json] [--print]`.
2. CLI loads config from env/.env without logging secrets.
3. Infra reads source/style as strict UTF-8 and rejects BOM or empty input.
4. Application validates input lengths against `HUMANHAND_MAX_CHARS`.
5. Domain builds style fingerprint, factual anchors, and rewrite prompt contract.
6. Infra LLM client calls configured OpenAI-compatible endpoint or a configured local compatible server.
7. Infra validates LLM response schema.
8. Domain compares facts and decides whether repair loop is needed.
9. Domain/infra scrub metadata from final text.
10. Infra writes LF-normalized UTF-8 output to `--out` with exactly one trailing newline.
11. CLI prints a concise result to stdout or JSON-only stdout; logs/counters go to stderr.

### Verify Command

1. CLI parses `humanhand verify <output> [--provider <name>] [--json]`.
2. Infra reads output as strict UTF-8.
3. Application hashes text and checks optional cache if enabled.
4. Detector adapter is selected by provider/config. If no live provider is configured, local heuristic fallback is used.
5. Detector response is schema validated and cached without storing text.
6. CLI prints human-likelihood result.

### Diff-Facts Command

1. CLI reads source and output as strict UTF-8.
2. Domain extracts factual anchors and compares coverage, conflicts, omissions, and additions.
3. CLI prints summary and machine-friendly JSON when requested.

### Scrub Command

1. CLI reads file as strict UTF-8.
2. Domain audits or removes metadata-like markers.
3. If `--audit`, no output file is modified.
4. If writing, only write to `--out` or documented default; never overwrite input unless a spec later explicitly allows it, which this blueprint does not.

## Data Flow

- User text enters through file paths/stdin or configured external endpoint responses.
- User text exists in process memory only for the duration of a command.
- User text must not be written to logs, cache, telemetry, fixtures, or persistent history.
- Output text is written only to the user-requested output path.
- Hashes use SHA-256; logs and cache keys may store prefixes or full hashes but never source text.

## State Management Rules

- No global mutable state in domain.
- Config is immutable after load for a command.
- Cache connections are scoped to command execution and closed.
- Counters are local to one command and emitted to stderr at command end.
- Determinism uses explicit seed from `HUMANHAND_SEED` or default config, never hidden global randomness.

## Persistence Boundaries

- No primary database.
- Optional SQLite cache may store only detector score records: text hash, provider, model, schema version, score fields, timestamp, cache metadata, and compact raw provider score data that contains no user text.
- Cache schema must include a schema version and be backward-compatible where practical.
- Cache file should be `0600` where supported.
- No migration framework is required; cache schema creation/update is lazy and safe.

## External Integration Boundaries

- LLM and detector integrations must be behind application ports.
- External calls must use timeout default 30 seconds.
- Retry up to 3 times on network errors and 5xx responses with exponential backoff.
- Do not retry validation errors, 4xx authentication errors, policy refusals, or unsafe endpoint errors.
- Reject non-HTTPS external endpoints unless `HUMANHAND_ALLOW_INSECURE=1`; allow localhost HTTP only when explicitly enabled.
- Do not implement undocumented detector endpoints. If a provider contract is unknown, create a clear adapter interface and tests with mocks, then stop live implementation behind missing-docs Decision Log entry.

## Security Boundaries

- Trust boundaries: CLI args, file contents, env vars, LLM responses, detector responses, cache contents, and stdout/stderr consumers.
- Validate at every trust boundary.
- Redact secrets and user text before logging.
- Never include provenance headers, model names, prompts, or hidden JSON in generated output.
- Never write to input files.
- Never run live network tests by default.

## Validation Boundaries

- CLI validates required flags, paths, mutually exclusive flags, JSON mode, and empty input.
- Infra validates UTF-8, BOM absence, path safety, endpoint security, response schema, cache schema.
- Domain validates semantic contracts: factual anchor preservation, metadata-free output, style fingerprint inputs, detector score shape.

## Error Handling Boundaries

- Domain returns typed result objects or raises domain-specific exceptions only for invalid pure inputs.
- Infra wraps side-effect failures into application-level errors without leaking secrets/user text.
- CLI maps errors to stable exit codes and friendly one-line messages.
- JSON mode prints JSON-only stdout. Logs still go to stderr.

## Observability Boundaries

- Structured JSONL logs go to stderr only.
- Human-facing results go to stdout only.
- Required log fields: timestamp, level, event, message, elapsed_ms, model, endpoint_host, input_length, output_length, sha256_prefix, cache_hit, attempt, retry_reason.
- Missing fields must use null or be omitted by documented rule; do not invent new fields without updating SPEC-007.
- No remote metrics, dashboards, tracing, or telemetry.

## Architectural Invariants

- CLI-only product.
- Single-process runtime.
- Domain layer is pure.
- No user text in logs/cache/fixtures.
- Strict UTF-8 input and byte-clean UTF-8 output.
- Optional paid services must not be required for local tests.
- Commands are source-controlled in `COMMANDS.md`.
- Implementation proceeds only through active ExecPlans.

## Forbidden Changes

- Adding a web server, HTTP API, GUI, TUI, background worker, auth system, cloud database, telemetry, remote metrics, or hosted deployment.
- Persisting source/style/output text except requested output file.
- Logging prompts or model responses.
- Auto-submitting to academic/professional platforms.
- Changing package manager without ADR.
- Auto-publishing releases from CI.

## How to Add a New Feature

1. Add or update a spec under `.agent/specs/`.
2. Add or update an ExecPlan under `.agent/execplans/`.
3. Ensure Files to Change is explicit.
4. Update `COMMANDS.md` if new validation commands are needed.
5. Implement through the active ExecPlan only.
6. Add tests at the lowest layer first.
7. Run validation and update docs.

## How to Add a New Dependency

1. Check existing dependencies in `pyproject.toml` and lock file.
2. Prefer standard library or existing dependencies.
3. If necessary, add the smallest stable package with a compatible license.
4. Update `pyproject.toml`, lock file, `ENVIRONMENT.md` if config changes, and `DECISIONS.md` if the dependency affects architecture.
5. Run install, audit, lint, tests, and build.

## How to Modify Data Schema

Only the optional detector-score cache has a schema.

1. Update SPEC-002 first.
2. Keep user text out of schema.
3. Add or increment schema version.
4. Implement lazy, backward-compatible schema creation/update.
5. Add integration tests for empty cache, existing old schema, cache hit, cache miss, and no-text persistence.
6. Document rollback as deleting the cache file.

## How to Add a New Integration

1. Add provider contract tests with mocked HTTP.
2. Implement provider adapter under `src/humanhand/infra/detectors/` or LLM adapter under `src/humanhand/infra/`.
3. Validate response schema.
4. Add env vars to `ENVIRONMENT.md`.
5. Add redaction rules.
6. Add live test marker skipped by default.
7. Do not add undocumented endpoints.

## Architecture Review Checklist

- Does domain remain pure?
- Are all side effects in infra?
- Are CLI commands only parsing and wiring?
- Are all external responses schema validated?
- Are secrets/user text excluded from logs/cache/tests?
- Does output pass scrub before write?
- Are commands documented in `COMMANDS.md`?
- Are tests present at the right layer?
- Are non-goals preserved?
- Is any extra changed file justified?
```

FILE: ROADMAP.md

```text
# Roadmap

Do not implement directly from this file. Implementation must happen through an ExecPlan in `.agent/execplans/`.

This roadmap sequences Human Hand from repository discovery to production readiness. It is strategic. Coding agents must use the linked ExecPlan as the implementation source of truth.

| Phase | Purpose | Dependencies | Exit Criteria | Linked Specs | Linked ExecPlans |
|---|---|---|---|---|---|
| Phase 0: Repository discovery and foundation | Confirm greenfield state, commands, stack, risks, and bootstrap project skeleton. | Blueprint pack placed in repository. | EP-000 complete; EP-001 complete; `sh scripts/preflight.sh`, install, lint, format, typecheck, unit baseline, build pass. | SPEC-000, SPEC-008 | EP-000, EP-001 |
| Phase 1: Core domain | Implement pure business logic for style, facts, metadata scrub, prompt contracts, and repair decisions. | Phase 0 complete. | Domain unit tests pass; no infra imports in domain; core contracts documented. | SPEC-001, SPEC-006 | EP-002 |
| Phase 2: Data and persistence | Implement strict file I/O and optional SQLite detector cache without storing text. | Phase 1 interfaces stable. | File I/O and cache integration tests pass; no user text persisted. | SPEC-002, SPEC-006 | EP-003 |
| Phase 3: API or service layer | Implement application services, OpenAI-compatible LLM client, detector clients, and CLI command contracts. | Phases 1-2 complete. | Mocked service/CLI integration tests pass; live tests gated. | SPEC-003, SPEC-006 | EP-004 |
| Phase 4: UI or client layer | Polish CLI UX, JSON mode, no-color, predictable stdout/stderr, empty/error states. | Phase 3 commands exist. | CLI acceptance tests pass; no generated prose printed without `--print`. | SPEC-004, SPEC-006 | EP-005 |
| Phase 5: Auth, permissions, and security | Confirm no auth scope and harden secrets, endpoints, schema validation, redaction, cache permissions, and safe file behavior. | Phases 1-4 complete. | Security tests, Bandit, secret scan, endpoint safety tests pass. | SPEC-005, SPEC-006 | EP-006 |
| Phase 6: Testing hardening | Raise confidence with coverage, regressions, CI matrix, gated live E2E, smoke/performance checks. | Phases 1-5 complete. | Coverage >=85%; `sh scripts/verify.sh` passes locally; CI matrix green. | SPEC-001 through SPEC-008 | EP-007 |
| Phase 7: Observability and operations | Add JSONL logs, redaction, local counters, health command, runbooks. | Phase 6 baseline stable. | Observability tests pass; logs contain required fields and no user text. | SPEC-007 | EP-008 |
| Phase 8: Deployment and release | Prepare packaging, wheel install, release workflow, changelog, docs, rollback path. | Phase 7 complete. | Wheel installs in clean env; release workflow is manual; post-install smoke passes. | SPEC-008 | EP-009 |
| Phase 9: Production readiness | Final verification, security/privacy/performance/docs review, rollback drill, launch gate. | Phases 0-8 complete. | `sh scripts/verify.sh`, `sh scripts/production-readiness-check.sh`, and `sh scripts/loop.sh` pass; remaining risks documented. | SPEC-008 | EP-010 |

## Production Readiness Milestone

Production readiness is reached only when all ExecPlans EP-000 through EP-010 are complete, all specs are satisfied, all scripts required by `COMMANDS.md` pass, packaging artifacts are verified, release and rollback docs are complete, and a final Decision Log entry records the launch gate result.
```

FILE: DECISIONS.md

```text
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
```

FILE: TESTING.md

```text
# Testing Strategy

## Test Pyramid

Human Hand uses a local-first pyramid:

1. Many unit tests for pure domain logic and config validation.
2. Focused integration tests for file I/O, cache, mocked HTTP, and CLI wiring.
3. Small E2E/acceptance tests through Typer `CliRunner` and subprocess smoke tests.
4. Gated live E2E tests for configured LLM/detector endpoints only when explicitly enabled.

## Unit Test Rules

- Unit tests live in `tests/unit/`.
- Unit tests must never hit network, read secrets, depend on real home directories, or require paid accounts.
- Domain unit tests must import only domain modules and standard library helpers unless testing application ports.
- Every domain rule must have tests for success, invalid input, and boundary cases.
- Metadata scrub tests must include BOM, hidden JSON wrappers, provenance headers, model tags, trailing whitespace, CRLF normalization, and exactly one trailing newline.
- Fact diff tests must include preserved facts, omitted facts, contradicted facts, added facts, numbers, dates, named entities, and quotation-like text.

## Integration Test Rules

- Integration tests live in `tests/integration/`.
- Use temporary directories for files and cache.
- Use respx/httpx or equivalent mocks for HTTP.
- Verify retry behavior with 5xx/network errors and no retry for 4xx/schema errors.
- Verify cache stores no text by inspecting SQLite rows.
- Verify endpoint safety rejects insecure HTTP unless explicitly allowed.

## E2E Test Rules

- E2E tests live in `tests/e2e/`.
- Default E2E tests must use local mocks/fakes and complete without secrets.
- Live tests must be marked and skipped unless `HUMANHAND_RUN_LIVE_E2E=1`.
- Live tests must fail clearly when required endpoint/key/model is missing.
- E2E tests must cover `rewrite`, `verify`, `diff-facts`, `scrub`, `health`, `--help`, and `--version` after those commands exist.

## Contract Tests

- CLI contract tests assert command names, flags, stdout/stderr separation, JSON-only stdout in `--json` mode, exit codes, and no generated prose on stdout without `--print`.
- LLM contract tests assert request shape, schema-mode response parsing, fallback prompt-parse behavior when enabled, timeout, retry, and redaction.
- Detector contract tests assert provider selection, response schema validation, cache key construction, fallback heuristic result shape, and no user text persistence.

## Smoke Test Rules

- Smoke tests live in `tests/smoke/`.
- `sh scripts/smoke-test.sh` must complete under 30 seconds on mocks.
- Smoke tests must run without external network or secrets.
- Smoke tests must assert `humanhand --help`, `humanhand --version`, and at least one mocked rewrite/verify path after EP-004.

## Regression Test Rules

Add a regression test whenever fixing a bug that affects:

- Fact preservation.
- Metadata cleanup.
- UTF-8/BOM handling.
- Output newline behavior.
- Logging redaction.
- Cache text leakage.
- Endpoint security.
- Detector/LLM schema validation.
- CLI stdout/stderr contracts.

## Performance Test Rules

- Mock smoke test must be under 30 seconds.
- At least 95% of mock smoke runs should complete under 30 seconds in CI-class environments.
- `--help` and `--version` must emit first stdout byte within 100 ms in normal local conditions.
- Input cap defaults to 200,000 characters; tests must cover cap enforcement without allocating excessive memory.
- Logging overhead target is under 5% of run time; test with a simple benchmark or timing assertion in EP-008/EP-010 when stable.

## Accessibility Test Rules

Human Hand has no GUI. CLI accessibility requirements are:

- Screen-reader-friendly, predictable text.
- No spinners.
- Color off by default on Windows unless supported.
- `--no-color` honored.
- JSON mode prints JSON-only stdout.
- Empty input produces a friendly one-line error.

CLI tests must cover these behaviors after EP-005.

## Security Test Rules

- Run `sh scripts/security-check.sh`.
- Run `sh scripts/dependency-audit.sh`.
- Include tests for no secrets in logs, no user text in logs/cache, no insecure endpoint unless allowed, strict UTF-8 rejection, BOM rejection, and safe output path behavior.
- Unit tests must include redaction filter patterns for common key formats without storing real keys.

## Test Data Rules

- Fixtures must be synthetic and short.
- No real user data.
- No copyrighted third-party text beyond trivial fair-use snippets; prefer original invented samples.
- No sample API keys or realistic secrets.
- Fixtures must not include raw LLM/detector responses containing user text.

## Mocking Rules

- Mock at the external boundary, not inside domain logic.
- Mock HTTP with respx/httpx or provider adapter fakes.
- Mock time/randomness with injected values or deterministic seed.
- Do not mock the scrubber or fact diff in rewrite acceptance tests; those are core guarantees.

## Fixture Rules

- Use pytest fixtures for temporary files, fake configs, fake LLM clients, fake detector clients, and cache paths.
- Keep fixtures local to the tests that need them unless reused across three or more files.
- Fixture names must describe behavior, not implementation shortcuts.

## Required Tests per Feature

Each feature must include:

- Unit tests for pure logic.
- Integration tests for side effects.
- CLI/contract tests for user-visible behavior.
- Privacy/logging tests for text and secret redaction.
- Failure-mode tests for invalid input and unavailable external services.
- Regression tests for any bug fixed during the ExecPlan.

## Validation Matrix

| Area | Command |
|---|---|
| Lint | `sh scripts/lint.sh` |
| Format | `sh scripts/format-check.sh` |
| Typecheck | `sh scripts/typecheck.sh` |
| Unit | `sh scripts/test-unit.sh` |
| Integration | `sh scripts/test-integration.sh` |
| E2E | `sh scripts/test-e2e.sh` |
| Build | `sh scripts/build.sh` |
| Security | `sh scripts/security-check.sh` |
| Audit | `sh scripts/dependency-audit.sh` |
| Smoke | `sh scripts/smoke-test.sh` |
| Full | `sh scripts/verify.sh` |

## Definition of Test Done

Testing is done for an ExecPlan when all required tests pass, new behavior has regression coverage, tests do not rely on live network unless gated, coverage requirements for the phase are met, and no test fixture/log/cache contains user text or secrets.
```

FILE: SECURITY.md

```text
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
| Insecure endpoint exfiltration | Reject HTTP unless `HUMANHAND_ALLOW_INSECURE=1`; document local-only use. |
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
```

FILE: ENVIRONMENT.md

```text
# Environment

## Required Tools

| Tool | Required Version | Purpose | Verification |
|---|---|---|---|
| Python | 3.11.x | Runtime and tests | `python --version` or `uv run python --version` |
| uv | Current stable | Dependency sync, lock, commands | `uv --version` |
| POSIX sh | Git Bash, WSL, MSYS2, or CI shell | Run scripts | `sh scripts/preflight.sh` |
| Git | Current stable | Diff review and CI | `git --version` |

Windows 10/11 is first-class. Linux and macOS are best-effort. On Windows, use Git Bash, WSL, or another POSIX-compatible shell for `scripts/*.sh`.

## Package Manager

Use uv for development. Do not use Poetry, pipenv, npm, pnpm, conda, or ad-hoc virtualenv instructions unless an ADR changes the package manager.

## Environment Variables

| Name | Required | Environment | Example Value | Secret? | Description | Validation Rule |
|---|---|---|---|---|---|---|
| `HUMANHAND_LLM_BASE_URL` | Optional for local tests; required for live rewrite | local/live | `https://api.openai.com/v1` or `http://127.0.0.1:8000/v1` | No | OpenAI-compatible base URL. | Must be valid URL; reject `http://` unless `HUMANHAND_ALLOW_INSECURE=1`. |
| `HUMANHAND_LLM_API_KEY` | Optional unless endpoint requires it | local/live | `env-provided-secret` | Yes | API key for OpenAI-compatible endpoint. | Must never be logged; may be empty for local servers that do not require auth. |
| `HUMANHAND_LLM_MODEL` | Optional until live calls | local/live | `gpt-4.1-mini` or local model name | No | Model passed to OpenAI-compatible endpoint. | Non-empty string when live LLM is used. Do not invent model names in code. |
| `HUMANHAND_SEED` | Optional | all | `12345` | No | Deterministic seed. | Integer string when set. |
| `HUMANHAND_MAX_CHARS` | Optional | all | `200000` | No | Input character cap. | Positive integer; default 200000. |
| `HUMANHAND_TIMEOUT_SECONDS` | Optional | all | `30` | No | External call timeout. | Positive number; default 30. |
| `HUMANHAND_ALLOW_INSECURE` | Optional | local only | `1` | No | Allows HTTP endpoints for local servers. | Only `1`, `true`, or `yes` enable; default false. |
| `HUMANHAND_CONFIG` | Optional | all | `C:\Users\me\humanhand.toml` | No | Optional config file path if implemented. | Must point to readable file when set. |
| `HUMANHAND_CACHE_DIR` | Optional | all | `.cache/humanhand` | No | Cache directory for detector-score cache. | Must be writable when cache enabled; no text files allowed. |
| `HUMANHAND_CACHE_ENABLED` | Optional | all | `1` | No | Enables/disables detector cache. | Boolean-like; default enabled only for detector scores if implemented. |
| `HUMANHAND_DETECTOR_PROVIDER` | Optional | all | `local` | No | Detector provider: local, gptzero, originality, copyleaks, winston, turnitin. | Must be known provider; unknown fails clearly. |
| `GPTZERO_API_KEY` | Optional | live detector | `env-provided-secret` | Yes | GPTZero API key. | Required only when provider is `gptzero`; redacted. |
| `ORIGINALITY_API_KEY` | Optional | live detector | `env-provided-secret` | Yes | Originality.ai API key. | Required only when provider is `originality`; redacted. |
| `COPYLEAKS_API_KEY` | Optional | live detector | `env-provided-secret` | Yes | Copyleaks API key or token. | Required only when provider is `copyleaks`; redacted. |
| `WINSTON_API_KEY` | Optional | live detector | `env-provided-secret` | Yes | Winston AI API key. | Required only when provider is `winston`; redacted. |
| `TURNITIN_API_KEY` | Optional | live detector | `env-provided-secret` | Yes | Turnitin AI API credential if a supported account/API exists. | Required only when provider is `turnitin`; adapter must not invent endpoints. |
| `HUMANHAND_RUN_LIVE_E2E` | Optional | test | `1` | No | Enables live E2E tests. | Default false. Live tests skip unless true. |
| `NO_COLOR` | Optional | all | `1` | No | Standard no-color signal. | Any non-empty value disables color. |

## Secrets

- Store secrets in the process environment or local ignored `.env` only.
- `.env` must not be committed.
- Do not include placeholder secrets in docs that look real.
- Never print secrets in logs or test output.

## Local Development Setup

1. Place this blueprint pack in the repository root.
2. Run `sh scripts/preflight.sh`.
3. Execute EP-001 to create `pyproject.toml`, source tree, tests, and CI.
4. Run `sh scripts/install.sh`.
5. Run validation commands from `COMMANDS.md`.

## Local Database Setup

No standalone database setup. The optional detector-score SQLite cache is created lazily by the verify path when cache is enabled. It must never contain user text.

## Test Environment Setup

- Default tests require no secrets and no network.
- Live tests require `HUMANHAND_RUN_LIVE_E2E=1` plus explicit endpoint/provider credentials.
- CI must not set live E2E by default.

## Staging Environment Setup

There is no hosted staging service. Staging means a clean local or CI environment that installs the built wheel and runs smoke tests against mocked/local endpoints.

## Production Environment Setup

There is no hosted production service. Production means the released wheel/sdist and documented local CLI workflow on user machines.

## Configuration Validation

Config loading must validate env vars at command startup and fail before reading user text when possible for missing endpoint/model/key on live paths. Local fallback commands must remain usable without paid keys.

## Environment Parity Rules

- CI and local dev use the same scripts.
- Windows and Ubuntu CI must run the same validation sequence where possible.
- Live network tests are opt-in everywhere.

## Troubleshooting

- If `uv` is missing, install uv before running development commands.
- If scripts fail with `pyproject.toml not found`, execute EP-001 foundation.
- If live calls fail for missing keys, either configure the endpoint/key/model or use local mocked/fallback tests.
- If HTTP localhost endpoints are rejected, set `HUMANHAND_ALLOW_INSECURE=1` only for local development.
```

FILE: DEPLOYMENT.md

```text
# Deployment

## Deployment Environments

Human Hand has no hosted server deployment.

| Environment | Meaning | Deployment Target |
|---|---|---|
| Local development | Repository checkout with uv | Developer or agent machine |
| CI | GitHub Actions Windows/Ubuntu matrix | Ephemeral CI runners |
| Release candidate | Built wheel/sdist installed into clean env | Maintainer machine or CI artifact |
| Production | User-installed package | Windows 10/11 local PC; Linux/macOS best-effort |

## Deployment Architecture

- Build artifact: Python wheel and source distribution.
- Install method: `pip install humanhand` after published, or `pip install dist/humanhand-*.whl` for local artifact.
- Runtime: local single-process CLI.
- Database: none; optional local SQLite cache only.
- External services: user-configured LLM/detector endpoints.

## Build Artifact

`sh scripts/build.sh` must create artifacts under `dist/` using `python -m build`. Artifacts must not contain `.env`, `.cache/`, test outputs, secrets, user text, or local detector/LLM responses.

## Release Flow

1. Complete EP-010.
2. Confirm `sh scripts/verify.sh` exits 0.
3. Confirm `sh scripts/production-readiness-check.sh` exits 0.
4. Confirm `sh scripts/loop.sh` prints `build: complete`.
5. Build wheel/sdist with `sh scripts/build.sh`.
6. Install wheel in a clean environment.
7. Run post-install smoke tests.
8. Prepare release notes and changelog.
9. Obtain explicit maintainer approval for tag/publish.
10. Publish manually only after approval.

## Deployment Steps

### Local Wheel Install

1. Run `sh scripts/build.sh`.
2. Create clean Python 3.11 environment.
3. Run `pip install dist/humanhand-*.whl`.
4. Run `humanhand --version`.
5. Run `humanhand --help`.
6. Run a smoke rewrite/verify path using mocked/local endpoint or documented local fallback.

### PyPI Release

PyPI publishing is manual and requires explicit maintainer approval. No CI workflow may auto-publish to PyPI.

## Migration Steps

No primary database migrations. Optional cache schema is created lazily. Cache rollback is deletion of `.cache/humanhand/cache.db` or the configured cache file.

## Rollback Steps

- Application rollback: reinstall previous wheel version.
- Config rollback: restore previous env/config values.
- Cache rollback: delete local cache file; it contains no user text and can be rebuilt.
- Release rollback: yank or supersede package only with maintainer decision.

## Post-Deploy Smoke Tests

- `humanhand --version` exits 0 and prints version.
- `humanhand --help` exits 0 and prints command help.
- `humanhand scrub --audit <synthetic-file>` exits 0.
- `humanhand diff-facts <synthetic-source> <synthetic-output>` exits 0.
- `humanhand verify <synthetic-output>` exits 0 using local heuristic fallback when no provider key is configured.
- Mocked/local rewrite path completes without printing generated prose to stdout unless `--print` is used.

## Required Approvals

Explicit maintainer approval is required for:

- Git tags.
- GitHub releases.
- PyPI publishing.
- Any live detector/LLM testing with paid accounts.
- Any irreversible data or release action.

## Deployment STOP Conditions

Stop when:

- Release approval is missing.
- Tests or production-readiness checks fail after bounded recovery.
- Artifacts contain secrets, user text, `.env`, `.cache`, or unexpected files.
- Wheel install fails in a clean environment.
- Rollback path is not documented.

## Production Verification

Production verification is local artifact verification, not server monitoring. It requires passing validation scripts, clean wheel install, smoke tests, docs review, security/privacy review, release notes, rollback instructions, and signed-off launch gate in EP-010.
```

FILE: OPERATIONS.md

```text
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
```

FILE: OBSERVABILITY.md

```text
# Observability

## Logging Strategy

Human Hand emits structured JSONL logs to stderr only. Human-facing results go to stdout. Generated prose is never printed to stdout unless the user passes an explicit `--print` flag.

Logs support local debugging without telemetry. There are no remote metrics, dashboards, distributed traces, or phone-home behavior.

## Structured Log Fields

Required fields when applicable:

| Field | Type | Rule |
|---|---|---|
| `timestamp` | string | ISO-8601 UTC timestamp. |
| `level` | string | `debug`, `info`, `warning`, `error`. |
| `event` | string | Stable event name such as `rewrite.start`. |
| `message` | string | Redacted human-readable summary; no user text. |
| `elapsed_ms` | number/null | Duration for completed operation. |
| `model` | string/null | Model name from config, no secrets. |
| `endpoint_host` | string/null | Host only, no path/query/key. |
| `input_length` | number/null | Character count only. |
| `output_length` | number/null | Character count only. |
| `sha256_prefix` | string/null | Short prefix of hash; no full text. |
| `cache_hit` | boolean/null | Detector cache hit/miss when applicable. |
| `attempt` | number/null | External call attempt number. |
| `retry_reason` | string/null | Redacted reason, such as `network_error` or `http_503`. |

## Redaction Rules

- Never log source text, style samples, prompts, generated output, raw LLM response text, raw detector response text, or secrets.
- Redact common key formats and env var values.
- Strip URL credentials and query strings before logging endpoint host.
- Do not log file contents.
- Tests must assert redaction on representative events.

## Metrics

No remote metrics. Local counters may be emitted to stderr at command end as JSONL events. Allowed counters:

- `rewrite_attempts`.
- `repair_attempts`.
- `detector_calls`.
- `cache_hits`.
- `cache_misses`.
- `retry_count`.
- `duration_ms`.
- `input_chars` and `output_chars`.

Counters must not include text.

## Traces

No distributed tracing. For local debugging, use correlated event names and elapsed times within one command run. Do not add trace exporters.

## Health Checks

`humanhand health --json` is the health surface. It must not call external endpoints by default. It must validate local config shape, cache path, Python/platform, and command availability.

## Uptime Checks

Not applicable. There is no hosted service.

## Dashboards

Not applicable. No dashboards or remote telemetry. Maintainers may inspect CI logs and release smoke outputs only.

## Alerts

No runtime alerts. CI failures, security audit failures, and reported issues are the alert channels.

## Service-Level Indicators

For local production readiness:

- Command success rate in CI smoke tests.
- Mock smoke duration.
- Test coverage.
- Security/audit status.
- Redaction test status.
- Packaging install success.

## Service-Level Objectives

- Mock smoke test under 30 seconds.
- `--help` and `--version` first stdout byte within 100 ms under normal local conditions.
- Zero known user-text logging/cache leaks.
- Zero committed secrets.

## Debugging Production Issues

1. Ask for command, version, redacted logs, platform, and config shape.
2. Do not ask for real user text.
3. Reproduce with synthetic fixtures.
4. Use event names, elapsed times, endpoint host, attempts, retry reason, and hashes to isolate issue.
5. Add regression tests for fixes.

## Observability Acceptance Criteria

- JSONL logs parse successfully.
- Required fields appear for rewrite, verify, detector, cache, retry, and error paths.
- stdout/stderr separation is tested.
- Redaction tests prove no user text or secrets appear.
- Health command works without secrets or network.
- No remote telemetry code exists.
```

FILE: PRODUCTION_READINESS.md

```text
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

- [ ] EP-000 through EP-010 complete.
- [ ] `sh scripts/verify.sh` passes.
- [ ] `sh scripts/production-readiness-check.sh` passes.
- [ ] `sh scripts/loop.sh` prints `build: complete`.
- [ ] Wheel/sdist built.
- [ ] Clean install smoke passes.
- [ ] No secrets or user text leaks.
- [ ] README/CHANGELOG/release notes updated.
- [ ] Rollback drill documented.
- [ ] Final Decision Log entry added.
```

FILE: RELEASE.md

```text
# Release Process

## Release Types

| Type | Description | Approval |
|---|---|---|
| Development snapshot | Local build from repository. | No publish approval. |
| Release candidate | Built artifact for maintainer testing. | Maintainer review. |
| Patch release | Bug/security fix without new scope. | Maintainer approval. |
| Minor release | New approved feature via ExecPlan. | Maintainer approval. |
| Major release | Breaking public behavior or major architecture change. | Maintainer approval and ADR. |

## Versioning

Use semantic versioning after first public release. Before 1.0, minor versions may include breaking changes only when release notes state them clearly. Version must be defined in one source in `pyproject.toml` or package metadata after EP-001.

## Changelog

Maintain `CHANGELOG.md` after EP-009. Each release entry must include:

- Version.
- Date.
- Added/changed/fixed/security sections.
- Upgrade notes.
- Privacy/security implications if any.
- Known risks.

## Branch Strategy

Branch strategy is lightweight for an open-source CLI:

- `main` contains releasable work after verification.
- Feature branches or agent sessions implement one ExecPlan.
- Release tags require maintainer approval.
- Do not rewrite public release history.

## Release Candidate Criteria

- Active ExecPlan complete.
- `sh scripts/verify.sh` passes.
- `sh scripts/production-readiness-check.sh` passes for production candidates.
- Wheel/sdist build.
- Clean install smoke pass.
- No committed secrets or user text.
- Release notes drafted.

## Release Checklist

- [ ] Confirm active ExecPlan is complete.
- [ ] Run `sh scripts/verify.sh`.
- [ ] Run `sh scripts/production-readiness-check.sh` for production release.
- [ ] Run `sh scripts/build.sh`.
- [ ] Install wheel in clean Python 3.11 environment.
- [ ] Run post-install smoke tests.
- [ ] Review `git diff --name-only`.
- [ ] Review artifacts for `.env`, `.cache`, secrets, and user text.
- [ ] Update `CHANGELOG.md`.
- [ ] Prepare release notes.
- [ ] Obtain explicit maintainer approval for tag/publish.
- [ ] Publish manually if approved.

## Smoke Tests

Post-release smoke tests:

- `humanhand --version`.
- `humanhand --help`.
- `humanhand health --json`.
- `humanhand scrub --audit` on synthetic fixture.
- `humanhand diff-facts` on synthetic fixture.
- `humanhand verify` with local heuristic fallback.
- Mocked/local rewrite path.

## Approvals

Manual approval is required for:

- Git tag creation.
- GitHub release publication.
- PyPI publication.
- Live paid detector usage.
- Any release rollback/yank.

## Release Notes

Release notes must mention:

- CLI command changes.
- Env/config changes.
- Detector/LLM integration changes.
- Security/privacy changes.
- Known limitations.
- Ethical/legal responsibility disclaimer.

## Post-Release Monitoring

There is no hosted monitoring. Maintainers monitor:

- CI status.
- Issue tracker.
- Security reports.
- User-reported install/runtime failures.
- PyPI package integrity and metadata.
```

FILE: ROLLBACK.md

```text
# Rollback Process

## Rollback Triggers

Rollback may be needed when:

- Released wheel fails to install.
- CLI command fails on basic smoke tests.
- Output contains metadata or hidden wrappers.
- User text or secrets appear in logs/cache/artifacts.
- Critical fact-drift regression is confirmed.
- Dependency/security issue affects release.
- Release artifact contains unexpected files.

## Rollback Decision Owner

Maintainer decides release rollback, PyPI yanking, or superseding release. Coding agents must not perform rollback actions against public releases without explicit maintainer approval.

## Rollback Types

| Type | Action |
|---|---|
| Application rollback | Reinstall previous wheel version. |
| Config rollback | Restore previous env/config values. |
| Cache rollback | Delete `.cache/humanhand/cache.db` or configured cache file. |
| Release rollback | Yank/supersede release after maintainer decision. |
| Documentation rollback | Correct docs and release notes. |

## Application Rollback

1. Identify previous known-good version.
2. Install previous wheel with pip.
3. Run `humanhand --version`.
4. Run post-install smoke tests.
5. Document the reason and result.

## Database Rollback

No primary database. Optional cache rollback is deletion. Cache contains no user text and can be rebuilt.

## Config Rollback

Restore prior values for `HUMANHAND_*` and provider keys. Do not print old or new secret values in logs, issues, or reports.

## Feature Flag Rollback

No feature flag system exists. If a future feature flag is added, document it in `ENVIRONMENT.md`, `ARCHITECTURE.md`, and an ADR.

## Verification After Rollback

- `humanhand --version` shows expected version.
- `humanhand --help` works.
- `humanhand health --json` works without exposing secrets.
- Synthetic `verify`, `diff-facts`, and `scrub --audit` work.
- Logs contain no user text or secrets.

## Communication

Release rollback communication must include:

- Affected version.
- Reason in non-sensitive terms.
- User action required.
- Whether user text/secrets were affected.
- Mitigation and fixed version if available.

## Postmortem

For security/privacy/fact-drift rollback, add:

- Root cause.
- Detection method.
- Impact.
- Fix.
- Regression tests added.
- Process changes.
- Linked ExecPlan or ADR.
```

FILE: CONTRIBUTING.md

```text
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
```

FILE: .agent/PLANS.md

```text
# ExecPlan Standard

An ExecPlan is a self-contained implementation document for one feature or system change. A new agent with no prior conversation must be able to continue from the ExecPlan alone.

## Required Sections

Every ExecPlan must include:

1. Purpose / Big Picture
2. Scope
3. Non-goals
4. Context and Orientation
5. Files to Read First
6. Files to Change
7. Interfaces and Contracts
8. Milestones
9. Concrete Steps
10. Validation and Acceptance
11. Idempotence and Recovery
12. Progress
13. Surprises & Discoveries
14. Decision Log
15. Outcomes & Retrospective

## Execution Rules

- One active ExecPlan per session.
- Do not implement directly from `ROADMAP.md`.
- Read `AGENTS.md`, `COMMANDS.md`, `.agent/PLANS.md`, `.agent/EXECUTION_RULES.md`, and the active ExecPlan before editing.
- Run `sh scripts/preflight.sh` before edits.
- Complete milestones in order.
- Validate after every milestone.
- Continue autonomously unless a STOP condition applies.
- Use only commands from `COMMANDS.md`.

## Milestone Rules

Each milestone must include:

- Goal.
- Files to read.
- Files to change.
- Exact edits expected.
- Validation command.
- Expected result.
- Recovery instruction.

Milestones must be small enough that a lower-tier coding agent can complete and validate them without guessing.

## Validation Rules

- Use exact commands from `COMMANDS.md`.
- Record command and result in the ExecPlan.
- Do not skip validation because a later command will cover it.
- Do not weaken tests or scripts to pass.
- Live network tests must be explicitly gated.

## Acceptance Rules

An ExecPlan must define observable acceptance criteria. Completion requires all acceptance criteria and validation commands to pass.

## Idempotence Rules

- Re-running a partially completed ExecPlan must be safe.
- Avoid duplicate files, duplicated config, duplicated log fields, or duplicate CLI commands.
- If a file already exists, inspect it and modify minimally rather than recreate blindly.
- If repository state differs from the plan, record the difference and choose the smallest safe adjustment.

## Recovery Rules

Use bounded retry for failures:

1. First same-root failure: smallest targeted fix.
2. Second same-root failure: narrower diagnostic.
3. Third same-root failure: change approach or stop under STOP condition.

Record failed hypotheses in Surprises & Discoveries.

## Progress Update Rules

- Check off each milestone only after its validation passes.
- Update Surprises & Discoveries when reality differs from plan.
- Update Decision Log for assumptions, extra files, dependencies, interfaces, or behavior choices.
- Update Outcomes & Retrospective at completion.
- Write `.agent/state/last-result.env` as the final file operation.

## Decision Log Rules

Each Decision Log entry must include date, decision, reason, and consequence. Extra changed files must be justified here.

## Completion Rules

Done means:

- All milestones complete.
- All validations pass.
- Acceptance criteria pass.
- Final diff reviewed.
- Expected changed files match actual changed files or extra files are justified.
- Remaining risks documented.
- `.agent/state/last-result.env` written.
- Final response includes required status report.
```

FILE: .agent/EXECUTION_RULES.md

```text
# Execution Rules

## One Active ExecPlan Rule

Implement exactly one ExecPlan per session. Do not work on another plan unless the user explicitly changes the active plan.

## No Hidden Context Rule

Assume no memory outside repository files and the current user instruction. If a fact matters, it must appear in `AGENTS.md`, `COMMANDS.md`, `.agent/PLANS.md`, a spec, an ExecPlan, or repository code.

## No Roadmap-Only Implementation Rule

`ROADMAP.md` is not an implementation plan. Do not implement from it directly.

## Continue-by-Default Rule

Do not ask for next steps. Continue through milestones until the active ExecPlan is complete or a STOP condition in `AGENTS.md` applies.

## STOP-Only Rule

Stop only for explicit STOP conditions. When stopping, provide exact blocker, evidence, smallest decision needed, and recommended default.

## Anti-Drift Rule

Do not broaden scope, refactor unrelated files, change architecture, add features, change package manager, or alter public contracts unless the active ExecPlan requires it.

## Anti-Hallucination Rule

Do not invent commands, APIs, config keys, environment variables, database tables, detector endpoints, model names, file paths, or package functions. Verify or create them in scope before use.

## Anti-Fixation Rule

For repeated validation failures, use the three-step bounded retry rule from `AGENTS.md`. Never keep patching the same failure without a new hypothesis.

## Test-Before-Completion Rule

An ExecPlan is not complete until required validation commands pass. Do not rely on reasoning alone.

## Diff Review Rule

Before final response, run `git diff --name-only`, compare with Files to Change, and justify extra changed files in the Decision Log.

## Final Response Rule

Final response must report ExecPlan id/status, milestones, changed files, commands/results, acceptance status, decisions, assumptions, risks, production-readiness status when applicable, and confirmation that `.agent/state/last-result.env` was written.
```

FILE: .agent/prompts/execute-active-execplan.md

```text
# Prompt: Execute Active ExecPlan

Read `AGENTS.md`, `COMMANDS.md`, `.agent/PLANS.md`, `.agent/EXECUTION_RULES.md`, and `[EXECPLAN_PATH]`.

Implement `[EXECPLAN_PATH]` to completion.

Additional user request, if any:

`[OPTIONAL_USER_REQUEST]`

Rules:

- Do not ask for next steps.
- Do not implement from `ROADMAP.md` directly.
- Do not broaden scope.
- Use only commands from `COMMANDS.md`.
- Run `sh scripts/preflight.sh` before edits.
- Complete milestones in order.
- Validate after each milestone using the command in the ExecPlan.
- Update the ExecPlan Progress, Surprises & Discoveries, Decision Log, and Outcomes & Retrospective as you work.
- Apply bounded retry on failures.
- Stop only for STOP conditions in `AGENTS.md`.
- Before completion, run required final validation, run `git diff --name-only`, compare changed files with Files to Change, and justify extra files.
- Write `.agent/state/last-result.env` as the final file operation.
- Final response must include ExecPlan id/status, milestones completed, files changed, commands run/results, acceptance status, decisions, assumptions, risks, production-readiness status if applicable, and confirmation that `.agent/state/last-result.env` was written.
```

FILE: .agent/prompts/continue-execplan.md

```text
# Prompt: Continue a Partially Completed ExecPlan

Read `AGENTS.md`, `COMMANDS.md`, `.agent/PLANS.md`, `.agent/EXECUTION_RULES.md`, and the active ExecPlan.

Continue the active ExecPlan to completion.

Required actions:

- Inspect Progress.
- Inspect Surprises & Discoveries.
- Inspect Decision Log.
- Inspect Outcomes & Retrospective if present.
- Resume at the first incomplete milestone.
- Validate prior assumptions against repository files before editing.
- Run `sh scripts/preflight.sh` unless it was run successfully in the current session.
- Continue autonomously.
- Do not ask for next steps.
- Stop only for STOP conditions in `AGENTS.md`.
- Use only commands from `COMMANDS.md`.
- Validate after each milestone.
- Update the ExecPlan as you work.
- Run final validation, run `git diff --name-only`, write `.agent/state/last-result.env` as the final file operation, and produce the required final report.
```

FILE: .agent/prompts/debug-validation-failure.md

```text
# Prompt: Debug a Failing Validation Command

Read `AGENTS.md`, `COMMANDS.md`, `.agent/PLANS.md`, `.agent/EXECUTION_RULES.md`, and the active ExecPlan.

Debug the failing validation command without broad rewrites.

Required actions:

1. Capture the exact failing command.
2. Capture the exact error summary.
3. Identify whether this is the first, second, or third same-root failure.
4. Form one specific hypothesis.
5. Make the smallest targeted fix.
6. Rerun the narrowest relevant command from `COMMANDS.md`.
7. If the same-root failure occurs a second time, create or run a narrower diagnostic.
8. If the same-root failure occurs a third time, stop the current approach, record failed hypotheses in Surprises & Discoveries, choose a simpler implementation path if safe, or stop under a STOP condition.
9. Do not rewrite unrelated code.
10. Do not weaken validation.
11. Update the active ExecPlan Decision Log and Progress as appropriate.
12. Continue the ExecPlan after the validation passes.
```

FILE: .agent/prompts/final-review.md

```text
# Prompt: Final Review

Read `AGENTS.md`, `COMMANDS.md`, `.agent/PLANS.md`, `.agent/EXECUTION_RULES.md`, and the active ExecPlan.

Perform final review for the active ExecPlan.

Required actions:

- Verify all Progress checkboxes are complete or accurately incomplete.
- Verify all acceptance criteria are satisfied.
- Run the final validation command required by the ExecPlan.
- Run `sh scripts/verify.sh` when the ExecPlan requires full verification.
- Run `sh scripts/production-readiness-check.sh` when the ExecPlan is EP-010 or explicitly requires it.
- Run `git diff --name-only`.
- Compare changed files with Files to Change.
- Justify extra changed files in the Decision Log.
- Check no secrets or user text were added.
- Update Outcomes & Retrospective.
- Write `.agent/state/last-result.env` as the final file operation.
- Produce final report with ExecPlan id/status, milestones completed, changed files, commands/results, acceptance status, decisions, assumptions, risks, production-readiness status if applicable, and confirmation that `.agent/state/last-result.env` was written.
```

FILE: .agent/specs/SPEC-000-product-scope.md

```text
# SPEC-000: Product Scope

## Status

Accepted blueprint specification.

## Owner

Blueprint / Maintainer.

## Linked Roadmap Phase

Phase 0 through Phase 9.

## Linked ExecPlans

EP-000 through EP-010.

## User-Visible Goal

Users can install and run a local CLI named `humanhand` that rewrites AI-assisted drafts into the style of a supplied human sample while preserving facts, stripping metadata, and offering verification tools.

## Non-Goals

- Web UI, GUI, TUI, HTTP API, hosted service, public SDK, auth, accounts, roles, sessions, cloud database, background workers, telemetry, remote metrics, automated platform submission, fine-tuning, server deployment, auto-PyPI publish, and implementation outside active ExecPlans.

## Terms

- Source text: AI-assisted draft provided by user.
- Style sample: Human-written sample provided by user.
- Humanized output: Rewritten output file.
- Detector provider: Commercial detector integration or local heuristic fallback.
- User text: Source text, style sample, prompts, generated output, and raw text-bearing provider responses.

## Required Behavior

- CLI-only interface.
- Local-first single-user workflow.
- OpenAI-compatible endpoint support.
- Local heuristic detector fallback.
- Strict privacy: no telemetry, no user-text logging, no user-text cache.
- Byte-clean UTF-8 output with LF newlines and exactly one trailing newline.
- Clear disclaimer that users bear legal and ethical responsibility.

## Inputs

- Files or stdin for source text where command supports stdin.
- File path for style sample.
- Output path.
- Environment/config for optional endpoints and detector providers.

## Outputs

- Plain UTF-8 output file.
- Human-facing command results on stdout.
- Structured JSONL logs/counters on stderr.
- JSON-only stdout when `--json` is used.

## Error States

- Missing files.
- Empty input.
- UTF-8 decode failure or BOM.
- Input too large.
- Unsafe output path.
- Missing endpoint/model/key for live path.
- Detector unavailable.
- Schema validation failure.
- Fact drift above threshold.

## Data Rules

- User input files are read-only.
- No persistent user-text history.
- Cache stores detector score metadata only.
- Test fixtures are synthetic.

## Security Rules

- No secrets in repo/logs/artifacts.
- HTTPS endpoints by default.
- Redaction everywhere.
- Output scrub before write.

## Accessibility Rules

- Predictable CLI output.
- No spinners.
- `--no-color` honored.
- Screen-reader-friendly text.

## Performance Rules

- Input cap default 200,000 chars.
- External timeout default 30 seconds.
- Retry cap 3.
- Smoke tests under 30 seconds.

## Observability Rules

- JSONL stderr logs only.
- No telemetry.
- Local counters only.

## Required Tests

- CLI smoke tests.
- Privacy tests.
- Metadata output tests.
- Fact preservation tests.
- Packaging install tests.
- Security/audit tests.

## Acceptance Criteria

- Non-goals remain absent.
- All core commands work by EP-010.
- `sh scripts/verify.sh` passes.
- `sh scripts/production-readiness-check.sh` passes.
- User text is not logged or cached.
- README/docs include ethical responsibility and privacy implications.
```

FILE: .agent/specs/SPEC-001-core-domain.md

```text
# SPEC-001: Core Domain

## Status

Accepted blueprint specification.

## Owner

Blueprint / Maintainer.

## Linked Roadmap Phase

Phase 1: Core domain.

## Linked ExecPlans

EP-002, with related validation in EP-004 and EP-007.

## User-Visible Goal

Human Hand rewrites text in the supplied human style while preserving factual content and removing metadata-like artifacts.

## Non-Goals

- Network calls, file I/O, cache access, logging, CLI parsing, detector HTTP clients, LLM SDK usage, or paid provider logic in domain.
- Guaranteeing legal/academic acceptability.
- Training or fine-tuning models.

## Terms

- Style fingerprint: Structured representation of voice, syntax, punctuation, vocabulary, paragraph shape, idioms, and formatting tendencies.
- Fact anchor: Extracted factual item such as named entity, number, date, claim, relation, citation-like marker, or quoted phrase.
- Drift: Omission, contradiction, or unsupported addition relative to source facts.
- Metadata marker: BOM, provenance header, JSON wrapper, model tag, detector tag, telemetry-like field, or hidden marker.
- Repair decision: Deterministic decision to accept output, request repair, or fail.

## Required Behavior

- Build style fingerprint from style sample using deterministic pure functions.
- Extract fact anchors from source and output.
- Compare fact anchors and produce drift report with omissions, additions, contradictions, and preservation score.
- Build prompt contracts that require style matching, fact preservation, plain text output, no metadata, and no hidden wrappers.
- Scrub metadata-like markers from candidate output before writing.
- Decide repair loop state based on drift and scrub results.
- Respect deterministic seed where randomness is needed; prefer deterministic algorithms.

## Inputs

- Source text string.
- Style sample text string.
- Candidate output text string.
- Optional thresholds and seed.

## Outputs

- `StyleFingerprint` value object.
- `FactDiffReport` value object.
- `ScrubReport` value object.
- Prompt payload or message contract value object.
- `RepairDecision` value object.
- Clean output text string.

## Error States

- Empty source/style/candidate.
- Input exceeds configured cap.
- Non-string or invalid types at pure boundary.
- Unscrubbable metadata if output cannot be made clean without losing content.
- Fact drift above acceptable threshold.

## Data Rules

- Domain functions do not persist data.
- Domain may compute hashes but must not log.
- Domain results must not include full prompts in objects intended for logging.

## Security Rules

- Domain scrubber must remove metadata markers before infra writes output.
- Domain must not include secrets or env values.
- Domain must not include source/style text in error messages intended for logs.

## Accessibility Rules

Not applicable to domain logic.

## Performance Rules

- Domain processing should handle 200,000 characters without excessive memory growth.
- Prefer linear or near-linear text scans.

## Observability Rules

- Domain emits no logs.
- Application/infra may log lengths and hash prefixes derived from domain inputs.

## Required Tests

- Style fingerprint unit tests for vocabulary, punctuation, paragraph shape, idiom, and formatting tendencies.
- Fact extraction/diff tests for numbers, dates, names, claims, omitted facts, added facts, contradictions.
- Scrub tests for BOM, JSON wrappers, model markers, metadata headers, trailing whitespace, CRLF normalization, exactly one newline.
- Prompt contract tests asserting plain text/no metadata/fact preservation instructions.
- Repair decision tests for accept, repair, and fail states.
- Import-boundary test proving domain does not import infra/cli/http libraries.

## Acceptance Criteria

- Domain tests pass.
- Domain has no I/O/network/env/logging dependencies.
- Output scrub is deterministic.
- Fact diff report is machine-friendly and used by CLI/application paths.
- No user text is embedded in log-oriented errors.
```

FILE: .agent/specs/SPEC-002-data-model.md

```text
# SPEC-002: Data Model and Persistence

## Status

Accepted blueprint specification.

## Owner

Blueprint / Maintainer.

## Linked Roadmap Phase

Phase 2: Data and persistence.

## Linked ExecPlans

EP-003, EP-006, EP-010.

## User-Visible Goal

Human Hand reads and writes local text files safely and may cache detector scores without storing user text.

## Non-Goals

- Primary database.
- Server-side storage.
- User accounts.
- Persistent text history.
- Migrations framework.
- Backups for cache.

## Terms

- Detector score cache: Optional SQLite database containing detector score metadata only.
- Text hash: SHA-256 digest of normalized text used as cache key.
- Schema version: Integer or string identifying cache table shape.

## Required Behavior

- Read files as strict UTF-8.
- Reject BOM.
- Normalize output to LF, strip trailing whitespace per line, ensure exactly one trailing newline.
- Prevent output path from overwriting input files.
- Cache detector scores by text hash, provider, model, and schema version.
- Cache must never store source text, style sample, output text, prompts, or raw responses containing text.
- Cache schema created lazily.
- Cache file permissions set to `0600` where supported.

## Inputs

- Source/style/output file paths.
- Optional stdin source where command supports it.
- Cache directory env/config.
- Detector score result objects.

## Outputs

- Clean output file.
- Cache rows with score metadata only.
- Audit report for scrub command.

## Error States

- File not found.
- Permission denied.
- UTF-8 decode error.
- BOM detected.
- Output path equals input path.
- Cache unavailable or corrupt.
- Cache schema incompatible.

## Data Rules

Cache allowed fields:

- `schema_version`.
- `text_sha256` or hash prefix/full digest.
- `provider`.
- `model`.
- `score`.
- `label`.
- `raw_score_json` only if proven text-free.
- `created_at`.
- `expires_at` if TTL is implemented.

Forbidden fields:

- Source text.
- Style sample text.
- Generated output text.
- Prompt text.
- Raw LLM response text.
- Raw detector response containing submitted text.
- Secrets.

## Security Rules

- Input files read-only.
- Cache contains no secrets/user text.
- Atomic output writes must not leak text to logs.
- Cache deletion is safe rollback.

## Accessibility Rules

File errors must be short, clear, and one-line for CLI users unless `--json` is used.

## Performance Rules

- File handling supports 200,000 chars by default.
- Cache lookup is indexed by hash/provider/model/schema.
- Cache operations do not dominate detector verification time.

## Observability Rules

- Log path hashes or basenames only when necessary; prefer lengths and hash prefixes.
- Log cache hit/miss, not cache row contents.

## Required Tests

- Strict UTF-8 read success/failure.
- BOM rejection.
- LF output normalization.
- Exactly one trailing newline.
- No overwrite of input path.
- Cache create/read/update.
- Cache no-text inspection.
- Cache permission best-effort test where supported.
- Cache corrupt/incompatible behavior.

## Acceptance Criteria

- File I/O integration tests pass.
- Cache integration tests pass.
- No persistent user-text storage exists.
- Rollback by cache deletion is documented.
```

FILE: .agent/specs/SPEC-003-api-contracts.md

```text
# SPEC-003: CLI and Service Contracts

## Status

Accepted blueprint specification.

## Owner

Blueprint / Maintainer.

## Linked Roadmap Phase

Phase 3: API or service layer.

## Linked ExecPlans

EP-004, EP-005, EP-008, EP-009.

## User-Visible Goal

Users interact with Human Hand through stable CLI commands and optional env/config. There is no HTTP API.

## Non-Goals

- HTTP routes.
- Webhooks.
- Public SDK beyond internal contracts.
- Server auth.
- Streaming UI.

## Terms

- Command contract: CLI name, arguments, flags, stdout/stderr behavior, exit code, and output schema.
- Service method: Application use case invoked by CLI.
- JSON mode: JSON-only stdout with logs still on stderr.

## Required Behavior

Required commands:

- `humanhand rewrite --source <path|-> --style <path> --out <path> [--json] [--print] [--no-color]`.
- `humanhand verify <output> [--provider <provider>] [--json] [--no-color]`.
- `humanhand diff-facts <ai-source> <output> [--json] [--no-color]`.
- `humanhand scrub <file> [--out <path>] [--audit] [--json] [--no-color]`.
- `humanhand health [--json] [--no-color]`.
- `humanhand --help`.
- `humanhand --version`.

Application service methods should mirror these commands: rewrite, verify, diff_facts, scrub, health.

## Inputs

- CLI args and flags.
- Env/config values.
- Input file contents.
- Provider responses via infra adapters.

## Outputs

- Exit code 0 for success.
- Nonzero exit code for errors.
- Human-readable stdout or JSON-only stdout.
- Logs/counters to stderr only.
- Output file for rewrite/scrub write paths.

## Error States

- Invalid command/flag.
- Missing required path.
- File read/write errors.
- Config validation errors.
- LLM/detector unavailable.
- Schema validation errors.
- Fact drift repair failure.
- Unsafe endpoint.

## Data Rules

- CLI must not print generated prose unless `--print` is passed.
- JSON output must not include full source/style/prompt text.
- JSON output for `diff-facts` may include factual anchor summaries derived from user text only because the command's purpose is to show differences to the user; logs must not include those anchors.

## Security Rules

- No secrets in stdout/stderr.
- No user text in stderr logs.
- External calls require explicit config.
- Detector providers require env keys unless local fallback.

## Accessibility Rules

- Predictable command output.
- No spinners.
- `--no-color` honored.
- Color off by default on Windows unless terminal supports it.
- Friendly one-line errors.

## Performance Rules

- `--help` and `--version` first byte under 100 ms target.
- External calls timeout after 30 seconds by default.
- Retry cap 3.

## Observability Rules

- Each command logs start/end/error events to stderr JSONL.
- Required fields from SPEC-007.

## Required Tests

- Typer CliRunner command contract tests.
- Service unit tests with fake ports.
- Mocked HTTP integration tests for LLM and detectors.
- JSON mode tests.
- stdout/stderr separation tests.
- Exit code tests.
- No prose-to-stdout without `--print` test.

## Acceptance Criteria

- Required commands exist and are documented.
- Contract tests pass.
- Live calls are gated.
- No HTTP API files/routes are introduced.
```

FILE: .agent/specs/SPEC-004-ui-ux-behavior.md

```text
# SPEC-004: CLI UX Behavior

## Status

Accepted blueprint specification.

## Owner

Blueprint / Maintainer.

## Linked Roadmap Phase

Phase 4: UI or client layer.

## Linked ExecPlans

EP-005, EP-007, EP-009.

## User-Visible Goal

Users receive predictable, accessible, machine-friendly CLI behavior with clear success, empty, loading/status, and error states.

## Non-Goals

- GUI.
- Web UI.
- TUI.
- Real-time streaming UI.
- Spinners.
- Interactive prompts during unattended execution.

## Terms

- Human-facing stdout: user result text.
- Logs: JSONL stderr only.
- Status message: short progress line on stderr without user text.
- JSON mode: JSON-only stdout.

## Required Behavior

- `--help` and `--version` are fast and do not load heavy clients.
- `--json` prints valid JSON only on stdout.
- `--no-color` disables color.
- `NO_COLOR` disables color.
- Color defaults off on Windows unless appropriate terminal support is detected.
- No spinners; use short status messages on stderr.
- Empty input produces a friendly one-line error.
- Generated prose is not printed to stdout unless `--print` is passed.
- Rewrite success prints output path and summary, not text, unless `--print`.
- Verify prints provider, score, label, cache hit, and explanation appropriate to provider/fallback.
- Diff-facts prints a concise drift summary and detailed JSON in `--json` mode.
- Scrub audit prints metadata findings without modifying input.

## Inputs

- CLI flags/args.
- Terminal capabilities.
- `NO_COLOR` env var.
- Command result objects.

## Outputs

- Plain stdout for human results.
- JSON stdout for `--json`.
- JSONL stderr logs/status.
- Stable exit codes.

## Error States

- Empty input.
- Invalid path.
- Missing config.
- Provider unavailable.
- Fact drift failure.
- Output path unsafe.

## Data Rules

- Do not print source/style/prompt in errors.
- `diff-facts` and `scrub --audit` may show user-facing snippets/findings because that is the explicit purpose; logs must still avoid user text.

## Security Rules

- Secrets redacted.
- Endpoint host only in logs.
- No generated output to stdout without `--print`.

## Accessibility Rules

- No color-only communication.
- No spinner animations.
- Text labels before values.
- Machine-friendly JSON mode.
- Screen-reader-friendly error text.

## Performance Rules

- Help/version first stdout byte within 100 ms target.
- No network or config-heavy initialization for help/version.

## Observability Rules

- Status/progress to stderr only.
- Logs remain JSONL when logging is enabled.

## Required Tests

- CLI help/version speed smoke where practical.
- `--json` stdout parse tests.
- stdout/stderr separation tests.
- `--no-color` and `NO_COLOR` tests.
- Empty input error tests.
- No generated prose without `--print` test.
- Audit does not modify input test.

## Acceptance Criteria

- CLI acceptance tests pass.
- No GUI/TUI/web files introduced.
- CLI output is predictable and accessible.
```

FILE: .agent/specs/SPEC-005-auth-and-permissions.md

```text
# SPEC-005: Auth, Permissions, and Security Baseline

## Status

Accepted blueprint specification.

## Owner

Blueprint / Maintainer.

## Linked Roadmap Phase

Phase 5: Auth, permissions, and security.

## Linked ExecPlans

EP-006, EP-008, EP-010.

## User-Visible Goal

Human Hand runs locally without accounts while protecting user files, secrets, outputs, logs, cache, and endpoint configuration.

## Non-Goals

- Authentication.
- Authorization roles.
- Accounts.
- Sessions.
- Tokens issued by Human Hand.
- Server-side permissions.
- CSRF/CORS/session management.

## Terms

- External credential: API key/token for user-configured LLM or detector provider.
- Permission boundary: Local filesystem read/write behavior and cache permissions.
- Security baseline: Required controls despite no auth.

## Required Behavior

- No auth code or account model.
- API keys read from env/.env only.
- `.env` ignored.
- Input files read only.
- Output path cannot equal input path.
- Cache file permission best effort `0600`.
- HTTP endpoints rejected unless allowed.
- Secrets redacted in logs/errors.
- User text not logged/cached.
- Security commands pass.

## Inputs

- Env vars.
- CLI paths.
- Config file path if implemented.
- External endpoint URLs.

## Outputs

- Redacted errors/logs.
- Safe output files.
- Cache metadata only.

## Error States

- Missing API key for provider.
- Unsafe endpoint.
- Unsafe output path.
- Secret-looking value detected in artifact/log test.
- User text found in cache/log test.

## Data Rules

- No user text in logs/cache/artifacts/fixtures.
- No secrets in repo or output.
- Cache deletion is safe.

## Security Rules

- Redaction tests required.
- Secret scan required.
- Bandit and pip-audit required.
- Schema validation required for external responses.

## Accessibility Rules

Security errors must be concise and actionable.

## Performance Rules

Security checks should be part of verification and not require network except dependency audit as configured by pip-audit. If audit cannot run due network/tool limitation, record and follow STOP/recovery rules.

## Observability Rules

Security events logged as redacted JSONL. Do not include secret values, request bodies, file contents, or provider text.

## Required Tests

- No auth routes/classes/session state tests by absence/structure where practical.
- Secret redaction tests.
- User text logging tests.
- Endpoint safety tests.
- Safe output path tests.
- Cache no-text and permissions tests.
- Schema validation failure tests.

## Acceptance Criteria

- Auth remains out of scope.
- Security baseline tests pass.
- Security scripts pass or documented accepted findings exist.
- No secrets/user text leaks are present.
```

FILE: .agent/specs/SPEC-006-error-handling.md

```text
# SPEC-006: Error Handling

## Status

Accepted blueprint specification.

## Owner

Blueprint / Maintainer.

## Linked Roadmap Phase

All phases.

## Linked ExecPlans

EP-002 through EP-010.

## User-Visible Goal

Users receive clear, stable, safe errors that explain what failed without leaking source text, style samples, generated output, prompts, responses, or secrets.

## Non-Goals

- Full stack traces in normal CLI output.
- Logging user text for diagnostics.
- Retrying non-retryable failures.
- Interactive approval prompts.

## Terms

- User-facing error: stdout/stderr message intended for CLI user.
- Log error: JSONL stderr event for diagnostics.
- Retryable failure: network error or 5xx response from external endpoint.
- Non-retryable failure: validation error, auth error, schema error, unsafe endpoint, invalid input.

## Required Behavior

- Stable error categories: `input_error`, `config_error`, `io_error`, `external_error`, `schema_error`, `fact_drift_error`, `security_error`, `internal_error`.
- Friendly one-line errors by default.
- JSON error object in `--json` mode.
- Exit codes nonzero for errors.
- Retries up to 3 only for network/5xx.
- Exponential backoff with cap.
- Redacted logs for all failures.
- Bounded retry for coding agents during validation failures.

## Inputs

- Exceptions from domain/application/infra.
- External HTTP statuses/errors.
- CLI parse failures.

## Outputs

- User-facing message.
- JSON error object in `--json` mode.
- Redacted log event.
- Exit code.

## Error States

- Empty input.
- UTF-8/BOM error.
- Input too large.
- Missing config.
- Unsafe endpoint.
- External timeout/retry exhausted.
- Schema validation error.
- Detector unavailable.
- Fact drift unresolved.
- Cache corrupt/unavailable.

## Data Rules

- Error objects must not contain user text except explicit user-facing diff/audit result fields.
- Logs must never contain user text.
- Include hash prefix/length instead of text where helpful.

## Security Rules

- Secrets always redacted.
- Do not log HTTP bodies.
- Do not include API keys in URLs or messages.

## Accessibility Rules

- Errors are short, direct, and avoid color-only meaning.
- Suggest one next action when safe.

## Performance Rules

- Retry cap enforced.
- Timeout default 30 seconds.
- No infinite loops.

## Observability Rules

- Log `event`, `level`, `message`, `retry_reason`, `attempt`, `elapsed_ms`, and endpoint host where applicable.

## Required Tests

- Error mapping tests.
- JSON mode error tests.
- Redaction tests.
- Retry and non-retry tests.
- Exit code tests.
- Empty input and BOM tests.

## Acceptance Criteria

- All known errors map to safe messages.
- No stack traces in normal CLI output.
- No text/secrets in logs.
- Retry behavior is bounded and tested.
```

FILE: .agent/specs/SPEC-007-observability.md

```text
# SPEC-007: Observability

## Status

Accepted blueprint specification.

## Owner

Blueprint / Maintainer.

## Linked Roadmap Phase

Phase 7: Observability and operations.

## Linked ExecPlans

EP-008, EP-010.

## User-Visible Goal

Users and maintainers can diagnose local CLI issues with safe structured logs, counters, and health output without telemetry or sensitive text leakage.

## Non-Goals

- Remote metrics.
- Dashboards.
- Distributed tracing.
- Phone-home.
- Hosted alerts.
- Logging user text.

## Terms

- JSONL log: one JSON object per stderr line.
- Local counter: aggregate event emitted at command end.
- Health command: local configuration/runtime diagnostic command.

## Required Behavior

- Logs to stderr only.
- Human results to stdout only.
- Required log fields implemented where applicable.
- Redaction applied to secrets and text-like fields.
- Local counters emitted for command runs.
- `humanhand health --json` validates config shape without network by default.
- No remote telemetry code.

## Inputs

- Command lifecycle events.
- Config values.
- Retry outcomes.
- Cache hit/miss.
- Timing values.

## Outputs

- JSONL stderr logs.
- JSON health output.
- Local counter events.

## Error States

- Log serialization failure.
- Redaction failure.
- Invalid health config.
- Cache path unavailable.

## Data Rules

- Logs/counters contain no source/style/prompt/output/provider text.
- Hash prefixes and lengths are allowed.
- Endpoint host allowed; path/query disallowed.

## Security Rules

- Redaction before serialization.
- Secret scan covers logging fixtures.
- Tests assert user text absence.

## Accessibility Rules

- Health output supports JSON for machines.
- Human health output is predictable and concise.

## Performance Rules

- Logging overhead target under 5% of run time.
- Health command should not perform external network calls by default.

## Observability Rules

This spec defines observability rules. Changes require docs/tests update.

## Required Tests

- JSONL parse tests.
- Required field tests.
- Redaction tests.
- stdout/stderr separation tests.
- Health command tests.
- No telemetry import/config tests where practical.

## Acceptance Criteria

- Observability tests pass.
- Logs are safe and useful.
- Health command works offline.
- No remote telemetry exists.
```

FILE: .agent/specs/SPEC-008-production-readiness.md

```text
# SPEC-008: Production Readiness

## Status

Accepted blueprint specification.

## Owner

Blueprint / Maintainer.

## Linked Roadmap Phase

Phase 9: Production readiness.

## Linked ExecPlans

EP-009, EP-010.

## User-Visible Goal

Human Hand can be installed and used as a reliable local CLI package with documented privacy, security, release, rollback, and operational behavior.

## Non-Goals

- Hosted deployment.
- Auto-publishing.
- Runtime telemetry.
- Server operations.
- Primary database readiness.

## Terms

- Production: released package installed on user machines.
- Launch gate: final maintainer decision after checks pass.
- Rollback drill: verified steps to return to previous known-good package/config/cache state.

## Required Behavior

- All core commands work.
- All validation scripts pass.
- Wheel/sdist build and install.
- README/CHANGELOG/release notes complete.
- Manual release workflow exists.
- No auto-PyPI publish.
- Rollback path documented.
- Security/privacy/performance/accessibility/observability reviews complete.
- `scripts/loop.sh` prints `build: complete`.

## Inputs

- Repository source.
- Build scripts.
- CI workflows.
- Release docs.
- Test results.

## Outputs

- Wheel/sdist artifacts.
- Verification logs.
- Production readiness report in EP-010.
- Release notes/changelog.

## Error States

- Validation failure.
- Artifact install failure.
- Security/audit finding.
- Missing docs.
- Rollback unclear.
- Secret/user text detected.

## Data Rules

- Artifacts contain no `.env`, `.cache`, secrets, user text, or local test outputs.
- Test data synthetic.

## Security Rules

- Security scripts pass or findings documented/accepted.
- Release publish requires approval.
- No irreversible action by agent.

## Accessibility Rules

- CLI accessibility tests pass.
- Docs explain JSON/no-color behavior.

## Performance Rules

- Smoke under 30 seconds.
- Help/version performance target assessed.
- Input cap and timeout/retry rules tested.

## Observability Rules

- Required logs/counters/health behavior complete.
- No remote telemetry.

## Required Tests

- Full verify.
- Production readiness check.
- Clean wheel install smoke.
- Security/audit scans.
- Artifact content inspection.
- Rollback drill verification.

## Acceptance Criteria

- EP-010 complete.
- `sh scripts/verify.sh` passes.
- `sh scripts/production-readiness-check.sh` passes.
- `sh scripts/loop.sh` prints `build: complete`.
- Maintainer approval status recorded before publishing.
```

FILE: .agent/execplans/EP-000-repository-discovery.md

```text
---
id: EP-000
title: Repository Discovery
status: complete
owner: agent
created: 2026-07-05
updated: 2026-07-05
---

# EP-000: Repository Discovery

## Purpose / Big Picture

Discover repository structure, stack, commands, current implementation state, risks, and missing information before implementation. For this greenfield repository, discovery established that the blueprint pack is the initial control plane and EP-001 must create the Python project foundation.

## Scope

- Inventory files and directories.
- Detect package manager and commands.
- Detect tests and CI.
- Confirm architecture baseline.
- Identify assumptions and risks.
- Update `COMMANDS.md`, `ARCHITECTURE.md`, and `ASSUMPTIONS.md` if repository evidence differs.

## Non-goals

- Implement product code.
- Add dependencies.
- Create CLI behavior beyond discovery docs.
- Run live LLM/detector calls.
- Publish or release artifacts.

## Context and Orientation

The input states the repository is greenfield. This plan is marked complete for the generated blueprint. Re-open it only if the repository contains existing code or unknown files before EP-001.

## Files to Read First

- `AGENTS.md`
- `COMMANDS.md`
- `.agent/PLANS.md`
- `.agent/EXECUTION_RULES.md`
- `PROJECT_BRIEF.md`
- `ASSUMPTIONS.md`
- `ARCHITECTURE.md`

## Files to Change

Expected when re-running discovery only if evidence differs:

- `COMMANDS.md`
- `ARCHITECTURE.md`
- `ASSUMPTIONS.md`
- `.agent/execplans/EP-000-repository-discovery.md`
- `.agent/state/last-result.env`

## Interfaces and Contracts

- Discovery uses shell/git commands only.
- No product API is created.
- Command updates must be supported by repository evidence.

## Milestones

### M1 — Inventory repository

- Goal: Identify existing files and greenfield conflicts.
- Files to read: repository root listing.
- Files to change: this ExecPlan only if findings differ.
- Exact edits expected: Record unexpected existing files in Surprises & Discoveries.
- Validation command: `sh scripts/preflight.sh`
- Expected result: `preflight: ok`
- Recovery: If preflight fails for missing blueprint files, restore required files before continuing. If uv is missing, stop with tool-install blocker.

### M2 — Detect stack and package manager

- Goal: Confirm whether `pyproject.toml`, lock files, or alternative package managers exist.
- Files to read: `pyproject.toml`, `uv.lock`, `poetry.lock`, `requirements.txt`, `setup.cfg` if present.
- Files to change: `ASSUMPTIONS.md`, `COMMANDS.md` if evidence differs.
- Exact edits expected: Record detected package manager and adjust commands only if existing repo evidence contradicts uv requirement.
- Validation command: `sh scripts/preflight.sh`
- Expected result: `preflight: ok`
- Recovery: If multiple package managers exist, record conflict and choose uv only if safe; otherwise STOP.

### M3 — Detect tests and CI

- Goal: Confirm current validation surface.
- Files to read: `tests/`, `.github/workflows/`, script files.
- Files to change: `COMMANDS.md` if existing validation commands differ.
- Exact edits expected: Update command matrix only with evidence.
- Validation command: `sh scripts/preflight.sh`
- Expected result: `preflight: ok`
- Recovery: If tests/CI exist and conflict with blueprint, record and require EP-001 adjustment.

### M4 — Confirm architecture and risk baseline

- Goal: Confirm greenfield architecture and risks.
- Files to read: `ARCHITECTURE.md`, `ASSUMPTIONS.md`, discovered files.
- Files to change: `ARCHITECTURE.md`, `ASSUMPTIONS.md`, this ExecPlan.
- Exact edits expected: Add assumptions or risks found during discovery.
- Validation command: `git diff --name-only`
- Expected result: Only discovery docs changed if any.
- Recovery: If implementation files changed, revert accidental discovery edits unless user requested otherwise.

## Concrete Steps

1. Run `find . -maxdepth 3 -type f | sort` or equivalent safe listing.
2. Run `git status --short`.
3. Inspect package/test/CI files if present.
4. Update docs only if evidence differs from blueprint.
5. Run validation commands.
6. Write `.agent/state/last-result.env` as final file operation if this plan is re-executed.

## Validation and Acceptance

- `sh scripts/preflight.sh` prints `preflight: ok`.
- Repository status and risks are documented.
- No product code was implemented.
- If repository was not greenfield, follow-up ExecPlan changes are documented.

## Idempotence and Recovery

Discovery can be repeated safely. Do not delete files during discovery. If results differ from prior assumptions, update docs and continue only if no STOP condition applies.

## Progress

- [x] M1 — Inventory repository.
- [x] M2 — Detect stack and package manager.
- [x] M3 — Detect tests and CI.
- [x] M4 — Confirm architecture and risk baseline.

## Surprises & Discoveries

- Greenfield status was provided as input; no existing implementation was assumed.
- `scripts/loop.sh` is required by production readiness even though it is additional to the required script list.

## Decision Log

- 2026-07-05: Treat repository as greenfield and make EP-001 responsible for project bootstrap. Reason: input selected greenfield status. Consequence: scripts beyond preflight may fail clearly until EP-001 creates `pyproject.toml`.

## Outcomes & Retrospective

EP-000 is complete for the blueprint baseline. Re-run only if existing repository files are discovered before EP-001.
```

FILE: .agent/execplans/EP-001-foundation.md

```text
---
id: EP-001
title: Foundation
status: not_started
owner: agent
created: 2026-07-05
updated: 2026-07-05
---

# EP-001: Foundation

## Purpose / Big Picture

Bootstrap the Human Hand Python 3.11 repository foundation: package metadata, uv dependency management, source/test layout, linting, typechecking, baseline CLI skeleton, baseline CI, environment validation, verification scripts, and documentation baseline.

## Scope

- Create Python package structure under `src/humanhand`.
- Create `pyproject.toml` and `uv.lock`.
- Configure ruff, mypy, pytest, pytest-cov, pytest-asyncio, respx, httpx, typer, OpenAI SDK, bandit, pip-audit, build.
- Create minimal Typer CLI with `--help`, `--version`, and `health` placeholder.
- Create baseline tests and CI workflow.
- Create `.gitignore`, `README.md`, `CHANGELOG.md`, and license placeholder if absent.
- Make scripts from `COMMANDS.md` work for baseline checks.

## Non-goals

- Implement rewrite, detector, fact diff, scrub, cache, LLM clients, or production release.
- Add GUI/web/TUI/server/auth.
- Add paid detector live behavior.
- Implement directly from `ROADMAP.md`.

## Context and Orientation

This is the first implementation plan after greenfield discovery. Scripts already exist from the blueprint pack but most will fail until `pyproject.toml`, source files, and tests exist. Before editing, inspect the repository for any user-created files and avoid overwriting them.

## Files to Read First

- `AGENTS.md`
- `COMMANDS.md`
- `.agent/PLANS.md`
- `.agent/EXECUTION_RULES.md`
- `PROJECT_BRIEF.md`
- `ARCHITECTURE.md`
- `ENVIRONMENT.md`
- `TESTING.md`
- `.agent/specs/SPEC-000-product-scope.md`
- `.agent/specs/SPEC-003-api-contracts.md`
- `.agent/specs/SPEC-004-ui-ux-behavior.md`

## Files to Change

Expected files:

- `pyproject.toml`
- `uv.lock`
- `.gitignore`
- `README.md`
- `CHANGELOG.md`
- `LICENSE` if missing and maintainer has specified license text; otherwise document blocker.
- `src/humanhand/__init__.py`
- `src/humanhand/__main__.py`
- `src/humanhand/cli/__init__.py`
- `src/humanhand/cli/app.py`
- `src/humanhand/cli/output.py`
- `src/humanhand/infra/__init__.py`
- `src/humanhand/infra/config.py`
- `tests/conftest.py`
- `tests/unit/test_foundation.py`
- `tests/e2e/test_cli_foundation.py`
- `tests/smoke/test_smoke_foundation.py`
- `.github/workflows/ci.yml`
- `COMMANDS.md` only if script commands need evidence-based adjustment.
- `.agent/execplans/EP-001-foundation.md`
- `.agent/state/last-result.env`

## Interfaces and Contracts

- Console script name: `humanhand`.
- Python package: `humanhand`.
- Baseline commands: `humanhand --help`, `humanhand --version`, `humanhand health --json`.
- `health --json` must not call network or read user text.
- Baseline logs must not contain secrets/user text.

## Milestones

### M1 — Create package metadata and uv project

- Goal: Establish installable Python 3.11 project.
- Files to read: `COMMANDS.md`, `ENVIRONMENT.md`.
- Files to change: `pyproject.toml`, `uv.lock`, `.gitignore`.
- Exact edits expected: Add project metadata, dependencies, dev dependencies, ruff/mypy/pytest config, console script, ignored `.env`, `.cache/`, `.venv/`, `dist/`, `build/`, coverage artifacts.
- Validation command: `sh scripts/install.sh`
- Expected result: `install: ok`
- Recovery: If uv sync fails, inspect dependency names/versions in `pyproject.toml`; make smallest correction. If uv missing, STOP with tool-install blocker.

### M2 — Create source skeleton and config baseline

- Goal: Provide importable package and minimal config validation.
- Files to read: `ARCHITECTURE.md`, `ENVIRONMENT.md`.
- Files to change: `src/humanhand/__init__.py`, `src/humanhand/__main__.py`, `src/humanhand/cli/__init__.py`, `src/humanhand/cli/app.py`, `src/humanhand/cli/output.py`, `src/humanhand/infra/__init__.py`, `src/humanhand/infra/config.py`.
- Exact edits expected: Implement Typer app with version option and `health`; implement config dataclass with defaults for max chars, timeout, cache dir, detector provider; no rewrite behavior yet.
- Validation command: `sh scripts/typecheck.sh`
- Expected result: `typecheck: ok`
- Recovery: If typecheck fails, fix annotations/imports only; do not add core behavior.

### M3 — Create baseline tests

- Goal: Establish test harness and smoke baseline.
- Files to read: `TESTING.md`, `SPEC-004`.
- Files to change: `tests/conftest.py`, `tests/unit/test_foundation.py`, `tests/e2e/test_cli_foundation.py`, `tests/smoke/test_smoke_foundation.py`.
- Exact edits expected: Test package import, config defaults, CLI help/version, health JSON, stdout/stderr separation, no network by default.
- Validation command: `sh scripts/test-unit.sh`
- Expected result: `unit tests: ok`
- Recovery: If unit tests fail, fix tests or skeleton to match documented baseline; do not implement future commands.

### M4 — Configure lint, format, typecheck, build

- Goal: Make baseline static and build commands pass.
- Files to read: `COMMANDS.md`, scripts in `scripts/`.
- Files to change: `pyproject.toml`, existing source/tests, scripts only if command mismatch is proven.
- Exact edits expected: Ensure ruff, mypy, pytest markers, coverage config, and build backend are valid.
- Validation command: `sh scripts/verify.sh`
- Expected result: `verify: ok` for baseline, with integration/E2E/smoke directories present and no live network.
- Recovery: Use bounded retry. If a script assumes future functionality, adjust the script to baseline-safe behavior only with COMMANDS.md update.

### M5 — Add CI and documentation baseline

- Goal: Create CI matrix and contributor docs for install/test.
- Files to read: `DEPLOYMENT.md`, `RELEASE.md`, `CONTRIBUTING.md`.
- Files to change: `.github/workflows/ci.yml`, `README.md`, `CHANGELOG.md`, `LICENSE` if safe.
- Exact edits expected: Windows/Ubuntu matrix running install and verify; README with scope/privacy/ethical disclaimer and current skeleton status; changelog unreleased section.
- Validation command: `sh scripts/verify.sh`
- Expected result: `verify: ok`
- Recovery: If CI syntax cannot be validated locally, run local verify and record CI syntax as remaining risk.

## Concrete Steps

1. Run `sh scripts/preflight.sh`.
2. Inspect repository for existing files.
3. Complete M1 through M5 in order.
4. Update Progress after each milestone passes.
5. Run `git diff --name-only` and compare with Files to Change.
6. Write `.agent/state/last-result.env` as final file operation.

## Validation and Acceptance

- All milestone commands pass.
- `humanhand --help`, `humanhand --version`, and `humanhand health --json` work.
- `sh scripts/verify.sh` passes.
- No future-scope commands are implemented except stubs/help if necessary.
- Domain/infra/CLI package skeleton respects architecture boundaries.
- `.env` and `.cache/` are ignored.

## Idempotence and Recovery

If files already exist, inspect and minimally update them. Do not overwrite user-created README/LICENSE without checking content. If license is unspecified, do not invent one; document in Decision Log and leave `LICENSE` absent or placeholder only if repository already has one.

## Progress

- [ ] M1 — Create package metadata and uv project.
- [ ] M2 — Create source skeleton and config baseline.
- [ ] M3 — Create baseline tests.
- [ ] M4 — Configure lint, format, typecheck, build.
- [ ] M5 — Add CI and documentation baseline.

## Surprises & Discoveries

- None yet.

## Decision Log

- 2026-07-05: Planned `src/humanhand` layout with Typer CLI. Reason: aligns with architecture and package requirements. Consequence: tests run against installed package through uv.

## Outcomes & Retrospective

Not started.
```

FILE: .agent/execplans/EP-002-core-domain.md

```text
---
id: EP-002
title: Core Domain
status: not_started
owner: agent
created: 2026-07-05
updated: 2026-07-05
---

# EP-002: Core Domain

## Purpose / Big Picture

Implement pure business/domain logic for style fingerprinting, fact diffing, metadata scrub, prompt contract construction, and repair-loop decisions. This plan creates the product's core guarantees without file I/O, network, CLI, cache, logging, or infra imports.

## Scope

- Domain entities/value objects.
- Style fingerprint extraction.
- Factual anchor extraction and diff report.
- Metadata scrub and audit rules.
- Prompt builder contracts for schema-mode rewrite and repair.
- Repair loop decision logic.
- Unit tests and import-boundary tests.

## Non-goals

- LLM calls.
- Detector provider clients.
- File reads/writes.
- SQLite cache.
- CLI command implementation.
- Live tests.
- Broad refactors outside domain/test files.

## Context and Orientation

EP-001 must be complete. Domain code must remain pure. The application/infra layers will consume domain objects later.

## Files to Read First

- `ARCHITECTURE.md`
- `TESTING.md`
- `.agent/specs/SPEC-001-core-domain.md`
- `.agent/specs/SPEC-006-error-handling.md`
- Existing `src/humanhand/` files
- Existing `tests/` patterns

## Files to Change

Expected files:

- `src/humanhand/domain/__init__.py`
- `src/humanhand/domain/types.py`
- `src/humanhand/domain/style.py`
- `src/humanhand/domain/facts.py`
- `src/humanhand/domain/scrub.py`
- `src/humanhand/domain/prompts.py`
- `src/humanhand/domain/repair.py`
- `tests/unit/domain/test_style.py`
- `tests/unit/domain/test_facts.py`
- `tests/unit/domain/test_scrub.py`
- `tests/unit/domain/test_prompts.py`
- `tests/unit/domain/test_repair.py`
- `tests/unit/domain/test_import_boundaries.py`
- `.agent/execplans/EP-002-core-domain.md`
- `.agent/state/last-result.env`

## Interfaces and Contracts

- Domain functions accept strings/config value objects and return dataclasses or typed dictionaries.
- `scrub_output(text)` returns cleaned text and `ScrubReport`.
- `diff_facts(source, candidate)` returns `FactDiffReport` with omissions/additions/contradictions/preservation score.
- `build_rewrite_prompt(source, style, fingerprint, facts)` returns a schema-oriented prompt contract without side effects.
- `decide_repair(diff, scrub_report, attempt, max_attempts)` returns accept/repair/fail.

## Milestones

### M1 — Define domain types and boundaries

- Goal: Create shared dataclasses/enums/exceptions for domain results.
- Files to read: `SPEC-001`, existing package skeleton.
- Files to change: `src/humanhand/domain/__init__.py`, `src/humanhand/domain/types.py`, `tests/unit/domain/test_import_boundaries.py`.
- Exact edits expected: Add immutable dataclasses for style, facts, scrub, repair; add import-boundary test scanning domain imports for forbidden infra/CLI/http/sqlite/logging modules.
- Validation command: `sh scripts/test-unit.sh`
- Expected result: `unit tests: ok`
- Recovery: If import-boundary test is brittle, narrow it to module import graph and forbidden module names; do not remove the boundary test.

### M2 — Implement style fingerprint

- Goal: Extract deterministic style traits from human sample.
- Files to read: `SPEC-001`, tests patterns.
- Files to change: `src/humanhand/domain/style.py`, `tests/unit/domain/test_style.py`.
- Exact edits expected: Compute sentence length tendencies, paragraph shape, punctuation habits, vocabulary markers, idiom-like repeated phrases, formatting tendencies; handle empty input with domain error.
- Validation command: `sh scripts/test-unit.sh`
- Expected result: `unit tests: ok`
- Recovery: If heuristics overfit tests, simplify to deterministic measurable traits from spec.

### M3 — Implement fact anchors and diff

- Goal: Detect factual preservation risks.
- Files to read: `SPEC-001`, `SPEC-006`.
- Files to change: `src/humanhand/domain/facts.py`, `tests/unit/domain/test_facts.py`.
- Exact edits expected: Extract dates, numbers, named-entity-like spans, quoted phrases, claim sentences; compare source/candidate for omissions, additions, basic contradictions, preservation score.
- Validation command: `sh scripts/test-unit.sh`
- Expected result: `unit tests: ok`
- Recovery: If contradiction detection is unreliable, limit v1 to deterministic number/date/entity conflicts and record limitation in Decision Log.

### M4 — Implement metadata scrub and audit

- Goal: Guarantee clean plain-text output before write.
- Files to read: `SECURITY.md`, `SPEC-001`, `SPEC-002`.
- Files to change: `src/humanhand/domain/scrub.py`, `tests/unit/domain/test_scrub.py`.
- Exact edits expected: Remove BOM, JSON wrappers, Markdown code fences around whole output, provenance/model tags, metadata headers, trailing tags; normalize LF; strip trailing whitespace; exactly one trailing newline.
- Validation command: `sh scripts/test-unit.sh`
- Expected result: `unit tests: ok`
- Recovery: If a scrub rule risks deleting legitimate prose, make it audit-only unless clearly metadata-like and record decision.

### M5 — Implement prompt contracts and repair decisions

- Goal: Build deterministic prompt payloads and repair-loop state transitions.
- Files to read: `SPEC-001`, `SPEC-003`, `ARCHITECTURE.md`.
- Files to change: `src/humanhand/domain/prompts.py`, `src/humanhand/domain/repair.py`, `tests/unit/domain/test_prompts.py`, `tests/unit/domain/test_repair.py`.
- Exact edits expected: Prompt contract requires fact preservation, style match, plain text only, no metadata, schema fields; repair decision accepts/repairs/fails by diff/scrub thresholds and attempt count.
- Validation command: `sh scripts/verify.sh`
- Expected result: `verify: ok`
- Recovery: If full verify fails outside domain from prior baseline, run narrower failing script, fix only plan-related causes, and record unrelated failures as blockers.

## Concrete Steps

1. Run `sh scripts/preflight.sh`.
2. Confirm EP-001 completion.
3. Implement M1-M5 in order.
4. Update Progress after each passing validation.
5. Run `git diff --name-only` and compare to Files to Change.
6. Write `.agent/state/last-result.env` last.

## Validation and Acceptance

- Domain unit tests pass.
- Full verify passes if EP-001 baseline is healthy.
- Domain imports no infra/CLI/network/cache/logging modules.
- Scrub guarantees output normalization.
- Fact diff and prompt contracts are deterministic.

## Idempotence and Recovery

If domain files already exist, preserve public contracts unless tests/specs require change. If domain heuristics differ from plan but satisfy tests/specs, record the decision and continue.

## Progress

- [ ] M1 — Define domain types and boundaries.
- [ ] M2 — Implement style fingerprint.
- [ ] M3 — Implement fact anchors and diff.
- [ ] M4 — Implement metadata scrub and audit.
- [ ] M5 — Implement prompt contracts and repair decisions.

## Surprises & Discoveries

- None yet.

## Decision Log

- 2026-07-05: Plan uses deterministic heuristic fact/style extraction in domain. Reason: local tests must pass without external services. Consequence: v1 fact diff is a conservative guard, not a formal semantic proof.

## Outcomes & Retrospective

Not started.
```

FILE: .agent/execplans/EP-003-data-and-persistence.md

```text
---
id: EP-003
title: Data and Persistence
status: not_started
owner: agent
created: 2026-07-05
updated: 2026-07-05
---

# EP-003: Data and Persistence

## Purpose / Big Picture

Implement safe file I/O and optional SQLite detector-score cache while preserving privacy guarantees: strict UTF-8, BOM rejection, no input overwrite, clean output writes, and no user text persisted outside requested output.

## Scope

- Infra file reader/writer.
- Output normalization integration with domain scrubber.
- Optional SQLite cache schema and repository.
- Cache no-text validation.
- Integration tests with temporary directories.
- Backup/restore and safe cache deletion docs if needed.

## Non-goals

- Primary database.
- Migrations framework.
- Storing user text.
- LLM/detector HTTP clients.
- CLI command polish beyond using file/cache helpers in tests if necessary.

## Context and Orientation

EP-002 domain scrub/diff is available. Infra may import domain scrub types but domain must not import infra. SQLite cache is optional and stores detector score metadata only.

## Files to Read First

- `ARCHITECTURE.md`
- `SECURITY.md`
- `ENVIRONMENT.md`
- `.agent/specs/SPEC-002-data-model.md`
- `src/humanhand/domain/scrub.py`
- Existing infra config files

## Files to Change

Expected files:

- `src/humanhand/infra/files.py`
- `src/humanhand/infra/cache.py`
- `src/humanhand/infra/config.py`
- `src/humanhand/application/ports.py` if cache/file ports are introduced.
- `tests/integration/test_file_io.py`
- `tests/integration/test_detector_cache.py`
- `tests/unit/infra/test_config.py`
- `OPERATIONS.md` if cache troubleshooting changes.
- `.agent/execplans/EP-003-data-and-persistence.md`
- `.agent/state/last-result.env`

## Interfaces and Contracts

- `read_text_strict(path_or_stdin)` returns text or safe error.
- `write_clean_text(path, text, input_paths)` writes UTF-8 LF text after scrub/normalization and refuses input overwrite.
- `DetectorScoreCache.get(key)` and `.put(record)` store score metadata only.
- Cache key includes text hash, provider, model, schema version.

## Milestones

### M1 — Implement strict UTF-8 file reading

- Goal: Safely read user input files.
- Files to read: `SPEC-002`, `SECURITY.md`.
- Files to change: `src/humanhand/infra/files.py`, `tests/integration/test_file_io.py`.
- Exact edits expected: Read bytes, reject BOM, decode strict UTF-8, reject empty input where helper or caller requires, return safe errors without content.
- Validation command: `sh scripts/test-integration.sh`
- Expected result: `integration tests: ok`
- Recovery: If platform path behavior differs, use pathlib and temp paths; do not special-case Windows with unsafe string logic.

### M2 — Implement clean output writing

- Goal: Write only byte-clean output and never overwrite inputs.
- Files to read: `src/humanhand/domain/scrub.py`, `SPEC-002`.
- Files to change: `src/humanhand/infra/files.py`, `tests/integration/test_file_io.py`.
- Exact edits expected: Apply scrub/normalization, write UTF-8 no BOM, LF, exactly one trailing newline, refuse output path same as input path, create parent dirs only when safe/documented.
- Validation command: `sh scripts/test-integration.sh`
- Expected result: `integration tests: ok`
- Recovery: If atomic write introduces temp-file issues, use a simple safe write for v1 and record atomic write as future improvement.

### M3 — Implement detector score cache schema

- Goal: Create optional SQLite cache without user text.
- Files to read: `SPEC-002`, `ARCHITECTURE.md`.
- Files to change: `src/humanhand/infra/cache.py`, `tests/integration/test_detector_cache.py`.
- Exact edits expected: Lazy schema create, indexes by hash/provider/model/schema, get/put, no text columns, best-effort permissions 0600, corrupt cache safe error.
- Validation command: `sh scripts/test-integration.sh`
- Expected result: `integration tests: ok`
- Recovery: If sqlite permission tests are OS-dependent, assert best effort with platform guard; do not remove no-text tests.

### M4 — Wire config and ports

- Goal: Make cache/file helpers configurable without leaking infra into domain.
- Files to read: `src/humanhand/infra/config.py`, `ARCHITECTURE.md`.
- Files to change: `src/humanhand/infra/config.py`, `src/humanhand/application/ports.py`, `tests/unit/infra/test_config.py`.
- Exact edits expected: Add cache dir/enabled config, max chars validation, timeout validation; define Protocols if application ports do not exist.
- Validation command: `sh scripts/typecheck.sh`
- Expected result: `typecheck: ok`
- Recovery: If Protocol imports create cycles, move ports to application layer and update imports only.

### M5 — Full persistence validation

- Goal: Prove file/cache behavior passes full local checks.
- Files to read: Changed files and tests.
- Files to change: This ExecPlan only unless fixes needed.
- Exact edits expected: Update progress, decisions, docs if cache behavior changed.
- Validation command: `sh scripts/verify.sh`
- Expected result: `verify: ok`
- Recovery: Use bounded retry; if dependency audit fails due network/tool outage, record evidence and STOP if required by active phase.

## Concrete Steps

1. Run preflight.
2. Confirm EP-002 complete.
3. Implement file read, file write, cache, config/ports, validation in order.
4. Inspect SQLite schema in tests to prove no text columns.
5. Run diff review.
6. Write last-result file last.

## Validation and Acceptance

- Strict UTF-8/BOM tests pass.
- Output normalization tests pass.
- Input overwrite refusal tests pass.
- Cache schema no-text tests pass.
- Cache permissions best-effort tests pass where supported.
- Full verify passes.

## Idempotence and Recovery

Cache creation is lazy and safe to rerun. If cache schema already exists, migrations must be backward-compatible or cache deletion must be documented as safe. Do not persist text to solve cache misses.

## Progress

- [ ] M1 — Implement strict UTF-8 file reading.
- [ ] M2 — Implement clean output writing.
- [ ] M3 — Implement detector score cache schema.
- [ ] M4 — Wire config and ports.
- [ ] M5 — Full persistence validation.

## Surprises & Discoveries

- None yet.

## Decision Log

- 2026-07-05: Cache rollback is deletion, not migrations. Reason: cache stores no user text and is optional. Consequence: schema code must tolerate missing cache and rebuild.

## Outcomes & Retrospective

Not started.
```

FILE: .agent/execplans/EP-004-api-or-service-layer.md

```text
---
id: EP-004
title: API or Service Layer
status: not_started
owner: agent
created: 2026-07-05
updated: 2026-07-05
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

- [ ] M1 — Define application services and ports.
- [ ] M2 — Implement OpenAI-compatible LLM client.
- [ ] M3 — Implement detector clients and local fallback.
- [ ] M4 — Implement CLI commands.
- [ ] M5 — Full service-layer verification.

## Surprises & Discoveries

- None yet.

## Decision Log

- 2026-07-05: Treat CLI commands as the external API contract. Reason: product is CLI-only. Consequence: SPEC-003 tests CLI/service behavior instead of HTTP routes.

## Outcomes & Retrospective

Not started.
```

FILE: .agent/execplans/EP-005-user-interface-or-client.md

```text
---
id: EP-005
title: User Interface or Client
status: not_started
owner: agent
created: 2026-07-05
updated: 2026-07-05
---

# EP-005: User Interface or Client

## Purpose / Big Picture

Not applicable as GUI/web UI. Human Hand's user interaction layer is the CLI client. This plan polishes CLI UX, machine-friendly output, accessibility, empty/error states, status messages, and no-color behavior.

## Scope

- CLI result rendering.
- JSON-only stdout mode.
- No-color and Windows color behavior.
- Empty input and common error messages.
- Status/progress messages to stderr without user text.
- Help text and docs alignment.
- E2E/acceptance tests.

## Non-goals

- GUI, web UI, TUI, streaming UI, spinners.
- New core rewrite behavior.
- New detector providers.
- Auth or accounts.

## Context and Orientation

EP-004 command contracts exist. This plan refines user-visible behavior without changing underlying domain guarantees.

## Files to Read First

- `.agent/specs/SPEC-004-ui-ux-behavior.md`
- `.agent/specs/SPEC-006-error-handling.md`
- `ARCHITECTURE.md`
- `src/humanhand/cli/app.py`
- `src/humanhand/cli/output.py`
- Existing CLI tests

## Files to Change

Expected files:

- `src/humanhand/cli/app.py`
- `src/humanhand/cli/output.py`
- `src/humanhand/cli/errors.py` if needed.
- `tests/e2e/test_cli_ux.py`
- `tests/e2e/test_cli_json.py`
- `tests/e2e/test_cli_errors.py`
- `tests/smoke/test_cli_smoke.py`
- `README.md`
- `.agent/execplans/EP-005-user-interface-or-client.md`
- `.agent/state/last-result.env`

## Interfaces and Contracts

- `--json` stdout is valid JSON only.
- `--no-color` disables color.
- `NO_COLOR` disables color.
- Generated prose appears on stdout only with `--print`.
- Status and logs go to stderr.
- Exit codes are stable for success vs known errors.

## Milestones

### M1 — Implement JSON and text renderers

- Goal: Centralize CLI output formatting.
- Files to read: `SPEC-004`, `src/humanhand/cli/output.py`.
- Files to change: `src/humanhand/cli/output.py`, `tests/e2e/test_cli_json.py`.
- Exact edits expected: Render success/error objects in text or JSON; JSON mode writes no extra text; no user text in logs.
- Validation command: `sh scripts/test-e2e.sh`
- Expected result: `e2e tests: ok`
- Recovery: If Typer captures stderr/stdout unexpectedly, use CliRunner isolation and assert streams separately.

### M2 — Implement color/no-color and accessibility behavior

- Goal: Make output screen-reader and terminal friendly.
- Files to read: `SPEC-004`, `ENVIRONMENT.md`.
- Files to change: `src/humanhand/cli/output.py`, `src/humanhand/cli/app.py`, `tests/e2e/test_cli_ux.py`.
- Exact edits expected: Honor `--no-color` and `NO_COLOR`; default color off on Windows unless supported; no color-only meaning; no spinners.
- Validation command: `sh scripts/test-e2e.sh`
- Expected result: `e2e tests: ok`
- Recovery: If terminal detection is flaky, default to no color and record decision.

### M3 — Polish empty/error states

- Goal: Provide clear safe messages for common failures.
- Files to read: `SPEC-006`, `SECURITY.md`.
- Files to change: `src/humanhand/cli/app.py`, `src/humanhand/cli/errors.py` if needed, `tests/e2e/test_cli_errors.py`.
- Exact edits expected: Friendly one-line errors for empty input, missing files, BOM, unsafe path, missing config, provider unavailable; JSON error shape in `--json`; no source/style text in messages.
- Validation command: `sh scripts/test-e2e.sh`
- Expected result: `e2e tests: ok`
- Recovery: If error mapping duplicates application logic, move mapping to CLI helper only; do not change domain exceptions broadly.

### M4 — Update smoke and docs

- Goal: Align docs and smoke tests with polished CLI behavior.
- Files to read: `README.md`, `COMMANDS.md`.
- Files to change: `tests/smoke/test_cli_smoke.py`, `README.md`.
- Exact edits expected: Document commands, privacy, no generated stdout unless `--print`, JSON/no-color examples, local fallback.
- Validation command: `sh scripts/smoke-test.sh`
- Expected result: `smoke test: ok`
- Recovery: If smoke exceeds 30 seconds, reduce fixture size and avoid live calls.

### M5 — Full CLI UX verification

- Goal: Prove CLI UX meets spec.
- Files to read: changed tests and docs.
- Files to change: this ExecPlan only unless fixes needed.
- Exact edits expected: Update Progress/Decision Log.
- Validation command: `sh scripts/verify.sh`
- Expected result: `verify: ok`
- Recovery: Use bounded retry; do not relax stdout/stderr or JSON-only requirements.

## Concrete Steps

1. Run preflight.
2. Implement renderers, color, errors, docs/smoke in order.
3. Keep changes in CLI/tests/docs only.
4. Review diff and write final state file.

## Validation and Acceptance

- JSON-only stdout tests pass.
- No-color tests pass.
- Empty/error state tests pass.
- Generated prose hidden unless `--print`.
- Smoke under 30 seconds.
- Full verify passes.

## Idempotence and Recovery

If CLI helpers already exist, extend them rather than duplicate renderers. Prefer default no-color if terminal behavior is uncertain.

## Progress

- [ ] M1 — Implement JSON and text renderers.
- [ ] M2 — Implement color/no-color and accessibility behavior.
- [ ] M3 — Polish empty/error states.
- [ ] M4 — Update smoke and docs.
- [ ] M5 — Full CLI UX verification.

## Surprises & Discoveries

- None yet.

## Decision Log

- 2026-07-05: Treat CLI as nearest equivalent client/UI layer. Reason: project has no GUI/web/TUI. Consequence: accessibility requirements are CLI-focused.

## Outcomes & Retrospective

Not started.
```

FILE: .agent/execplans/EP-006-auth-security-and-permissions.md

```text
---
id: EP-006
title: Auth, Security, and Permissions
status: not_started
owner: agent
created: 2026-07-05
updated: 2026-07-05
---

# EP-006: Auth, Security, and Permissions

## Purpose / Big Picture

Authentication is not applicable. This plan confirms auth remains out of scope and hardens the security baseline: secrets, redaction, endpoint safety, schema validation, safe file permissions, no user-text logging/cache, and security checks.

## Scope

- Confirm no auth/account/session/role code exists.
- Harden redaction filter.
- Enforce endpoint safety.
- Enforce response schema validation.
- Test no user text in logs/cache.
- Ensure `.env` ignored.
- Ensure cache permissions best effort.
- Run Bandit, pip-audit, secret-pattern scan.

## Non-goals

- Implement authentication or authorization.
- Add web security headers, CSRF, CORS, sessions, or roles.
- Add rate-limiting server behavior.
- Add new product features.

## Context and Orientation

Human Hand is a single-user local CLI. Security baseline still matters because user text and secrets are sensitive.

## Files to Read First

- `SECURITY.md`
- `.agent/specs/SPEC-005-auth-and-permissions.md`
- `.agent/specs/SPEC-006-error-handling.md`
- `OBSERVABILITY.md`
- Existing logging/config/http/cache/file code

## Files to Change

Expected files:

- `src/humanhand/infra/logging.py`
- `src/humanhand/infra/config.py`
- `src/humanhand/infra/http.py`
- `src/humanhand/infra/llm.py`
- `src/humanhand/infra/cache.py`
- `src/humanhand/infra/files.py`
- `tests/unit/infra/test_redaction.py`
- `tests/integration/test_security_baseline.py`
- `tests/integration/test_no_text_persistence.py`
- `tests/integration/test_endpoint_security.py`
- `.gitignore`
- `SECURITY.md` if findings require docs updates.
- `.agent/execplans/EP-006-auth-security-and-permissions.md`
- `.agent/state/last-result.env`

## Interfaces and Contracts

- Redaction function accepts arbitrary values and returns safe strings/structures.
- Endpoint validator rejects unsafe HTTP unless allow flag is set.
- Log writer never emits user text/secrets.
- Cache/file helpers enforce no text persistence and safe writes.

## Milestones

### M1 — Confirm auth is absent and `.env` ignored

- Goal: Preserve no-auth scope and secret ignore rules.
- Files to read: repository tree, `.gitignore`, source files.
- Files to change: `.gitignore`, `tests/integration/test_security_baseline.py`.
- Exact edits expected: Add tests/checks that no auth/session/account modules or CLI commands exist; ensure `.env` ignored.
- Validation command: `sh scripts/test-integration.sh`
- Expected result: `integration tests: ok`
- Recovery: If existing names contain auth-like substrings for external API keys, narrow absence test to server auth/account/session concepts.

### M2 — Harden redaction and logging safety

- Goal: Prevent secrets/user text in logs.
- Files to read: `OBSERVABILITY.md`, logging code.
- Files to change: `src/humanhand/infra/logging.py`, `tests/unit/infra/test_redaction.py`, `tests/integration/test_security_baseline.py`.
- Exact edits expected: Redact common key patterns and configured secret values; log only lengths/hashes/hosts; tests use sentinel user text to prove absence.
- Validation command: `sh scripts/test-unit.sh`
- Expected result: `unit tests: ok`
- Recovery: If logs are not centralized, create minimal logging helper and route existing logs through it without broad refactor.

### M3 — Harden endpoint and schema validation

- Goal: Reject unsafe endpoints and invalid external responses.
- Files to read: `src/humanhand/infra/http.py`, `src/humanhand/infra/llm.py`, detector adapters.
- Files to change: `src/humanhand/infra/http.py`, `src/humanhand/infra/llm.py`, detector adapters, `tests/integration/test_endpoint_security.py`.
- Exact edits expected: HTTPS enforcement, localhost/insecure flag behavior, response schema validation failures that do not log bodies.
- Validation command: `sh scripts/test-integration.sh`
- Expected result: `integration tests: ok`
- Recovery: If provider adapter schemas differ, validate common result object after adapter parse and record provider-specific limits.

### M4 — Prove no text persistence and safe permissions

- Goal: Verify files/cache cannot leak user text.
- Files to read: `src/humanhand/infra/cache.py`, `src/humanhand/infra/files.py`.
- Files to change: `tests/integration/test_no_text_persistence.py`, cache/files code if needed.
- Exact edits expected: Tests inspect cache DB bytes/rows for sentinel text absence; safe output path tests; cache permission best effort.
- Validation command: `sh scripts/test-integration.sh`
- Expected result: `integration tests: ok`
- Recovery: If SQLite file contains sentinel due test setup, fix cache record construction; never mask test by changing sentinel.

### M5 — Security verification

- Goal: Run security and audit commands.
- Files to read: `scripts/security-check.sh`, `scripts/dependency-audit.sh`.
- Files to change: this ExecPlan and docs if findings accepted.
- Exact edits expected: Resolve Bandit/pip-audit/secret-scan findings or document accepted non-secrets.
- Validation command: `sh scripts/security-check.sh`
- Expected result: `security check: ok`
- Recovery: If pip-audit/network unavailable during this milestone, run `sh scripts/dependency-audit.sh` separately; apply bounded retry and STOP if required command cannot run.

## Concrete Steps

1. Run preflight.
2. Complete M1-M5 in order.
3. Run `sh scripts/dependency-audit.sh` after security check.
4. Run `sh scripts/verify.sh` if security changes are broad.
5. Review diff and write final state.

## Validation and Acceptance

- No auth system introduced.
- Security tests pass.
- Redaction tests pass.
- Endpoint safety tests pass.
- No text persistence tests pass.
- Security check and dependency audit pass or documented accepted findings exist.

## Idempotence and Recovery

Security hardening can be rerun safely. Do not weaken redaction or endpoint rules for compatibility. Use explicit config gates for local insecure endpoints.

## Progress

- [ ] M1 — Confirm auth is absent and `.env` ignored.
- [ ] M2 — Harden redaction and logging safety.
- [ ] M3 — Harden endpoint and schema validation.
- [ ] M4 — Prove no text persistence and safe permissions.
- [ ] M5 — Security verification.

## Surprises & Discoveries

- None yet.

## Decision Log

- 2026-07-05: No auth implementation will be added. Reason: product is single-user local CLI. Consequence: security work focuses on secrets, text handling, endpoints, and filesystem permissions.

## Outcomes & Retrospective

Not started.
```

FILE: .agent/execplans/EP-007-testing-hardening.md

```text
---
id: EP-007
title: Testing Hardening
status: not_started
owner: agent
created: 2026-07-05
updated: 2026-07-05
---

# EP-007: Testing Hardening

## Purpose / Big Picture

Harden test coverage, reliability, regressions, CI validation, gated live E2E behavior, smoke/performance checks, and coverage thresholds so `sh scripts/verify.sh` is a trustworthy quality gate.

## Scope

- Unit/integration/E2E coverage review.
- Regression tests for critical flows.
- Failure-mode tests.
- Coverage threshold at or above 85%.
- Flaky test policy.
- CI matrix for Windows and Ubuntu.
- Gated live E2E tests.
- Smoke duration under 30 seconds.

## Non-goals

- New product features.
- Live network by default.
- Broad refactors.
- Performance benchmarking beyond required smoke/threshold checks.

## Context and Orientation

EP-001 through EP-006 should be complete. This plan improves confidence without changing product scope.

## Files to Read First

- `TESTING.md`
- `COMMANDS.md`
- `.github/workflows/ci.yml`
- Existing `tests/`
- Existing `pyproject.toml`
- `scripts/verify.sh`

## Files to Change

Expected files:

- `pyproject.toml`
- `.github/workflows/ci.yml`
- `tests/unit/`
- `tests/integration/`
- `tests/e2e/`
- `tests/smoke/`
- `tests/fixtures/` with synthetic text only.
- `scripts/test-e2e.sh` if marker gating needs correction.
- `scripts/verify.sh` if sequencing needs correction.
- `TESTING.md` if policy changes.
- `.agent/execplans/EP-007-testing-hardening.md`
- `.agent/state/last-result.env`

## Interfaces and Contracts

- `sh scripts/verify.sh` is the full local quality gate.
- Live tests skip unless `HUMANHAND_RUN_LIVE_E2E=1`.
- Coverage threshold is configured in pytest/coverage settings.
- Tests must not contain real user data or secrets.

## Milestones

### M1 — Audit test coverage and gaps

- Goal: Identify missing critical coverage.
- Files to read: `tests/`, `TESTING.md`, specs.
- Files to change: this ExecPlan Surprises & Discoveries, maybe `TESTING.md` if policy gap found.
- Exact edits expected: Record gap list for rewrite, verify, diff-facts, scrub, config, redaction, cache, endpoint, CLI JSON, errors.
- Validation command: `sh scripts/test-unit.sh`
- Expected result: `unit tests: ok`
- Recovery: If existing tests fail before changes, fix baseline only if within scope; otherwise STOP with evidence.

### M2 — Add regression and failure-mode tests

- Goal: Cover critical regressions and invalid inputs.
- Files to read: existing source/tests.
- Files to change: `tests/unit/`, `tests/integration/`, `tests/e2e/`, `tests/fixtures/`.
- Exact edits expected: Synthetic fixtures; tests for fact drift, scrub, UTF-8/BOM, unsafe path, no text logs/cache, retry, schema, CLI errors.
- Validation command: `sh scripts/test-unit.sh`
- Expected result: `unit tests: ok`
- Recovery: If fixture text resembles copyrighted/real data, replace with invented synthetic text.

### M3 — Harden integration and E2E gating

- Goal: Ensure no live calls by default and acceptance paths pass.
- Files to read: `scripts/test-e2e.sh`, pytest markers, CI workflow.
- Files to change: `pyproject.toml`, `tests/e2e/`, `tests/integration/`, `scripts/test-e2e.sh` if needed.
- Exact edits expected: Define markers `live`, `live_e2e`; skip live tests unless env set; mocked E2E paths remain default.
- Validation command: `sh scripts/test-e2e.sh`
- Expected result: `e2e tests: ok`
- Recovery: If marker selection skips all E2E tests, add non-live acceptance tests; do not enable live by default.

### M4 — Configure coverage and smoke performance

- Goal: Enforce coverage and smoke duration.
- Files to read: `pyproject.toml`, `tests/smoke/`, `scripts/smoke-test.sh`.
- Files to change: `pyproject.toml`, `tests/smoke/`, `scripts/smoke-test.sh` if needed.
- Exact edits expected: Set coverage >=85%; smoke asserts under 30 seconds on mocks; help/version performance check if practical.
- Validation command: `sh scripts/smoke-test.sh`
- Expected result: `smoke test: ok`
- Recovery: If timing is flaky, assert generous threshold only for complete smoke duration and record help/version timing as measured not hard fail unless stable.

### M5 — CI and full verify hardening

- Goal: Make CI run the same validation gates on Windows/Ubuntu.
- Files to read: `.github/workflows/ci.yml`, `COMMANDS.md`.
- Files to change: `.github/workflows/ci.yml`, `scripts/verify.sh` if sequencing stale.
- Exact edits expected: Matrix for Windows and Ubuntu, Python 3.11, uv install/cache, run install and verify; no live env vars by default.
- Validation command: `sh scripts/verify.sh`
- Expected result: `verify: ok`
- Recovery: If local OS cannot validate Windows path behavior, rely on pathlib tests and record CI matrix as final verifier.

## Concrete Steps

1. Run preflight.
2. Audit gaps.
3. Add tests before code fixes where possible.
4. Fix implementation only when tests expose real gaps within scope.
5. Run full verify and diff review.
6. Write last-result file last.

## Validation and Acceptance

- Coverage >=85%.
- Unit/integration/E2E/smoke tests pass.
- Live tests gated and skipped by default.
- CI matrix exists and runs verify.
- Smoke under 30 seconds.
- `sh scripts/verify.sh` passes.

## Idempotence and Recovery

Adding tests is safe to rerun. If tests reveal bugs outside this plan, fix only critical correctness/security issues needed for the tests; otherwise document and STOP if scope would expand.

## Progress

- [ ] M1 — Audit test coverage and gaps.
- [ ] M2 — Add regression and failure-mode tests.
- [ ] M3 — Harden integration and E2E gating.
- [ ] M4 — Configure coverage and smoke performance.
- [ ] M5 — CI and full verify hardening.

## Surprises & Discoveries

- None yet.

## Decision Log

- 2026-07-05: Coverage target set at >=85%. Reason: production-readiness input. Consequence: scripts/CI must fail below threshold after this plan.

## Outcomes & Retrospective

Not started.
```

FILE: .agent/execplans/EP-008-observability-and-operations.md

```text
---
id: EP-008
title: Observability and Operations
status: not_started
owner: agent
created: 2026-07-05
updated: 2026-07-05
---

# EP-008: Observability and Operations

## Purpose / Big Picture

Add local observability and operational readiness: structured JSONL logs, redaction, local counters, health command completion, operational runbooks, and tests proving no telemetry or text leakage.

## Scope

- Structured JSONL logger to stderr.
- Required log fields.
- Redaction filter integration.
- Local counters emitted at command end.
- Health command with config/cache/platform checks and no network by default.
- Operations docs/runbooks updates.
- Observability tests.

## Non-goals

- Remote metrics, dashboards, traces, alerts, OpenTelemetry exporters, hosted uptime checks.
- New product features.
- Changing CLI contracts except observability output on stderr.

## Context and Orientation

EP-007 should provide strong tests. This plan completes observability behavior required for production readiness.

## Files to Read First

- `OBSERVABILITY.md`
- `.agent/specs/SPEC-007-observability.md`
- `OPERATIONS.md`
- `src/humanhand/infra/logging.py`
- `src/humanhand/cli/app.py`
- Existing observability/security tests

## Files to Change

Expected files:

- `src/humanhand/infra/logging.py`
- `src/humanhand/infra/metrics.py` or `counters.py` if needed.
- `src/humanhand/infra/config.py`
- `src/humanhand/application/services.py`
- `src/humanhand/cli/app.py`
- `src/humanhand/cli/output.py`
- `tests/unit/infra/test_logging.py`
- `tests/integration/test_observability.py`
- `tests/e2e/test_health_command.py`
- `OBSERVABILITY.md`
- `OPERATIONS.md`
- `.agent/execplans/EP-008-observability-and-operations.md`
- `.agent/state/last-result.env`

## Interfaces and Contracts

- Logger emits JSONL dictionaries to stderr.
- Required fields from SPEC-007.
- Counter collector is command-scoped.
- Health command returns JSON-safe diagnostics without network or secrets.

## Milestones

### M1 — Implement structured logging fields

- Goal: Emit parseable JSONL logs with required fields.
- Files to read: `SPEC-007`, existing logging code.
- Files to change: `src/humanhand/infra/logging.py`, `tests/unit/infra/test_logging.py`.
- Exact edits expected: JSON serialization, field normalization, timestamp, event/level/message, lengths/hash prefixes, endpoint host, attempt/retry/cache fields.
- Validation command: `sh scripts/test-unit.sh`
- Expected result: `unit tests: ok`
- Recovery: If log field availability varies, allow null for unavailable fields and document rule.

### M2 — Integrate redaction and no-text log tests

- Goal: Prove logs contain no text/secrets.
- Files to read: `SECURITY.md`, redaction tests.
- Files to change: `src/humanhand/infra/logging.py`, `tests/integration/test_observability.py`.
- Exact edits expected: Route command/external/cache events through logger; tests use sentinel source/style/output/secrets and assert absence in stderr.
- Validation command: `sh scripts/test-integration.sh`
- Expected result: `integration tests: ok`
- Recovery: If CLI writes non-JSON status lines, decide whether status is separate from logs; document and test both without user text.

### M3 — Add local counters

- Goal: Emit end-of-run counters without telemetry.
- Files to read: `OBSERVABILITY.md`.
- Files to change: counter module if needed, application/CLI wiring, tests.
- Exact edits expected: Command-scoped counters for attempts, retries, cache hits/misses, durations, lengths; stderr only.
- Validation command: `sh scripts/test-integration.sh`
- Expected result: `integration tests: ok`
- Recovery: If counters complicate service signatures, inject a lightweight collector with default no-op behavior.

### M4 — Complete health command and docs

- Goal: Provide local health diagnostics and operational docs.
- Files to read: `OPERATIONS.md`, `ENVIRONMENT.md`.
- Files to change: `src/humanhand/application/services.py`, `src/humanhand/cli/app.py`, `tests/e2e/test_health_command.py`, `OPERATIONS.md`, `OBSERVABILITY.md`.
- Exact edits expected: Health reports version, Python/platform, config shape, cache path writable, endpoint URL shape, provider config presence, no network/secrets.
- Validation command: `sh scripts/test-e2e.sh`
- Expected result: `e2e tests: ok`
- Recovery: If platform checks are OS-dependent, assert stable keys and types rather than exact values.

### M5 — Observability full verification

- Goal: Verify observability and operations are production-ready.
- Files to read: changed tests/docs.
- Files to change: this ExecPlan only unless fixes needed.
- Exact edits expected: Update Progress/Decision Log.
- Validation command: `sh scripts/verify.sh`
- Expected result: `verify: ok`
- Recovery: Use bounded retry; do not add remote telemetry to satisfy observability.

## Concrete Steps

1. Run preflight.
2. Implement logging, redaction, counters, health, docs in order.
3. Keep stdout/stderr contracts intact.
4. Run full verify.
5. Write final state file.

## Validation and Acceptance

- JSONL logs parse.
- Required fields present or null by rule.
- No user text/secrets in logs/counters.
- Health command works offline.
- Operations docs updated.
- Full verify passes.

## Idempotence and Recovery

Logging integration can be rerun safely. If duplicate events appear, centralize emission at application boundaries; do not remove required fields.

## Progress

- [ ] M1 — Implement structured logging fields.
- [ ] M2 — Integrate redaction and no-text log tests.
- [ ] M3 — Add local counters.
- [ ] M4 — Complete health command and docs.
- [ ] M5 — Observability full verification.

## Surprises & Discoveries

- None yet.

## Decision Log

- 2026-07-05: Observability is local-only. Reason: product forbids telemetry. Consequence: no dashboards/traces/exporters are implemented.

## Outcomes & Retrospective

Not started.
```

FILE: .agent/execplans/EP-009-deployment-and-release.md

```text
---
id: EP-009
title: Deployment and Release
status: not_started
owner: agent
created: 2026-07-05
updated: 2026-07-05
---

# EP-009: Deployment and Release

## Purpose / Big Picture

Prepare Human Hand for local package deployment and manual release: build artifacts, wheel install, CI/CD release workflow, README install steps, changelog, post-install smoke, and rollback path.

## Scope

- Wheel and source distribution build readiness.
- Console script verification from installed wheel.
- Manual GitHub Actions release workflow that builds artifacts but does not auto-publish to PyPI.
- README installation and configuration docs.
- CHANGELOG and release checklist.
- Rollback docs validation.

## Non-goals

- Automatic PyPI publishing.
- Hosted deployment.
- Server production environment.
- New product behavior.
- Release tagging without approval.

## Context and Orientation

EP-008 should be complete. This plan makes artifacts shippable but does not publish them.

## Files to Read First

- `DEPLOYMENT.md`
- `RELEASE.md`
- `ROLLBACK.md`
- `PRODUCTION_READINESS.md`
- `pyproject.toml`
- `README.md`
- `.github/workflows/ci.yml`

## Files to Change

Expected files:

- `pyproject.toml`
- `README.md`
- `CHANGELOG.md`
- `.github/workflows/release.yml`
- `.github/workflows/ci.yml` if artifact check needs update.
- `scripts/build.sh`
- `scripts/smoke-test.sh`
- `tests/smoke/test_installed_wheel.py` or equivalent if feasible.
- `DEPLOYMENT.md`
- `RELEASE.md`
- `ROLLBACK.md`
- `.agent/execplans/EP-009-deployment-and-release.md`
- `.agent/state/last-result.env`

## Interfaces and Contracts

- Build command: `sh scripts/build.sh`.
- Artifact install: `pip install dist/humanhand-*.whl` in clean env.
- Release workflow is manual (`workflow_dispatch`) and uploads artifacts; no auto publish.
- Rollback is previous wheel reinstall/config restore/cache deletion.

## Milestones

### M1 — Verify package metadata and build config

- Goal: Ensure wheel/sdist metadata is complete and safe.
- Files to read: `pyproject.toml`, `.gitignore`, `README.md`.
- Files to change: `pyproject.toml`, `README.md` if metadata/docs incomplete.
- Exact edits expected: Confirm name/version/description/readme/requires-python/dependencies/entrypoint/license/classifiers/package data; exclude `.env`, `.cache`, tests if not intended.
- Validation command: `sh scripts/build.sh`
- Expected result: `build: ok`
- Recovery: If build includes unwanted files, adjust package include/exclude config and rebuild.

### M2 — Add post-install smoke validation

- Goal: Prove built wheel works in clean environment.
- Files to read: `scripts/smoke-test.sh`, existing smoke tests.
- Files to change: `tests/smoke/test_installed_wheel.py` or smoke docs/scripts if repository pattern differs.
- Exact edits expected: Add smoke procedure for installed `humanhand --version`, `--help`, `health`, synthetic verify/diff/scrub; no live network.
- Validation command: `sh scripts/smoke-test.sh`
- Expected result: `smoke test: ok`
- Recovery: If clean-env creation is too OS-specific for script, document manual command and keep automated smoke using uv-installed console script.

### M3 — Add manual release workflow

- Goal: Build artifacts in CI without auto-publish.
- Files to read: `.github/workflows/ci.yml`, `RELEASE.md`.
- Files to change: `.github/workflows/release.yml`.
- Exact edits expected: `workflow_dispatch`, Python 3.11, uv install, run verify/build, upload dist artifacts, no PyPI publish step.
- Validation command: `sh scripts/verify.sh`
- Expected result: `verify: ok`
- Recovery: If workflow syntax cannot be validated locally, keep simple actions syntax and record CI validation as remaining risk.

### M4 — Update release and rollback docs

- Goal: Document install, release, rollback, privacy, ethical responsibility.
- Files to read: `DEPLOYMENT.md`, `RELEASE.md`, `ROLLBACK.md`, `README.md`, `CHANGELOG.md`.
- Files to change: those docs.
- Exact edits expected: Add pip install steps, wheel install, env vars, local endpoint privacy note, detector fallback, manual approval gates, rollback steps, changelog unreleased entry.
- Validation command: `sh scripts/format-check.sh`
- Expected result: `format check: ok`
- Recovery: If docs lint is not configured, run `sh scripts/lint.sh` and record docs-only review.

### M5 — Release readiness verification

- Goal: Prove release prep passes local gates.
- Files to read: changed files.
- Files to change: this ExecPlan only unless fixes needed.
- Exact edits expected: Update Progress/Decision Log.
- Validation command: `sh scripts/verify.sh`
- Expected result: `verify: ok`
- Recovery: Use bounded retry; do not publish or tag.

## Concrete Steps

1. Run preflight.
2. Build artifact.
3. Smoke test installed/local console script.
4. Add release workflow with manual dispatch only.
5. Update docs.
6. Run verify and diff review.
7. Write final state file.

## Validation and Acceptance

- Build succeeds.
- Smoke succeeds.
- Manual release workflow exists and does not publish.
- README/CHANGELOG/release/rollback docs updated.
- Full verify passes.
- No release tag or PyPI publish performed.

## Idempotence and Recovery

Rebuilding artifacts is safe. Do not commit built artifacts unless release process explicitly calls for them. Do not run publish/tag commands.

## Progress

- [ ] M1 — Verify package metadata and build config.
- [ ] M2 — Add post-install smoke validation.
- [ ] M3 — Add manual release workflow.
- [ ] M4 — Update release and rollback docs.
- [ ] M5 — Release readiness verification.

## Surprises & Discoveries

- None yet.

## Decision Log

- 2026-07-05: Release workflow must be manual and artifact-only. Reason: input forbids auto PyPI publish. Consequence: publishing remains maintainer action outside agent automation.

## Outcomes & Retrospective

Not started.
```

FILE: .agent/execplans/EP-010-production-readiness.md

```text
---
id: EP-010
title: Production Readiness
status: not_started
owner: agent
created: 2026-07-05
updated: 2026-07-05
---

# EP-010: Production Readiness

## Purpose / Big Picture

Bring Human Hand to production readiness by running final verification, security/privacy/performance/accessibility/observability reviews, deployment dry run, rollback drill, documentation review, launch checklist, and final gate documentation.

## Scope

- Full verification.
- Production-readiness check.
- Security and dependency audit review.
- Privacy/no-text review.
- Performance smoke review.
- CLI accessibility review.
- Observability/health review.
- Wheel build/install dry run.
- Rollback drill documentation.
- Final launch gate report.

## Non-goals

- Publishing to PyPI.
- Creating release tag.
- Hosted deployment.
- Adding new features.
- Broad refactors.

## Context and Orientation

EP-000 through EP-009 must be complete. This plan verifies readiness and documents launch status. It may fix small gaps discovered by checks, but should not add product scope.

## Files to Read First

- `PRODUCTION_READINESS.md`
- `RELEASE.md`
- `ROLLBACK.md`
- `DEPLOYMENT.md`
- `OPERATIONS.md`
- `SECURITY.md`
- `OBSERVABILITY.md`
- All specs under `.agent/specs/`
- `COMMANDS.md`
- Active test and CI files

## Files to Change

Expected files:

- `PRODUCTION_READINESS.md`
- `README.md`
- `CHANGELOG.md`
- `RELEASE.md`
- `ROLLBACK.md`
- `DEPLOYMENT.md`
- `OPERATIONS.md`
- `OBSERVABILITY.md`
- `SECURITY.md` if review findings require updates.
- `scripts/production-readiness-check.sh`
- `scripts/loop.sh`
- Tests/source only for small readiness defects discovered by validation.
- `.agent/execplans/EP-010-production-readiness.md`
- `.agent/state/last-result.env`

## Interfaces and Contracts

- `sh scripts/verify.sh` must pass.
- `sh scripts/production-readiness-check.sh` must pass.
- `sh scripts/loop.sh` must print `build: complete`.
- Final report records launch gate result and remaining risks.

## Milestones

### M1 — Full verification baseline

- Goal: Establish all local checks pass before readiness review.
- Files to read: `COMMANDS.md`, scripts, failing outputs if any.
- Files to change: only files needed for small validation fixes and this ExecPlan.
- Exact edits expected: Run verify; fix any small in-scope failures; document failures and fixes.
- Validation command: `sh scripts/verify.sh`
- Expected result: `verify: ok`
- Recovery: Use bounded retry. On third same-root validation failure, change approach or STOP with evidence.

### M2 — Security and privacy review

- Goal: Prove no secrets/user text leaks and security controls pass.
- Files to read: `SECURITY.md`, `TESTING.md`, tests, logs/cache tests.
- Files to change: docs/tests/source only for small findings.
- Exact edits expected: Run security and audit commands; inspect secret scan; verify no text cache/log tests; update docs for accepted findings.
- Validation command: `sh scripts/security-check.sh`
- Expected result: `security check: ok`
- Recovery: If dependency audit separately fails, run `sh scripts/dependency-audit.sh`; fix or record accepted finding with maintainer action needed.

### M3 — Performance, accessibility, and observability review

- Goal: Confirm CLI performance/UX/logging readiness.
- Files to read: `PRODUCTION_READINESS.md`, `OBSERVABILITY.md`, `SPEC-004`, `SPEC-007`.
- Files to change: docs/tests/source for small findings.
- Exact edits expected: Verify smoke under 30 seconds, JSON/no-color tests, help/version target where practical, health/log/counter behavior.
- Validation command: `sh scripts/smoke-test.sh`
- Expected result: `smoke test: ok`
- Recovery: If timing is flaky, use measured evidence and avoid broad optimization; document remaining risk if target cannot be machine-enforced.

### M4 — Deployment dry run and rollback drill

- Goal: Prove artifact build/install and rollback path.
- Files to read: `DEPLOYMENT.md`, `RELEASE.md`, `ROLLBACK.md`.
- Files to change: docs and scripts if gaps found.
- Exact edits expected: Build artifacts, document clean install smoke, document previous-wheel reinstall/config/cache rollback drill; no publish/tag.
- Validation command: `sh scripts/build.sh`
- Expected result: `build: ok`
- Recovery: If clean install cannot be performed locally, record exact blocker and recommended default; do not publish.

### M5 — Production readiness gate

- Goal: Run final readiness command and set loop status.
- Files to read: `scripts/production-readiness-check.sh`, `scripts/loop.sh`, `PRODUCTION_READINESS.md`.
- Files to change: `scripts/production-readiness-check.sh`, `scripts/loop.sh`, docs, this ExecPlan.
- Exact edits expected: Ensure readiness script checks verify/build/smoke/docs and prints success; ensure loop prints `build: complete` only when readiness passes.
- Validation command: `sh scripts/production-readiness-check.sh`
- Expected result: `production readiness: ok`
- Recovery: Do not make readiness script pass by skipping required checks. Fix underlying issues or STOP.

### M6 — Final diff and launch report

- Goal: Complete final review and record launch status.
- Files to read: all changed files.
- Files to change: this ExecPlan, `.agent/state/last-result.env`.
- Exact edits expected: Run diff review; update Outcomes & Retrospective with launch gate, remaining risks, approvals status; write final env file.
- Validation command: `sh scripts/loop.sh`
- Expected result: `build: complete`
- Recovery: If loop fails, inspect readiness script output; fix only readiness gate issues.

## Concrete Steps

1. Run preflight.
2. Confirm EP-000 through EP-009 complete.
3. Complete M1-M6 in order.
4. Do not publish or tag.
5. Run `git diff --name-only`.
6. Write `.agent/state/last-result.env` last.

## Validation and Acceptance

- `sh scripts/verify.sh` passes.
- `sh scripts/security-check.sh` passes.
- `sh scripts/dependency-audit.sh` passes or accepted findings documented.
- `sh scripts/smoke-test.sh` passes.
- `sh scripts/build.sh` passes.
- `sh scripts/production-readiness-check.sh` passes.
- `sh scripts/loop.sh` prints `build: complete`.
- Launch gate report complete.
- No publish/tag/deployment performed.

## Idempotence and Recovery

Production readiness checks can be rerun. Do not weaken readiness scripts. If a check cannot be run due environment limitation, document exact limitation and STOP unless spec allows manual evidence.

## Progress

- [ ] M1 — Full verification baseline.
- [ ] M2 — Security and privacy review.
- [ ] M3 — Performance, accessibility, and observability review.
- [ ] M4 — Deployment dry run and rollback drill.
- [ ] M5 — Production readiness gate.
- [ ] M6 — Final diff and launch report.

## Surprises & Discoveries

- None yet.

## Decision Log

- 2026-07-05: Production readiness does not equal publish. Reason: release/publish requires maintainer approval. Consequence: this plan can verify artifacts but must not tag or publish.

## Outcomes & Retrospective

Not started.
```

FILE: .agent/checklists/agent-readiness.md

```text
# Agent Readiness Checklist

Use before handing an ExecPlan to a coding agent.

- [ ] Exactly one active ExecPlan is named.
- [ ] ExecPlan is self-contained enough for a new agent with no prior conversation.
- [ ] ExecPlan lists exact files to read first.
- [ ] ExecPlan lists exact files to change.
- [ ] ExecPlan lists explicit non-goals.
- [ ] ExecPlan milestones are ordered.
- [ ] Every milestone has goal, files to read, files to change, exact edits, validation command, expected result, and recovery instruction.
- [ ] Commands come from `COMMANDS.md`.
- [ ] Expected command outputs are defined.
- [ ] Acceptance criteria are observable.
- [ ] STOP conditions are explicit through `AGENTS.md`.
- [ ] Recovery and bounded retry rules are present.
- [ ] Diff review is required.
- [ ] No hidden context is required.
- [ ] No vague approval gate such as “ask user if good” remains.
- [ ] Non-goals prevent feature drift.
- [ ] Anti-hallucination guidance is present.
- [ ] Final response requirements are clear.
```

FILE: .agent/checklists/preflight.md

```text
# Preflight Checklist

Run before editing.

- [ ] Repository root contains `AGENTS.md`.
- [ ] Repository root contains `COMMANDS.md`.
- [ ] Repository root contains `.agent/PLANS.md`.
- [ ] Repository root contains active ExecPlan.
- [ ] `sh scripts/preflight.sh` prints `preflight: ok`.
- [ ] `git status --short` reviewed.
- [ ] uv availability checked.
- [ ] Python 3.11 availability checked after EP-001.
- [ ] Required secrets checked only for live paths; local tests need no secrets.
- [ ] `.env` is ignored if present.
- [ ] No local service is required unless active ExecPlan explicitly says so.
- [ ] Known blockers are recorded in the active ExecPlan.
```

FILE: .agent/checklists/implementation.md

```text
# Implementation Checklist

Use during each milestone.

- [ ] Read required docs and active ExecPlan.
- [ ] Inspect existing repository patterns before editing.
- [ ] Confirm commands, imports, APIs, env vars, data models, and dependencies from files.
- [ ] Implement one milestone at a time.
- [ ] Do not broaden scope.
- [ ] Do not do broad refactors or unrelated cleanup.
- [ ] Add or update tests with behavior changes.
- [ ] Keep domain pure.
- [ ] Keep user text out of logs/cache/tests.
- [ ] Validate milestone with exact command.
- [ ] Update Progress after validation passes.
- [ ] Update Decision Log for assumptions, dependencies, or extra files.
- [ ] Continue unless a STOP condition applies.
```

FILE: .agent/checklists/validation.md

```text
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
```

FILE: .agent/checklists/final-review.md

```text
# Final Review Checklist

Complete before final response.

- [ ] All ExecPlan acceptance criteria satisfied.
- [ ] Required final validation commands pass.
- [ ] `git diff --name-only` reviewed.
- [ ] Changed files match Files to Change.
- [ ] Extra changed files justified in Decision Log.
- [ ] Docs updated for behavior/config/security changes.
- [ ] No secrets committed.
- [ ] No real user text in fixtures/logs/cache/artifacts.
- [ ] No production/user data overwritten.
- [ ] No non-goal feature added.
- [ ] Risks documented.
- [ ] Outcomes & Retrospective updated.
- [ ] `.agent/state/last-result.env` written as final file operation.
- [ ] Final response includes required fields from `AGENTS.md`.
```

FILE: .agent/checklists/production-readiness.md

```text
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
```

FILE: .agent/checklists/release.md

```text
# Release Checklist

- [ ] Version updated in single source of truth.
- [ ] CHANGELOG updated.
- [ ] Release candidate criteria met.
- [ ] `sh scripts/verify.sh` passes.
- [ ] `sh scripts/build.sh` passes.
- [ ] Wheel installs in clean Python 3.11 environment.
- [ ] Staging/local smoke tests pass.
- [ ] Artifacts inspected for `.env`, `.cache`, secrets, user text.
- [ ] Release notes drafted.
- [ ] Maintainer approval obtained for tag/publish.
- [ ] Production publish performed manually only after approval.
- [ ] Post-release smoke tests pass.
- [ ] Issue tracker/security channels monitored.
```

FILE: .agent/checklists/rollback.md

```text
# Rollback Checklist

- [ ] Rollback trigger identified.
- [ ] Rollback decision owner identified.
- [ ] Previous known-good version identified.
- [ ] Application rollback method chosen: reinstall previous wheel.
- [ ] Config rollback values identified without exposing secrets.
- [ ] Database consideration: no primary DB; optional cache can be deleted.
- [ ] Rollback command/procedure documented.
- [ ] Verification after rollback completed.
- [ ] Communication drafted if release affected users.
- [ ] Postmortem created for security/privacy/critical regressions.
```

FILE: .agent/checklists/incident-response.md

```text
# Incident Response Checklist

- [ ] Detect: identify report, failing check, or user issue.
- [ ] Triage: classify as security, privacy, correctness, packaging, dependency, or docs.
- [ ] Mitigate: stop release/publish, disable affected path if possible, avoid collecting real user text.
- [ ] Communicate: prepare non-sensitive status and user action if needed.
- [ ] Resolve: fix through an ExecPlan or emergency patch plan.
- [ ] Verify: add regression tests and run required commands.
- [ ] Document: record root cause, impact, fix, and prevention.
- [ ] Follow up: update docs, release notes, security advisory, or rollback process as needed.
```

FILE: .agent/templates/execplan-template.md

```text
---
id: EP-XXX
title: <Title>
status: not_started
owner: agent
created: YYYY-MM-DD
updated: YYYY-MM-DD
---

# EP-XXX: <Title>

## Purpose / Big Picture

State the implementation goal and why it matters. A new agent with no prior conversation must understand the work from this file alone.

## Scope

- In-scope item.

## Non-goals

- Out-of-scope item.

## Context and Orientation

Describe relevant repository state, prior plans, constraints, and assumptions.

## Files to Read First

- `AGENTS.md`
- `COMMANDS.md`
- `.agent/PLANS.md`
- Relevant files.

## Files to Change

Expected files:

- `path/to/file`
- `.agent/execplans/EP-XXX-title.md`
- `.agent/state/last-result.env`

## Interfaces and Contracts

Define functions, commands, files, env vars, schemas, or user-visible behavior that must exist after this plan.

## Milestones

### M1 — <Milestone Name>

- Goal: <goal>
- Files to read: <files>
- Files to change: <files>
- Exact edits expected: <edits>
- Validation command: `<command from COMMANDS.md>`
- Expected result: `<expected output>`
- Recovery: <bounded recovery instruction>

## Concrete Steps

1. Run `sh scripts/preflight.sh`.
2. Complete milestones in order.
3. Validate after each milestone.
4. Update this ExecPlan.
5. Run diff review.
6. Write `.agent/state/last-result.env` last.

## Validation and Acceptance

- Acceptance criterion.

## Idempotence and Recovery

Explain how to rerun safely and how to recover from partial completion.

## Progress

- [ ] M1 — <Milestone Name>.

## Surprises & Discoveries

- None yet.

## Decision Log

- YYYY-MM-DD: <decision>. Reason: <reason>. Consequence: <consequence>.

## Outcomes & Retrospective

Not started.
```

FILE: .agent/templates/spec-template.md

```text
# SPEC-XXX: <Title>

## Status

Draft | Accepted | Superseded.

## Owner

<owner>

## Linked Roadmap Phase

<phase>

## Linked ExecPlans

<ExecPlan ids>

## User-Visible Goal

What user outcome this spec enables.

## Non-Goals

- Non-goal.

## Terms

- Term: definition.

## Required Behavior

- Behavior.

## Inputs

- Input.

## Outputs

- Output.

## Error States

- Error.

## Data Rules

- Data rule.

## Security Rules

- Security rule.

## Accessibility Rules if Applicable

- Accessibility rule or `Not applicable`.

## Performance Rules if Applicable

- Performance rule or `Not applicable`.

## Observability Rules if Applicable

- Observability rule or `Not applicable`.

## Required Tests

- Test.

## Acceptance Criteria

- Criterion.
```

FILE: .agent/templates/adr-template.md

```text
# ADR-XXXX: <Decision Title>

## Status

Proposed | Accepted | Superseded | Rejected

## Date

YYYY-MM-DD

## Owner

<owner>

## Context

What problem or constraint requires a decision?

## Decision

What decision was made?

## Alternatives Considered

- Alternative: tradeoff.

## Consequences

- Positive consequence.
- Negative consequence or risk.

## Validation

How will the decision be validated?

## Links

- Related specs, ExecPlans, files, issues, or docs.
```

FILE: .agent/templates/test-case-template.md

```text
# Test Case: <Name>

## Purpose

What behavior or risk this test covers.

## Layer

Unit | Integration | E2E | Smoke | Security | Performance

## Preconditions

- Required files/config.
- Required env vars, or state that none are required.

## Inputs

- Input data. Use synthetic text only.

## Steps

1. Step.

## Expected Result

- Observable result.

## Privacy/Security Assertions

- No user text in logs/cache.
- No secrets in output.

## Cleanup

- Temporary files/cache cleaned up.

## Regression Link

- Bug/ExecPlan/Decision link if applicable.
```

FILE: .agent/templates/runbook-template.md

```text
# Runbook: <Name>

## Purpose

What operational task or incident this runbook addresses.

## Scope

- In scope.

## Non-goals

- Out of scope.

## Preconditions

- Required access/tools.
- Required approvals.

## Safety Rules

- No user text collection unless explicitly required and approved.
- No secrets in logs or reports.
- Stop for destructive actions without approval.

## Procedure

1. Step.

## Validation

- Command/result or observable check.

## Rollback

- How to undo safely.

## Escalation

- Who/when to escalate.

## Post-Action Documentation

- What to record.
```

FILE: scripts/preflight.sh

```text
#!/usr/bin/env sh
set -eu

cd "$(dirname "$0")/.."

required_files="AGENTS.md COMMANDS.md PROJECT_BRIEF.md ASSUMPTIONS.md ARCHITECTURE.md ROADMAP.md .agent/PLANS.md .agent/EXECUTION_RULES.md"
for file in $required_files; do
  if [ ! -f "$file" ]; then
    echo "ERROR: required file missing: $file" >&2
    exit 1
  fi
done

required_scripts="scripts/install.sh scripts/lint.sh scripts/format-check.sh scripts/typecheck.sh scripts/test-unit.sh scripts/test-integration.sh scripts/test-e2e.sh scripts/build.sh scripts/security-check.sh scripts/dependency-audit.sh scripts/smoke-test.sh scripts/verify.sh scripts/production-readiness-check.sh scripts/loop.sh"
for file in $required_scripts; do
  if [ ! -f "$file" ]; then
    echo "ERROR: required script missing: $file" >&2
    exit 1
  fi
done

if ! command -v uv >/dev/null 2>&1; then
  echo "ERROR: uv is required for development commands. Install uv before continuing." >&2
  exit 1
fi

if [ -f .env ]; then
  if [ -f .gitignore ] && grep -qxF ".env" .gitignore; then
    :
  else
    echo "ERROR: .env exists but is not ignored exactly by .gitignore." >&2
    exit 1
  fi
fi

if [ -f pyproject.toml ]; then
  if ! grep -q "humanhand" pyproject.toml; then
    echo "ERROR: pyproject.toml exists but does not mention humanhand. Inspect before continuing." >&2
    exit 1
  fi
else
  echo "preflight: pyproject.toml not found; EP-001 must create it" >&2
fi

echo "preflight: ok"
```

FILE: scripts/install.sh

```text
#!/usr/bin/env sh
set -eu

cd "$(dirname "$0")/.."

if [ ! -f pyproject.toml ]; then
  echo "ERROR: pyproject.toml not found. Complete EP-001 before running install." >&2
  exit 1
fi

uv sync --all-extras --dev

echo "install: ok"
```

FILE: scripts/lint.sh

```text
#!/usr/bin/env sh
set -eu

cd "$(dirname "$0")/.."

if [ ! -f pyproject.toml ]; then
  echo "ERROR: pyproject.toml not found. Complete EP-001 before running lint." >&2
  exit 1
fi

uv run ruff check .

echo "lint: ok"
```

FILE: scripts/format-check.sh

```text
#!/usr/bin/env sh
set -eu

cd "$(dirname "$0")/.."

if [ ! -f pyproject.toml ]; then
  echo "ERROR: pyproject.toml not found. Complete EP-001 before running format check." >&2
  exit 1
fi

uv run ruff format --check .

echo "format check: ok"
```

FILE: scripts/typecheck.sh

```text
#!/usr/bin/env sh
set -eu

cd "$(dirname "$0")/.."

if [ ! -f pyproject.toml ]; then
  echo "ERROR: pyproject.toml not found. Complete EP-001 before running typecheck." >&2
  exit 1
fi

if [ ! -d src ]; then
  echo "ERROR: src/ not found. Complete EP-001 before running typecheck." >&2
  exit 1
fi

uv run mypy src tests

echo "typecheck: ok"
```

FILE: scripts/test-unit.sh

```text
#!/usr/bin/env sh
set -eu

cd "$(dirname "$0")/.."

if [ ! -d tests/unit ]; then
  echo "ERROR: tests/unit not found. Complete EP-001 before running unit tests." >&2
  exit 1
fi

uv run pytest tests/unit -m "not live and not live_e2e"

echo "unit tests: ok"
```

FILE: scripts/test-integration.sh

```text
#!/usr/bin/env sh
set -eu

cd "$(dirname "$0")/.."

if [ ! -d tests/integration ]; then
  echo "ERROR: tests/integration not found. Complete EP-001 before running integration tests." >&2
  exit 1
fi

uv run pytest tests/integration -m "not live and not live_e2e"

echo "integration tests: ok"
```

FILE: scripts/test-e2e.sh

```text
#!/usr/bin/env sh
set -eu

cd "$(dirname "$0")/.."

if [ ! -d tests/e2e ]; then
  echo "ERROR: tests/e2e not found. Complete EP-001 before running E2E tests." >&2
  exit 1
fi

if [ "${HUMANHAND_RUN_LIVE_E2E:-}" = "1" ]; then
  uv run pytest tests/e2e
else
  uv run pytest tests/e2e -m "not live and not live_e2e"
fi

echo "e2e tests: ok"
```

FILE: scripts/build.sh

```text
#!/usr/bin/env sh
set -eu

cd "$(dirname "$0")/.."

if [ ! -f pyproject.toml ]; then
  echo "ERROR: pyproject.toml not found. Complete EP-001 before running build." >&2
  exit 1
fi

uv run python -m build

echo "build: ok"
```

FILE: scripts/security-check.sh

```text
#!/usr/bin/env sh
set -eu

cd "$(dirname "$0")/.."

if [ ! -d src ]; then
  echo "ERROR: src/ not found. Complete EP-001 before running security check." >&2
  exit 1
fi

uv run bandit -q -r src

if grep -RIE --exclude-dir=.git --exclude-dir=.venv --exclude-dir=dist --exclude-dir=build --exclude-dir=.cache --exclude=uv.lock 'sk-[A-Za-z0-9_-]{20,}|ghp_[A-Za-z0-9]{20,}|xox[baprs]-[A-Za-z0-9-]{20,}|AKIA[0-9A-Z]{16}' . >/tmp/humanhand-secret-scan.txt 2>/dev/null; then
  cat /tmp/humanhand-secret-scan.txt >&2
  rm -f /tmp/humanhand-secret-scan.txt
  echo "ERROR: possible committed secret detected." >&2
  exit 1
fi
rm -f /tmp/humanhand-secret-scan.txt

echo "security check: ok"
```

FILE: scripts/dependency-audit.sh

```text
#!/usr/bin/env sh
set -eu

cd "$(dirname "$0")/.."

if [ ! -f pyproject.toml ]; then
  echo "ERROR: pyproject.toml not found. Complete EP-001 before running dependency audit." >&2
  exit 1
fi

uv run pip-audit

echo "dependency audit: ok"
```

FILE: scripts/smoke-test.sh

```text
#!/usr/bin/env sh
set -eu

cd "$(dirname "$0")/.."

if [ ! -d tests/smoke ]; then
  echo "ERROR: tests/smoke not found. Complete EP-001 before running smoke tests." >&2
  exit 1
fi

uv run pytest tests/smoke -m "not live and not live_e2e"

echo "smoke test: ok"
```

FILE: scripts/verify.sh

```text
#!/usr/bin/env sh
set -eu

cd "$(dirname "$0")/.."

sh scripts/preflight.sh
sh scripts/lint.sh
sh scripts/format-check.sh
sh scripts/typecheck.sh
sh scripts/test-unit.sh
sh scripts/test-integration.sh
sh scripts/test-e2e.sh
sh scripts/build.sh
sh scripts/security-check.sh
sh scripts/dependency-audit.sh
sh scripts/smoke-test.sh

echo "verify: ok"
```

FILE: scripts/production-readiness-check.sh

```text
#!/usr/bin/env sh
set -eu

cd "$(dirname "$0")/.."

sh scripts/verify.sh

required_docs="PROJECT_BRIEF.md ARCHITECTURE.md SECURITY.md ENVIRONMENT.md DEPLOYMENT.md OPERATIONS.md OBSERVABILITY.md PRODUCTION_READINESS.md RELEASE.md ROLLBACK.md README.md CHANGELOG.md"
for file in $required_docs; do
  if [ ! -f "$file" ]; then
    echo "ERROR: production readiness doc missing: $file" >&2
    exit 1
  fi
done

if git ls-files --error-unmatch .env >/dev/null 2>&1; then
  echo "ERROR: .env is tracked. Remove it before production readiness." >&2
  exit 1
fi

if [ ! -d dist ]; then
  echo "ERROR: dist/ not found after build." >&2
  exit 1
fi

if ! ls dist/humanhand-* >/dev/null 2>&1; then
  echo "ERROR: humanhand build artifacts not found in dist/." >&2
  exit 1
fi

echo "production readiness: ok"
```

FILE: scripts/loop.sh

```text
#!/usr/bin/env sh
set -eu

cd "$(dirname "$0")/.."

sh scripts/production-readiness-check.sh >/dev/null

echo "build: complete"
```

# How to Use This Blueprint Pack

1. Copy the generated files into the repository root, preserving paths and executable bits for scripts.
2. Choose one active ExecPlan under `.agent/execplans/`; start with `EP-001-foundation.md` because `EP-000` is complete for the greenfield baseline.
3. Run `sh scripts/preflight.sh` from repository root.
4. Run a lower-tier coding LLM with the execution prompt in `.agent/prompts/execute-active-execplan.md`.
5. To continue partial work, use `.agent/prompts/continue-execplan.md` and resume at the first incomplete milestone.
6. To debug failing validation, use `.agent/prompts/debug-validation-failure.md` and the bounded retry rule.
7. For final review, use `.agent/prompts/final-review.md`, run required validation, review `git diff --name-only`, and update Outcomes & Retrospective.
8. Decide production readiness only after EP-010, `sh scripts/verify.sh`, `sh scripts/production-readiness-check.sh`, and `sh scripts/loop.sh` pass.
9. Do not implement from `ROADMAP.md` directly; roadmap is strategic only.
10. As the repository evolves, update specs, ExecPlans, `COMMANDS.md`, architecture docs, and decisions before implementation drifts.

Generic lower-tier coding LLM invocation prompt:

Read AGENTS.md, COMMANDS.md, .agent/PLANS.md, and [EXECPLAN_PATH].
Implement [EXECPLAN_PATH] to completion.
Do not ask for next steps.
Do not implement from ROADMAP.md directly.
Do not broaden scope.
Complete milestones in order.
Validate after each milestone.
Update the ExecPlan as you work.
Use only commands from COMMANDS.md.
Stop only for STOP conditions in AGENTS.md.
At the end, run the required verification command, run git diff --name-only, update Outcomes & Retrospective, and report changed files, commands run, results, decisions, risks, and acceptance status.

Codex-style example:

    codex --cd . \
      --ask-for-approval never \
      --sandbox workspace-write \
      "Read AGENTS.md, COMMANDS.md, .agent/PLANS.md, and .agent/execplans/EP-001-foundation.md. Implement EP-001-foundation.md to completion. Do not ask for next steps. Stop only for STOP conditions in AGENTS.md. Update the ExecPlan as you work. Run validation after each milestone."

If the runner does not support those flags, paste the same instruction into any coding agent that can read files, edit files, and run terminal commands.
