---
id: EP-001
title: Foundation
status: in_progress
owner: agent
created: 2026-07-05
updated: 2026-07-06
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

- 2026-07-06: The repository already includes `.obsidian/`, `.serena/`, and a repo-root `CLAUDE.md`, so the user requested a repo-local workflow optimization pass before EP-001 package/bootstrap milestones.
- 2026-07-06: `rtk sh scripts/preflight.sh` reported `preflight: pyproject.toml not found; EP-001 must create it` and then `preflight: ok`, which matches the greenfield blueprint expectation.
- 2026-07-06: `rtk git diff --name-only` failed with `warning: Not a git repository` even though a `.git/` path exists. Narrow diagnostics showed `.git/` is present but empty, with no `HEAD` or `config`, so final diff review cannot run until the checkout is repaired or initialized.
- 2026-07-06: `gh auth status` showed the configured `dominator509` token is invalid for local GitHub CLI usage, even though the Codex GitHub connector can access `dominator509/HumanHand`.
- 2026-07-06: The existing remote GitHub repository `dominator509/HumanHand` already exists as a private repository with default branch `main`.

## Decision Log

- 2026-07-05: Planned `src/humanhand` layout with Typer CLI. Reason: aligns with architecture and package requirements. Consequence: tests run against installed package through uv.
- 2026-07-06: Per explicit user instruction, perform a repo-local agent workflow setup pass before EP-001 implementation milestones. Reason: the repo needed Obsidian, Serena, Claude, Codex, and RTK alignment before bulk coding begins. Consequence: EP-001 remains the active plan, but no product milestones are checked off in this session.
- 2026-07-06: Added `REPO_BRIEF.md`, updated `AGENTS.md`, `CLAUDE.md`, and `.serena/project.yml`, and created `.agent/state/continuation.md` to support the paired Claude-main / Codex-audit loop. Reason: these are the smallest durable control-plane surfaces for the requested workflow. Consequence: these are extra changed files relative to EP-001 Files to Change and are intentionally justified here.
- 2026-07-06: Did not repair or initialize Git during this setup pass. Reason: the user asked for workflow/tooling optimization, not Git recovery, and Git initialization changes repository history/state ownership. Consequence: final diff review remains a known blocker/risk until the worktree is repaired.
- 2026-07-06: Added Git/GitHub operational commands to `COMMANDS.md` for repository initialization, local author config, remote wiring, commit, auth status, and push. Reason: the user explicitly requested a GitHub-connected local repo that works with Codex sidebar commit/push actions. Consequence: `COMMANDS.md` is an intentional extra changed file for this session.
- 2026-07-06: Created a repository `.gitignore` that ignores transient caches, agent state, local Serena state, and local Obsidian workspace state while keeping durable repo docs and shared config versionable. Reason: the user asked for a proper Git ignore policy before initial publish. Consequence: local-only workspace noise should not pollute future commits or Codex sidebar state.
- 2026-07-06: Created `README.md` from the architecture and project brief, documenting product scope, privacy rules, current EP-001 status, and the planned layer boundaries. Reason: the user explicitly requested a README built from the architecture before initial commit/push. Consequence: EP-001 documentation baseline is partially advanced without claiming the full milestone complete.
- 2026-07-06: Recreated `.git/` under the desktop user context, set local Git author to `dominator509 <155886966+dominator509@users.noreply.github.com>`, and configured `origin` to `https://github.com/dominator509/HumanHand.git`. Reason: the original `.git/` was an empty broken stub and Codex sidebar Git actions need a valid local repo plus remote. Consequence: local Git metadata now matches the intended GitHub repository, but push still depends on valid desktop authentication.

## Outcomes & Retrospective

Repo-local workflow surfaces were tightened before EP-001 bootstrap implementation, and the repository is now being converted into a valid local Git checkout for publishability. Obsidian now has a durable link hub in `REPO_BRIEF.md`, Serena is configured Python-first with low-noise ignores and an initial prompt, `.gitignore` and `README.md` now exist, and the local repo has been reinitialized against the existing private GitHub remote. No EP-001 milestone is complete yet because package/bootstrap work has not started, and successful push still depends on desktop GitHub authentication.
