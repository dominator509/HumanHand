# Agent Readiness Checklist

Use before handing an ExecPlan to a coding agent.

- [ ] Exactly one active ExecPlan is named.
- [ ] ExecPlan is self-contained enough for a new agent with no prior conversation.
- [ ] ExecPlan lists exact files to read first.
- [ ] ExecPlan lists exact files to change.
- [ ] ExecPlan lists explicit non-goals.
- [ ] ExecPlan milestones are ordered.
- [ ] Every milestone has goal, files to read, files to change, exact edits, validation command, expected result, and recovery instruction.
- [ ] Commands come from `COMMANDS.md`.
- [ ] Expected command outputs are defined.
- [ ] Acceptance criteria are observable.
- [ ] STOP conditions are explicit through `AGENTS.md`.
- [ ] Recovery and bounded retry rules are present.
- [ ] Diff review is required.
- [ ] No hidden context is required.
- [ ] No vague approval gate such as “ask user if good” remains.
- [ ] Non-goals prevent feature drift.
- [ ] Anti-hallucination guidance is present.
- [ ] Final response requirements are clear.
