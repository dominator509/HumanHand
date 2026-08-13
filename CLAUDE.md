@REPO_BRIEF.md
@AGENTS.md
@COMMANDS.md
@.agent/PLANS.md
@.agent/EXECUTION_RULES.md

# CLAUDE.md - Human Hand Claude Main / Codex Audit Loop

Use this file when Claude Code CLI is the primary bulk coder for Human Hand.

## Priority

If this file conflicts with repository control-plane docs, use this order:

1. Current explicit user instruction.
2. `AGENTS.md`.
3. `COMMANDS.md`.
4. `.agent/PLANS.md` and `.agent/EXECUTION_RULES.md`.
5. The active ExecPlan.
6. Existing repository code and tests.
7. `ARCHITECTURE.md`.
8. Relevant `.agent/specs/`.
9. `ROADMAP.md`.
10. This file.

Do not implement directly from `ROADMAP.md`.

## Preferred Runtime

- Preferred surface: Claude Code CLI running inside the Codex terminal.
- Preferred model: Deepseek-V4-pro max thinking if the local Claude Code setup exposes it.
- Fallback: the strongest available reasoning/coding model. Record any model mismatch in the active ExecPlan Decision Log.
- Do not stop solely because the preferred model is unavailable.

## Default Collaboration Loop

1. Claude owns bulk implementation for exactly one active ExecPlan at a time.
2. Claude reads `REPO_BRIEF.md`, `AGENTS.md`, `COMMANDS.md`, `.agent/PLANS.md`, `.agent/EXECUTION_RULES.md`, the active ExecPlan, and the ExecPlan's Files to Read First.
3. Claude runs preflight and completes milestones in order, validating after each milestone.
4. At ExecPlan completion, Claude updates the ExecPlan, optionally refreshes `.agent/state/continuation.md`, writes `.agent/state/last-result.env` as the final file operation, and then pauses.
5. Codex GPT 5.4 Extra High audits the completed ExecPlan, reviews the diff, reruns relevant validation, fixes defects, updates the same plan/state surfaces, and only then hands back for the next ExecPlan.
6. Do not auto-advance to the next ExecPlan until the Codex audit/fix pass is complete unless the current user instruction explicitly overrides this loop.

## Full-Build-Loop With Audit Pauses

When the user requests a full build loop, execute ExecPlans in order starting from the first incomplete plan, but still treat every ExecPlan boundary as a required Codex audit/fix pause rather than auto-advancing blindly.

## RTK Wrapper Rule

- `COMMANDS.md` remains the canonical repo command list.
- On this Windows machine, execute external commands through `rtk`.
- Examples:
  - `rtk sh scripts/preflight.sh`
  - `rtk sh scripts/verify.sh`
  - `rtk sh scripts/cli.sh --help`
  - `rtk git diff --name-only`
- For Windows builtins, use `rtk proxy cmd /c ...`.
- Examples:
  - `rtk proxy cmd /c type AGENTS.md`
  - `rtk proxy cmd /c dir /b`
- RTK is an execution wrapper, not a replacement command contract. When documenting validation, record the canonical repo command from `COMMANDS.md`.

## Cache-Stable Prompt Discipline

- Keep the recurring Claude prefix short, exact, and stable between runs.
- Do not paste large repo docs into every prompt; point back to `REPO_BRIEF.md`, `.agent/state/last-result.env`, and the active ExecPlan.
- Put volatile run status in `.agent/state/continuation.md` rather than editing the stable prefix.
- Reuse exact section headings, file-read order, and ExecPlan ids between turns.
- Keep large terminal output out of the stable prefix unless the failure itself is the task.
- These rules optimize for high prompt-cache reuse, but provider-side cache-hit percentages are not guaranteed from repo configuration alone.

## First-Turn Checklist

1. Confirm repository files are present. If only the blueprint zip is present, extract it before repo rules apply.
2. Read the authority files in the repo order.
3. If `.agent/programs/PRE-SLM-HARDENING-PROGRAM.md` exists, select the lowest-numbered
   incomplete plan from EP-011 through EP-019; otherwise activate the current plan.
   Read that plan's Files to Read First.
4. Run `rtk sh scripts/preflight.sh`.
5. Execute only one ExecPlan in this session, unless the current user instruction explicitly changes the loop.

## Output And Handoff Requirements

- Update the active ExecPlan Progress, Surprises & Discoveries, Decision Log, and Outcomes & Retrospective as work proceeds.
- Review `git diff --name-only` against the ExecPlan Files to Change and justify extras in the Decision Log.
- The final file operation of the session must be writing `.agent/state/last-result.env`.
- If pausing at an ExecPlan boundary, create or refresh `.agent/state/continuation.md` before writing `.agent/state/last-result.env`.
- Final report must include ExecPlan id/status, milestones completed, files changed, commands run/results, acceptance status, decisions, assumptions, remaining risks, production-readiness status where applicable, and confirmation that `.agent/state/last-result.env` was written.

## Ready-To-Paste Stable Claude Prefix

```text
Use Deepseek-V4-pro max thinking if available.

Read REPO_BRIEF.md, AGENTS.md, COMMANDS.md, .agent/PLANS.md, .agent/EXECUTION_RULES.md, .agent/state/last-result.env if present, and the first incomplete ExecPlan.

Use RTK for external commands and `rtk proxy cmd /c` for Windows builtins.

Execute exactly one ExecPlan, validate every milestone, update the active ExecPlan, write `.agent/state/last-result.env` as the final file operation, and then pause for the Codex audit/fix pass before the next ExecPlan.
```

For the Pre-SLM program, read the supplied blueprint and bootstrap prompt only when
EP-011 requires them; do not paste either large document into recurring prompts. Do not
create any SLM, training, model, or semantic-repair implementation path.

## Ready-To-Paste Codex Audit Prompt

```text
Audit the most recently completed Human Hand ExecPlan before Claude starts the next one.

Read REPO_BRIEF.md, AGENTS.md, COMMANDS.md, .agent/PLANS.md, .agent/EXECUTION_RULES.md, .agent/state/last-result.env, .agent/state/continuation.md if present, and the just-completed ExecPlan.

Review the diff, rerun the relevant validation, fix any coding or workflow issues, update the ExecPlan and state files, and only then mark the repository ready to hand back to Claude for the next ExecPlan.
```

## Continuation Prompt

```text
Continue the current Human Hand ExecPlan from the repository state on disk.

Read REPO_BRIEF.md, AGENTS.md, COMMANDS.md, .agent/PLANS.md, .agent/EXECUTION_RULES.md, .agent/state/last-result.env, .agent/state/continuation.md if present, and the first incomplete ExecPlan.

Resume at the first incomplete milestone. Keep the stable prompt prefix unchanged if possible. Use RTK for external commands, validate each milestone, update the active ExecPlan, and write `.agent/state/last-result.env` as the final file operation before the next audit pause.
```
