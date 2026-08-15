# ADR-015: DeepSeek Training-Wheels Retirement Is Evidence-Based

- Date: 2026-08-13
- Status: Accepted

## Context

DeepSeek is intended to improve early quality and produce learning signals, not to become a hidden
permanent dependency. Removing it too early harms users; retaining it indefinitely undermines the
local-first objective.

## Decision

DeepSeek's recommended usage is reduced only through measured release gates, not calendar dates.

A release may recommend local-only mode when held-out evaluation demonstrates at least:

- 99.5% valid patch schema at first attempt;
- 95% hard-validator pass@1;
- 99% hard-validator pass within three candidates;
- 97% appropriate abstention;
- 75% human acceptance without edits;
- 95% human acceptance with no more than minor edits;
- under 5% DeepSeek escalation;
- under two percentage points of material quality gain from DeepSeek;
- zero accepted-path protected fact, citation, quotation, structure, stale revision, or
  unauthorized-scope errors.

Metrics must cover unseen authors, unseen documents, multiple registers, and the exact quantized
release artifact.

## Stages

1. Hybrid-quality recommended for non-sensitive difficult work.
2. Local-first default with bounded escalation.
3. Rare escalation below 5%.
4. DeepSeek removed from the recommended path.
5. Optional plugin retained for explicit use.

## Disable Equivalence

Before retirement, disabling or uninstalling the governor must preserve:

- import and style analysis;
- project/revision workflow;
- local writer;
- validators;
- training-data capture;
- export and audit;
- rollback.

## Consequences

- Cloud use declines based on user-visible quality.
- Metrics and privacy-preserving usage accounting are required.
- DeepSeek remains available without blocking the local-only destination.
