---
id: EP-XXX
title: <Title>
status: not_started
owner: agent
created: YYYY-MM-DD
updated: YYYY-MM-DD
---

# EP-XXX: <Title>

## Purpose / Big Picture

State the implementation goal and why it matters. A new agent with no prior conversation must understand the work from this file alone.

## Scope

- In-scope item.

## Non-goals

- Out-of-scope item.

## Context and Orientation

Describe relevant repository state, prior plans, constraints, and assumptions.

## Files to Read First

- `AGENTS.md`
- `COMMANDS.md`
- `.agent/PLANS.md`
- Relevant files.

## Files to Change

Expected files:

- `path/to/file`
- `.agent/execplans/EP-XXX-title.md`
- `.agent/state/last-result.env`

## Interfaces and Contracts

Define functions, commands, files, env vars, schemas, or user-visible behavior that must exist after this plan.

## Milestones

### M1 — <Milestone Name>

- Goal: <goal>
- Files to read: <files>
- Files to change: <files>
- Exact edits expected: <edits>
- Validation command: `<command from COMMANDS.md>`
- Expected result: `<expected output>`
- Recovery: <bounded recovery instruction>

## Concrete Steps

1. Run `sh scripts/preflight.sh`.
2. Complete milestones in order.
3. Validate after each milestone.
4. Update this ExecPlan.
5. Run diff review.
6. Write `.agent/state/last-result.env` last.

## Validation and Acceptance

- Acceptance criterion.

## Idempotence and Recovery

Explain how to rerun safely and how to recover from partial completion.

## Progress

- [ ] M1 — <Milestone Name>.

## Surprises & Discoveries

- None yet.

## Decision Log

- YYYY-MM-DD: <decision>. Reason: <reason>. Consequence: <consequence>.

## Outcomes & Retrospective

Not started.
