# SPEC-009: Pre-SLM Program Scope

## Purpose

Define the deterministic and privacy-preserving capabilities required before any
specialized local writing SLM is introduced.

## Data Contracts

- `PreSlmProgramManifest`: program id, current plan, plan sequence, non-goals, and
  acceptance status.
- `ProgramFinding`: stable code, severity, affected boundary, evidence, and review
  status.
- `ProgramStatus`: `planned`, `active`, `complete`, `blocked`, or `human_review_required`.

## Invariants

- EP-011 through EP-019 execute in order, one active plan at a time.
- No SLM implementation, training artifact, model download, or semantic repair exists.
- Existing public commands remain available throughout the migration.
- Unknown or unsupported behavior is reported rather than silently accepted.

## Inputs and Outputs

Inputs are repository control documents, user-selected local files, explicit project
policies, and synthetic/public research fixtures. Outputs are versioned specs, reports,
approved local state, and public artifacts with no internal metadata.

## Privacy Rules

Private documents remain local unless the user explicitly configures a permitted
external operation. Logs, fixtures, caches, and research requests contain no user text.

## Failure Behavior

Contradictions, missing evidence, unsupported formats, and unavailable live services
produce a documented finding or STOP condition. They do not produce a fake-green gate.

## CLI Behavior

The existing `health`, `rewrite`, `verify`, `diff-facts`, and `scrub` commands remain
stable. New command families become available only in the plan that implements them.

## JSON Result Schema

Machine results use a versioned object with `schema_version`, `status`, `code`,
`summary`, `findings`, and `artifact_refs`. User text is excluded by default.

## Backward Compatibility

Existing result types and `StyleFingerprint` remain compatibility facades until a
documented major-version change.

## Test Requirements

Test plan ordering, non-goal enforcement, no-SLM file policy, stable JSON shape, and
legacy command availability without live network access.

## Explicit Non-goals

SLM training/runtime, detector optimization, automatic publication, hosted services,
and hidden global history.

## Acceptance Criteria

All plan files exist and are self-contained; EP-011 is active; the blueprint and
bootstrap prompt are present; no forbidden SLM paths are created; and all later work
has a named plan and validation boundary.
