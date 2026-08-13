# SPEC-017: Pre-SLM Production Readiness

## Purpose

Define the release gate for the deterministic Pre-SLM workflow and distinguish local
proof from maintainer-owned or externally gated decisions.

## Data Contracts

`PreSlmReadinessReport` contains schema/version, plan statuses, validation results,
coverage, privacy mode checks, artifact audit results, compatibility results, blocked
gates, remaining risks, and release recommendation.

## Invariants

Readiness is local-only unless an explicitly gated live check is run. Green text cannot
hide a failed underlying command. No license, publish, tag, deployment, or live account
decision is invented.

## Inputs and Outputs

Inputs are all plan artifacts, scripts, tests, built wheels, audit reports, and explicit
operator decisions. Outputs are a report, changelog/release notes, rollback evidence,
and a final state handoff.

## Privacy Rules

Readiness artifacts contain no user documents, raw model/detector responses, secrets,
or external research payloads.

## Failure Behavior

Missing tools, unavailable Docker/keys/endpoints, unresolved human approvals, failed
audits, or incomplete coverage remain explicit blockers or risks.

## CLI Behavior

Update the documented validation scripts and production-readiness/loop gates only in
EP-019 after all pre-SLM surfaces exist.

## JSON Result Schema

The report has stable gate ids, status, evidence references, and a `production_ready`
boolean that cannot be true while a required gate is blocked.

## Backward Compatibility

The existing EP-010 local package-readiness contract remains visible; the Pre-SLM gate
is additive and does not imply PyPI publication.

## Test Requirements

Test every gate, fail-closed wrappers, wheel install on supported CI platforms, rollback
instructions, forbidden SLM paths, privacy scans, dependency scans, and compatibility.

## Explicit Non-goals

Publishing, hosted deployment, release tagging, legal license selection, and SLM launch.

## Acceptance Criteria

EP-019 reports honest local readiness, all required gates have evidence, remaining risks
are explicit, and no forbidden model/training files exist.
