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
- Expected changed files match actual changed files and untracked additions, or extra files are justified.
- Remaining risks documented.
- `.agent/state/last-result.env` written.
- Final response includes required status report.
