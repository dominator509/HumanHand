---
id: EP-018
title: Research Beacon and Scanner Observatory
status: complete
owner: claude
created: 2026-08-12
updated: 2026-08-13
---

# EP-018: Research Beacon and Scanner Observatory

## Purpose / Big Picture

Create a read-only, evidence-backed research and scanner observatory with a policy
firewall and human-approved quarantined proposals.

## Scope

Evidence/source tiers, snapshots, triggers, watchers, mocked xAI-compatible research
port, structured reports, proposals, policy decisions, synthetic control corpus, and
gated scanner runs.

## Non-goals

Private-document upload, invented OAuth, detector optimization, watermark-key recovery,
provenance destruction, automatic code changes, merge, publish, or deploy.

## Context and Orientation

Follow SPEC-015, ADR-006, privacy modes from EP-016, and the research sections of the
blueprint.

## Files to Read First

Authority stack, SPEC-015, ADR-006, security/privacy/network policy, provider ports,
fixtures, and dependency docs.

## Files to Change

Beacon/scanner domain/application/infra/CLI modules, policies/schemas/watchers, synthetic
fixtures, tests, docs, scripts, and this plan.

## Interfaces and Contracts

External research receives only public/synthetic/sanitized context; official documented
APIs only; live calls require explicit gates; proposals cannot bypass policy approval.

## Milestones

### M1 - Evidence and policy firewall

Goal: add source tiers, findings, blocked actions, and proposal contracts. Validation:
`sh scripts/test-unit.sh`. Expected: unit tests pass. Recovery: quarantine unclear claims.

### M2 - Mocked provider and watchers

Goal: add mocked research client and read-only watchers. Validation: `sh scripts/test-integration.sh`.
Expected: integration tests pass. Recovery: disable undocumented provider behavior.

### M3 - CLI and synthetic observatory

Goal: expose Beacon/scanner commands and control corpus. Validation: `sh scripts/test-e2e.sh`.
Expected: E2E tests pass. Recovery: keep live paths skipped by default.

### M4 - Boundary

Goal: full validation and handoff. Validation: `sh scripts/verify.sh`. Expected:
`verify: ok`. Recovery: bounded retry and documented external blocker.

## Concrete Steps

Implement M1-M4 in order, require evidence for decisions, and write state last.

## Validation and Acceptance

Default tests are offline; public/synthetic payloads are sanitized; source evidence is
traceable; blocked actions cannot be approved through ordinary paths.

## Idempotence and Recovery

Snapshots and proposals are append-only/versioned where configured. Never auto-merge or
modify production files from a research result.

## Progress

- [x] M1
- [x] M2
- [x] M3
- [x] M4

## Surprises & Discoveries

- Beacon CLI module names and store methods did not match the implemented flat
  domain modules, causing the real lifecycle tests to skip rather than run.
- Policy resources lacked strict schema/provenance validation, proposal
  evidence was not required for non-high-impact work, and source-tier strings
  disagreed with the domain enum.
- ZDR compliance was inferred from a model-name substring, which was not valid
  evidence of endpoint policy.

## Decision Log

- Wire the CLI to the actual deterministic trigger, snapshot, source registry,
  and schema-valid proposal-store contracts; keep incomplete installs fail closed.
- Re-run bundled policy review at approval time, preserve append-only decisions,
  and refuse blocked, unknown, malformed, or unreviewed payloads.
- Require exact policy schemas and curated provenance, all mandatory blocked
  actions, evidence for every proposal, and serialized enum-compatible tiers.
- Require an explicit operator-supplied set of ZDR-compliant models; provider
  results require nonempty findings, HTTPS evidence URLs, and confidence in [0,1].
- Update the program tracker after validation to remove its duplicate EP-016 row
  and identify EP-019 as the next, not-yet-started seam.

## Outcomes & Retrospective

Complete. Offline snapshots are traceable to investigations, source reporting
uses the registered public evidence set, policy approval is re-evaluated through
the firewall, scanner runs remain synthetic/offline by default, and live research
remains explicitly gated. The importer bundle passes 280 tests with 4 conditional
skips; full verification passes 1948 tests with 15 skips, 86.35% coverage, and
`verify: ok`.
