# ADR-006: Research Beacon Policy Firewall

- Date: 2026-08-12
- Status: Accepted for the Pre-SLM program

## Decision

The Research Beacon is read-only during observation and research, uses trusted-source
tiers, stores traceable evidence, and emits quarantined proposals requiring human
approval. It blocks private document upload, detector optimization, provenance
destruction, automatic merge, publish, and deployment.

## Reason

Research inputs are untrusted and external research must not become an uncontrolled
code or privacy channel.

## Consequence

Official APIs and mocked adapters are required. Live calls are explicitly gated and
receive only public, synthetic, or sanitized context.
