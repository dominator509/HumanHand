# DeepSeek Optional Quality Governor Policy

## Purpose

Define the exact privacy, authority, cost, routing, and output restrictions for optional DeepSeek
use. This policy is normative for EP-022 onward.

## Authority Boundary

DeepSeek is not a writer of accepted document content. It may return only a planning report,
critique report, diagnosis report, or Forge teacher artifact. A report is advisory and cannot be
applied as a document patch.

## Modes

| HumanHand mode | DeepSeek behavior |
|---|---|
| strict-local | adapter is NullQualityGovernor; calls are impossible |
| local-first | call only after objective local escalation |
| hybrid-quality | bounded plan and critique permitted |
| forge-teacher | approved/synthetic training material only |

Mode changes require explicit project-level action. A command must show that cloud transmission is
enabled before the first call.

## Operations and Schemas

### PlanningReport

Required fields:

- schema/version;
- request/capsule IDs;
- exact model ID;
- required block functions;
- required claim IDs;
- style priorities;
- risk flags;
- unresolved questions;
- recommendation: generate, abstain, or human-review.

Forbidden fields:

- replacement prose;
- full rewritten paragraph;
- tool calls;
- secrets;
- project paths;
- arbitrary instructions.

### CritiqueReport

Required fields:

- candidate digest;
- verdict: accept-soft-quality, revise, or human-review;
- bounded issue list;
- evidence spans within the candidate;
- local revision instructions;
- maximum revision scope;
- locked claim/protected identifiers.

A critique can never override a hard validator.

### DiagnosisReport

Required fields:

- failure-cluster code;
- evidence references;
- likely category;
- recommended action from an allowlist;
- confidence and limitations.

Allowed actions: add context, improve exemplar selection, retry locally once, abstain, route to
human, open an engineering investigation.

Forbidden action: weaken or disable a validator.

## Cloud Packet Policy

### NONE

No serialization, network, or provider call.

### ABSTRACT

May contain:

- style metric ranges;
- invariant/tendency codes;
- section and block purposes;
- document structure summary;
- pseudonymized claim propositions;
- validator codes;
- placeholder map IDs without local values.

### SANITIZED_BLOCK

May add:

- one redacted block;
- bounded adjacent redacted context;
- sanitized approved exemplars;
- non-sensitive continuity summary.

### APPROVED_CONTEXT

May add explicitly approved real content. It requires a per-project consent record and a visible
preflight summary. It still excludes complete vaults, raw files, metadata inventories, credentials,
project paths, unrelated sections, and private receipts.

## Local Sanitization

Before transmission:

1. Classify every field.
2. Replace protected values with typed placeholders.
3. Remove direct identifiers not required for quality review.
4. Minimize adjacent context.
5. exclude raw metadata and comments.
6. calculate packet digest and estimated token/cost.
7. enforce policy, consent, and budget.
8. show disclosure when required.

A response cannot introduce or modify placeholder values. Plans and critiques refer to placeholder
IDs only.

## Credentials

- Official DeepSeek API only.
- API key from approved secret provider.
- No key in config files, logs, errors, or receipts.
- Endpoint must use HTTPS.
- Exact current model IDs must be verified from official docs and pinned.
- Do not invent OAuth.
- Provider response headers and billing metadata may be stored without content when policy permits.

## Budgets and Circuit Breakers

Default bounds:

```toml
max_planner_calls_per_block = 1
max_critic_calls_per_block = 1
max_diagnostic_calls_per_block = 1
max_cloud_round_trips_per_block = 2
request_timeout_seconds = 60
retry_count = 1
```

Enforce:

- max input/output tokens;
- max request cost;
- max document cost;
- monthly budget;
- consecutive failure circuit breaker;
- provider outage backoff;
- explicit user override within configured maximum.

A budget or provider failure falls back to local/human flow.

## Retention and Observability

Never log request or response content. Permitted aggregate fields:

- operation;
- model ID;
- packet level;
- token counts;
- estimated/actual cost;
- latency;
- result class;
- retry count;
- sanitizer finding count;
- local/hybrid quality outcome.

Private receipts may store encrypted structured reports when the user opted in. Public artifacts
never include cloud-assistance records.

## Training Use

DeepSeek material may be retained for Forge only when:

- the source record is training-eligible;
- the user consent covers teacher processing;
- the report is schema-valid;
- data classification allows the provider;
- the artifact is labeled teacher-generated.

DeepSeek prose is not automatically a positive target. Gold targets remain human-authored or
human-approved.

## Disable Equivalence

Tests must prove that with DeepSeek disabled:

- import, style, project, context, local writer, review, export, audit, gold capture, and rollback
  work;
- no hidden API call occurs;
- CLI/UI states remain clear;
- results fail over to local or human review without data loss.

## Blocked Uses

- detector-score rewrite loops;
- watermark-key research or removal;
- silent provenance stripping;
- direct final-document generation;
- private full-document upload;
- PHI/regulated data without separately approved policy;
- validator modification;
- autonomous acceptance;
- unbounded recursive planning or criticism.
