# ADR-008: SLM Deferred and Future Writer Contract

- Date: 2026-08-12
- Status: Accepted for the Pre-SLM program

## Decision

No local model, training stack, model runtime, or model registry is included before
the Pre-SLM release gate. Only `SLM_HANDOFF_CONTRACT.md` may describe the future
`WriterClient` interface and its validators.

## Reason

Deterministic boundaries and human review must be independently usable and testable
before probabilistic writing is introduced.

## Consequence

Any future writer is a proposal source only. It must pass canonical, fact, style,
privacy, artifact, and human-approval validators before output is accepted.
