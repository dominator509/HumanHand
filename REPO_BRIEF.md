---
aliases:
  - Repo Brief
tags:
  - repo
  - control-plane
  - obsidian
  - serena
  - claude
  - codex
---

# REPO_BRIEF

## Purpose

Human Hand is a Windows-first Python 3.11 CLI with a completed EP-010 compatibility
baseline and an active Pre-SLM hardening program. Work remains ExecPlan-driven from
`.agent/`; the fastest durable orientation surface is this note plus the active plan
and handoff state.

## Start Here

- Authority stack: [AGENTS.md](AGENTS.md), [COMMANDS.md](COMMANDS.md), [.agent/PLANS.md](.agent/PLANS.md), [.agent/EXECUTION_RULES.md](.agent/EXECUTION_RULES.md)
- Product context: [PROJECT_BRIEF.md](PROJECT_BRIEF.md), [ARCHITECTURE.md](ARCHITECTURE.md), [ENVIRONMENT.md](ENVIRONMENT.md), [TESTING.md](TESTING.md)
- Current program: [.agent/programs/PRE-SLM-HARDENING-PROGRAM.md](.agent/programs/PRE-SLM-HARDENING-PROGRAM.md)
- Current implementation seam: [.agent/execplans/EP-011-pre-slm-program-contract.md](.agent/execplans/EP-011-pre-slm-program-contract.md)
- Blueprint: [HumanHand_PreSLM_Implementation_Blueprint.md](HumanHand_PreSLM_Implementation_Blueprint.md)
- Bootstrap prompt: [CODEX_BOOTSTRAP_PROMPT_HUMANHAND_PRE_SLM.md](CODEX_BOOTSTRAP_PROMPT_HUMANHAND_PRE_SLM.md)
- Future writer boundary: [SLM_HANDOFF_CONTRACT.md](SLM_HANDOFF_CONTRACT.md)

## Claude To Codex Loop

1. Claude Code CLI, preferably with Deepseek-V4-pro max thinking, is the default bulk implementer.
2. Claude executes exactly one active ExecPlan, validates milestones in order, updates the ExecPlan, and writes `.agent/state/last-result.env`.
3. Claude pauses before the next ExecPlan starts.
4. Codex GPT 5.4 Extra High audits the completed ExecPlan, reviews the diff, reruns relevant validation, fixes defects, updates the same ExecPlan/state surfaces, and only then hands back for the next ExecPlan.

## RTK Quick Reference

- External repo commands:
  - `rtk sh scripts/preflight.sh`
  - `rtk sh scripts/verify.sh`
  - `rtk sh scripts/cli.sh --help`
  - `rtk git diff --name-only`
- Windows builtins:
  - `rtk proxy cmd /c type AGENTS.md`
  - `rtk proxy cmd /c dir /b`
- `COMMANDS.md` keeps the canonical repo command strings. RTK is the execution wrapper, not a replacement command contract.

## Cache-Stable Prompt Discipline

- Keep the recurring Claude prefix short, exact, and stable between runs.
- Refer back to this file, `.agent/state/last-result.env`, and the active ExecPlan instead of pasting large repo context repeatedly.
- Put volatile pause/resume state in `.agent/state/continuation.md`, then write `.agent/state/last-result.env` last.
- Reuse exact ExecPlan ids, file-read order, and prompt headings whenever possible.
- This setup is optimized for high prompt-cache reuse, but provider-side cache-hit percentages are not guaranteed by repo configuration alone.

## Serena Notes

- Serena should treat this as a Python-first repo with docs and shell support, not as a bash-only project.
- Use this file as the top-level orientation note, then read the active ExecPlan and only the linked authority docs.
- Keep Serena quiet and additive: durable notes belong in memories and repo docs, not in broad workspace churn.

## Pre-SLM Boundary

- Source and human-style documents use separate clean-room lanes.
- Immutable originals, canonical evidence, internal working state, and public artifacts
  are separate channels.
- Strict-local, private-audited, and regulated privacy modes are planned through EP-019.
- Obsidian is an optional user-triggered projection, never the authoritative project store.
- No model training, download, runtime, or detector-score optimization is in scope.

## Obsidian Notes

- Use this file as the vault landing note and durable link hub.
- Prefer durable notes like this file over editing ephemeral workspace state unless the user explicitly wants a layout change.
- Link to authority docs instead of duplicating them in multiple notes.

## Handoff Files

- Required final file: `.agent/state/last-result.env`
- Optional pause note before that final file: `.agent/state/continuation.md`
