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
