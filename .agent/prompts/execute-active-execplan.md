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
