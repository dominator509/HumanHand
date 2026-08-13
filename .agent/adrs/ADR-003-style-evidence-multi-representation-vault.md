# ADR-003: Multi-Representation Style Evidence Vault

- Date: 2026-08-12
- Status: Accepted for the Pre-SLM program

## Decision

The Style Fidelity Vault stores an immutable original artifact, an exact surface view,
an analytical profile, authorship decisions, approved exemplars, invariants, and a
coverage report as separate representations.

## Reason

Style fidelity depends on preserving every supported visible and formatting signal,
not reducing a sample to one mutable string or shallow fingerprint.

## Consequence

No scrubber or normalizer may rewrite immutable evidence. A `complete` designation
requires complete supported coverage and resolved authorship spans.
