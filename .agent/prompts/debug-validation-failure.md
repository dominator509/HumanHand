# Prompt: Debug a Failing Validation Command

Read `AGENTS.md`, `COMMANDS.md`, `.agent/PLANS.md`, `.agent/EXECUTION_RULES.md`, and the active ExecPlan.

Debug the failing validation command without broad rewrites.

Required actions:

1. Capture the exact failing command.
2. Capture the exact error summary.
3. Identify whether this is the first, second, or third same-root failure.
4. Form one specific hypothesis.
5. Make the smallest targeted fix.
6. Rerun the narrowest relevant command from `COMMANDS.md`.
7. If the same-root failure occurs a second time, create or run a narrower diagnostic.
8. If the same-root failure occurs a third time, stop the current approach, record failed hypotheses in Surprises & Discoveries, choose a simpler implementation path if safe, or stop under a STOP condition.
9. Do not rewrite unrelated code.
10. Do not weaken validation.
11. Update the active ExecPlan Decision Log and Progress as appropriate.
12. Continue the ExecPlan after the validation passes.
