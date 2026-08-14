# ADR-011: Proposal-Only Model Authority

- Date: 2026-08-13
- Status: Accepted

## Context

HumanHand's strongest reliability property is that deterministic and human-approved state is
canonical. Connecting a model directly to the project store, document file, or exporter would
collapse that property. Grammar-constrained output alone is not a sufficient trust boundary.

## Decision

Every local or cloud model is an untrusted proposal source.

The local writer returns exactly one of:

- a `replace_block` EditPatch for one authorized block; or
- an explicit Abstention with a bounded reason code.

The response contains integrity anchors:

- capsule ID;
- project/document/revision/block IDs;
- base-text SHA-256;
- schema and version;
- decision;
- replacement text or abstention code.

Models have no direct access to:

- project database writes;
- filesystem writes;
- shell or tools;
- exporter;
- revision acceptance;
- validator configuration;
- secrets or key providers.

HumanHand performs strict application-side parsing even when the runtime uses JSON schema or
grammar constraints.

## Validation Order

1. Decode and schema.
2. Unknown/missing fields.
3. Integrity anchors.
4. Output size and special-token policy.
5. Authorized block scope.
6. Protected spans, numbers, dates, units, quotations, and citations.
7. Claims, modality, negation, attribution, and entities.
8. Structure.
9. Style hard invariants.
10. Privacy.
11. Human approval.

Any failure rejects the patch. A soft score never offsets a hard failure.

## Retry Policy

- One bounded local format-repair retry may occur when no semantic content has been accepted.
- Candidate generation may be used under configured limits.
- No unbounded self-correction loop is allowed.
- Failure after limits causes abstention or human escalation.

## Consequences

- The model can be replaced without changing document authority.
- Stale or malicious responses fail closed.
- Training can optimize contract adherence independently from prose quality.
- The application must maintain precise patch and revision semantics.

## Compatibility

The deterministic lexical review and manual workflow remain valid writer implementations. A
`NullWriterClient` represents the no-model mode.
