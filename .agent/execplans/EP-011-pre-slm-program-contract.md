---
id: EP-011
title: Pre-SLM Program Contract and Architecture Migration
status: completed
owner: agent
created: 2026-08-12
updated: 2026-08-12
---

# EP-011: Pre-SLM Program Contract and Architecture Migration

## Purpose / Big Picture

Bootstrap the user-approved Pre-SLM Hardening Program as a self-contained control
plane. Establish the program manifest, ADRs, specifications, future ExecPlans, SLM
handoff boundary, and source-of-truth documentation without adding functional SLM or
pre-SLM product code.

## Scope

- Import the supplied blueprint and bootstrap prompt at repository root.
- Create `.agent/programs/`, eight ADRs, nine specs, and EP-011 through EP-019.
- Create the documentation-only `SLM_HANDOFF_CONTRACT.md`.
- Update core architecture, project, CLI, security, testing, roadmap, and handoff docs.
- Repair only the evidence-backed Windows `uv.cmd` shell-resolution defect needed by
  the canonical preflight and validation scripts.

## Non-goals

- Implementing importers, stores, exporters, lexical rules, Beacon, or new CLI code.
- Training, downloading, or running an SLM.
- Choosing a license, publishing, tagging, deploying, or changing Git history.

## Context and Orientation

EP-000 through EP-010 are complete for the existing local CLI. The supplied blueprint
extends the sequence to EP-019. Existing compatibility contracts remain authoritative
until a later plan explicitly migrates them.

## Files to Read First

- `AGENTS.md`
- `COMMANDS.md`
- `.agent/PLANS.md`
- `.agent/EXECUTION_RULES.md`
- `ARCHITECTURE.md`
- `PROJECT_BRIEF.md`
- `SECURITY.md`
- `TESTING.md`
- `ROADMAP.md`
- `REPO_BRIEF.md`
- `CLAUDE.md`
- `.agent/state/last-result.env`
- `HumanHand_PreSLM_Implementation_Blueprint.md`
- `CODEX_BOOTSTRAP_PROMPT_HUMANHAND_PRE_SLM.md`
- `EP-010-production-readiness.md`

## Files to Change

- Root blueprint, bootstrap prompt, and `SLM_HANDOFF_CONTRACT.md`.
- `.agent/programs/PRE-SLM-HARDENING-PROGRAM.md`.
- `.agent/adrs/ADR-001` through `ADR-008`.
- `.agent/specs/SPEC-009` through `SPEC-017`.
- `.agent/execplans/EP-011` through `EP-019`.
- `AGENTS.md`, `CLAUDE.md`, `ARCHITECTURE.md`, `PROJECT_BRIEF.md`, `REPO_BRIEF.md`,
  `README.md`, `COMMANDS.md`, `ROADMAP.md`, `SECURITY.md`, `TESTING.md`,
  `ASSUMPTIONS.md`, `DECISIONS.md`, `CHANGELOG.md`, `ENVIRONMENT.md`,
  `CONTRIBUTING.md`, `PRODUCTION_READINESS.md`, `RELEASE.md`, `ROLLBACK.md`,
  `DEPLOYMENT.md`, `OPERATIONS.md`, and `OBSERVABILITY.md` as needed to remove
  contradictions.
- `scripts/uv.sh` and existing canonical scripts only for Windows uv resolution.
- `.agent/state/continuation.md` and `.agent/state/last-result.env` at handoff.

## Interfaces and Contracts

- The program manifest names EP-011 as active and EP-012 through EP-019 as planned.
- Every plan contains all required `.agent/PLANS.md` sections.
- `SLM_HANDOFF_CONTRACT.md` documents a future `WriterClient` only; it contains no
  implementation import or runtime.
- The current five public CLI commands remain available and unchanged in this plan.
- `sh scripts/preflight.sh` must print `preflight: ok` when run through RTK.

## Milestones

### M1 - Bootstrap source and control plane

- Goal: make the blueprint, prompt, program, ADRs, specs, and plans present.
- Files to read: supplied blueprint, prompt, `.agent/PLANS.md`.
- Files to change: all new control-plane files and root documents.
- Exact edits: add the files listed in the blueprint; mark EP-011 active and later plans
  planned; create no forbidden SLM paths.
- Validation: `sh scripts/preflight.sh`.
- Expected result: `preflight: ok`.
- Recovery: inspect missing/duplicate paths and apply the smallest additive correction.

### M2 - Architecture and compatibility migration

- Goal: remove contradictory single-string, no-persistence, and SLM-scope claims.
- Files to read: `ARCHITECTURE.md`, `PROJECT_BRIEF.md`, `README.md`, `SECURITY.md`,
  `TESTING.md`, `ROADMAP.md`, `REPO_BRIEF.md`, and `CLAUDE.md`.
- Files to change: source-of-truth docs and the documented command wrapper.
- Exact edits: describe four channels, dual ingress, privacy modes, public artifacts,
  deterministic finalization, Beacon limits, compatibility, and deferred SLM work.
- Validation: `git diff --name-only` and `git status --short --branch`.
- Expected result: only listed or Decision-Log-justified files are changed.
- Recovery: revert no user work; narrow the patch and document any extra file.

### M3 - Serena and Obsidian orientation

- Goal: make new control-plane files discoverable without publishing local workspace
  state.
- Files to read: `REPO_BRIEF.md`, `.serena/project.yml`, `.obsidian/` metadata.
- Files to change: `REPO_BRIEF.md` and Serena memories; do not make `.obsidian/` or
  `.serena/memories/` authoritative.
- Exact edits: link the blueprint, bootstrap prompt, program manifest, active plan,
  SLM handoff, and state files from the compact repo hub; keep LSP/Markdown support.
- Validation: `sh scripts/preflight.sh`.
- Expected result: `preflight: ok` and the link hub resolves to existing files.
- Recovery: preserve existing workspace settings and use additive links only.

### M4 - Boundary handoff

- Goal: complete EP-011 and hand the repository to Claude for EP-012.
- Files to read: active plan, diff, status, state files.
- Files to change: EP-011, continuation state, and final result state.
- Exact edits: update Progress, Discoveries, Decision Log, Outcomes, and write state last.
- Validation: `git diff --name-only`, `git status --short --branch`, and
  `sh scripts/preflight.sh`.
- Expected result: EP-011 is complete, EP-012 is the first incomplete plan, and no
  later plan has started.
- Recovery: stop with exact blocker and keep the current plan active if a gate fails.

## Concrete Steps

1. Verify the imported root files against the archive hashes.
2. Read the authority stack and blueprint in full.
3. Add the control-plane files and SLM handoff contract.
4. Update only documentation and the evidence-backed shell wrapper needed for the
   documented Windows command surface.
5. Re-onboard Serena memories and refresh the Obsidian-facing repo brief.
6. Run every milestone validation, review tracked and untracked changes, and write
   the state handoff as the final repository file operation.

## Validation and Acceptance

- `sh scripts/preflight.sh` passes through RTK.
- The two supplied Markdown files exist byte-for-byte at the root.
- All required program, ADR, spec, and plan files exist and are internally linked.
- EP-011 is complete; EP-012 is planned and next; EP-013 through EP-019 are untouched.
- No SLM, training, model, runtime, or forbidden path is created.
- Existing docs state that license selection, publishing, live calls, and deployment
  remain separately gated.

## Idempotence and Recovery

Re-running the plan must inspect existing files before editing, never overwrite user
work, never duplicate ADR/spec/plan files, and preserve existing `.obsidian/` and local
Serena state. If the shell toolchain is missing, record the exact failure rather than
claiming a green validation.

## Progress

- [x] Read authority files and supplied blueprint/prompt.
- [x] Import the two root Markdown documents.
- [x] Add the program, ADR, and specification control plane.
- [x] Add all ExecPlans and SLM handoff contract.
- [x] Update authoritative documentation and orientation memories.
- [x] Validate and complete the handoff.

## Surprises & Discoveries

- The installed Windows uv entry point is `uv.cmd`; nested Git Bash shells do not
  resolve it as bare `uv`, even though the Windows PATH contains it.
- Serena already has Markdown, Bash, YAML, TOML, and Python LSP support and an additive
  ignored-path configuration; no Obsidian layout change is required.
- The existing CLI remains compatible after routing all canonical uv calls through the
  resolver: direct version/help checks and all 277 E2E tests passed.

## Decision Log

- 2026-08-12: Bootstrap EP-011 from the supplied blueprint. Reason: the user requested
  the Pre-SLM program before any implementation work. Consequence: later plans are
  created but not executed.
- 2026-08-12: Add `scripts/uv.sh` and route canonical scripts through it. Reason: the
  required preflight could not discover the installed Windows `uv.cmd` from nested
  Git Bash. Consequence: canonical commands remain unchanged while resolving both
  native `uv` and Windows `uv.cmd`.
- 2026-08-12: Keep `.obsidian/` and `.serena/memories/` local-only. Reason: they are
  workspace/runtime state, not authoritative product data. Consequence: orientation
  lives in `REPO_BRIEF.md` and Serena memories.
- 2026-08-12: License remains pending. Reason: maintainer has not chosen one.
  Consequence: no license claim or publication action is added.
- 2026-08-12: Update the authoritative docs in the same bootstrap boundary. Reason:
  the old roadmap and architecture described EP-010 as the final seam and denied the
  selected local state/controlled parser boundaries. Consequence: docs now distinguish
  the completed compatibility baseline from the planned Pre-SLM program.

## Outcomes & Retrospective

EP-011 completed the documentation/control-plane bootstrap without adding product or
SLM implementation. The two supplied Markdown files are present byte-for-byte at the
repository root. The program manifest, eight ADRs, nine specifications, EP-011 through
EP-019, and the documentation-only SLM handoff contract are present; EP-011 is complete
and EP-012 is the next plan.

Validation evidence:

- `sh scripts/uv.sh --version` -> uv 0.11.25.
- `sh scripts/preflight.sh` -> `preflight: ok`.
- `sh scripts/cli.sh --help` -> existing five-command help surface.
- `sh scripts/cli.sh --version` -> `humanhand 1.0.0`.
- `sh scripts/test-e2e.sh` -> `277 passed`, `e2e tests: ok`.
- Archive and repository SHA-256 hashes match for both imported Markdown files.
- Serena was re-onboarded with updated core, stack, command, convention, and completion
  memories; Obsidian local workspace state was preserved and the repo brief is the link hub.

The repository is ready for Claude to begin EP-012. License selection, live external
calls, publication, tagging, deployment, and all SLM work remain explicitly pending.
