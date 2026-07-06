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
