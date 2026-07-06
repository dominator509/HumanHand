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
