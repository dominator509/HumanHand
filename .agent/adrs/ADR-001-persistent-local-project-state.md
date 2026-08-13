# ADR-001: Persistent Local Project State

- Date: 2026-08-12
- Status: Accepted for the Pre-SLM program

## Decision

HumanHand may persist project state only inside a user-selected project directory
under `.humanhand/`. It must not create hidden global document history.

## Reason

Fact evidence, revisions, approvals, and style packages need durable local state while
remaining under the user's control and outside the existing compatibility cache.

## Consequence

Project layout, migrations, retention, and rollback must be explicit. Obsidian is an
optional projection and never the authoritative store.
