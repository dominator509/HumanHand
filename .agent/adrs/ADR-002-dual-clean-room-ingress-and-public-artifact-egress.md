# ADR-002: Dual Clean-Room Ingress and Public Artifact Egress

- Date: 2026-08-12
- Status: Accepted for the Pre-SLM program

## Decision

AI/source documents and human style samples use separate import lanes, data types,
policies, and stores. Public output is built only through a `PublicDocument` boundary.

## Reason

Source facts must not become style evidence, style-sample facts must not become project
facts, and internal workflow metadata must not leak into public artifacts.

## Consequence

Every importer and exporter reports unsupported features and has a clean-room audit;
raw containers never reach a writer or public exporter.
