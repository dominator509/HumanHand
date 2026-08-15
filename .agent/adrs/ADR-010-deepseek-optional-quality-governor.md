# ADR-010: DeepSeek as an Optional Quality Governor

- Date: 2026-08-13
- Status: Accepted

## Context

An untuned or early-stage 2B writer may be weak at long-range planning, subtle rhetoric, failure
diagnosis, and soft quality review. Calling a frontier API for every final paragraph would undermine
HumanHand's local-first goal and could imprint generic cloud-model prose. A narrower supervisory
role can improve early quality at low cost while generating learning signals for the local model.

## Decision

DeepSeek is an optional `QualityGovernorClient`, not a writer.

Permitted runtime operations:

- `plan`: return structured rhetorical goals, required functions, style priorities, and risk flags;
- `critique`: return structured soft-quality issues for a hard-valid local candidate;
- `diagnose`: classify repeated local failures and recommend context, abstention, or human
  escalation.

Permitted Forge operation:

- `teach`: assist synthetic degradation, hard-negative, red-team, critique-label, and failure-cluster
  generation using approved or synthetic material.

DeepSeek may not:

- return prose that is directly accepted into the document;
- write project state or files;
- call arbitrary tools;
- alter validator policy;
- receive data beyond the active cloud-packet policy;
- become required for core HumanHand functionality;
- participate in unbounded recursive rewrite loops.

Flash is the default cost-efficient governor; Pro is an explicitly routed escalation. Exact API
model IDs must be discovered from official current documentation and pinned per run.

## Privacy Decision

DeepSeek use changes a project from strict-local to cloud-assisted. HumanHand must:

- require project-level opt-in;
- show the packet level and data categories before first use;
- block cloud calls under strict-local mode;
- pseudonymize and placeholder-lock protected values locally;
- never send the complete Style Fidelity Vault or full manuscript automatically;
- retain no raw request/response logs;
- store credentials only through approved secret providers;
- prohibit regulated data unless a separate approved policy permits it.

## Cost and Loop Bounds

Default maximum per block:

- one planning call;
- one critique call;
- one diagnosis call;
- no more than two cloud round trips in the normal local-first path.

Budgets are enforced per request, block, document, and billing period.

## Consequences

- Early output quality and diagnostics can improve without requiring larger local hardware.
- DeepSeek interventions become high-value training records.
- Cloud privacy and provider availability become explicit operational concerns.
- HumanHand must maintain a full NullQualityGovernor path and disable equivalence tests.

## Exit

ADR-015 defines the evidence-based retirement gate. Removing DeepSeek from the recommended path
does not remove the optional plugin.
