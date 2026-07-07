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

Before final response, run `git diff --name-only` and `git status --short --branch`, compare tracked and untracked changes with Files to Change, and justify extra changed files in the Decision Log.

## Final Response Rule

Final response must report ExecPlan id/status, milestones, changed files, commands/results, acceptance status, decisions, assumptions, risks, production-readiness status when applicable, and confirmation that `.agent/state/last-result.env` was written.
