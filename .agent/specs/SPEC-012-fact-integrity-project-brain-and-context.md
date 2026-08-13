# SPEC-012: Fact Integrity, Project Brain, and Context

## Purpose

Provide protected facts, evidence, local project state, revisions, and deterministic
context capsules without a model.

## Data Contracts

Contracts include `ProtectedSpan`, `ClaimV2`, `SourceEvidence`, `Entity`, `Relationship`,
`StructureSignature`, `DocumentRevision`, `ProjectState`, and `ContextCapsule`.

## Invariants

Names, quantities, units, dates, citations, quotations, URLs, code, modality, and
negation are protected. Missing anchors mean `unknown_coverage`, not perfect coverage.
Stale revisions cannot overwrite accepted state.

## Inputs and Outputs

Inputs are approved source packages, style constraints, user decisions, and selected
project directories. Outputs are local project state, migrations, revision reports,
and deterministic inspectable context capsules.

## Privacy Rules

Project state lives only under the user-selected `.humanhand/` directory. Sensitive
fields use configured application-layer encryption. No hidden global history exists.

## Failure Behavior

Contradictions, stale revisions, unknown coverage, invalid migrations, and malformed
capsules fail closed with typed findings and no silent overwrite.

## CLI Behavior

Implement `project init`, `status`, `ingest`, `revisions`, `export-obsidian`, plus
`context preview` and `context validate`.

## JSON Result Schema

Results contain schema/revision versions, stable private references, coverage status,
findings, and approval state. Public projections omit internal ids by default.

## Backward Compatibility

Existing fact-diff and result types remain available as compatibility facades. The
current rewrite path can operate without a project directory until migration is
explicitly enabled.

## Test Requirements

Test protected-span preservation, claims and evidence, migrations, stale revisions,
deterministic capsules, no-text leakage, rollback, and Obsidian projection isolation.

## Explicit Non-goals

Semantic embeddings, hidden cloud sync, model context injection, and automatic
Obsidian synchronization.

## Acceptance Criteria

Project state is user-selected and migratable, stale writes are rejected, unknown
coverage is explicit, and equal inputs produce equal schema-valid capsules.
