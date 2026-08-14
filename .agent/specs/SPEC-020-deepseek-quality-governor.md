# SPEC-020: Optional DeepSeek Quality Governor

## Purpose

Add an optional cloud quality layer that improves early planning, soft critique, and failure
diagnosis without directly authoring accepted document prose or becoming required for HumanHand.

## Provider

At implementation time, verify official current DeepSeek API documentation and model IDs. The
planned IDs as of this architecture decision are:

- `deepseek-v4-flash` for routine low-cost planning and critique;
- `deepseek-v4-pro` for explicit hard-case diagnosis/planning escalation.

Use only official APIs and HTTPS. Exact model ID is pinned in every report.

## Interfaces

```python
class QualityGovernorClient(Protocol):
    def plan(self, request: PlanningRequest) -> PlanningReport: ...
    def critique(self, request: CritiqueRequest) -> CritiqueReport: ...
    def diagnose(self, request: DiagnosisRequest) -> DiagnosisReport: ...
```

`NullQualityGovernor` is mandatory.

### `GovernorGuidance`

A bounded internal object derived from a valid report. It may include:

- required block functions;
- claim IDs;
- style priorities;
- risk flags;
- local revision instructions;
- maximum revision scope;
- human-review recommendation.

It cannot include final replacement prose or altered protected values.

## Cloud Packet

Every request passes:

1. data classification;
2. project cloud consent;
3. packet-level policy;
4. local sanitizer;
5. placeholder lock;
6. budget estimate;
7. provider/model allowlist;
8. circuit breaker.

Packet levels are NONE, ABSTRACT, SANITIZED_BLOCK, and APPROVED_CONTEXT as defined in
`DEEPSEEK_GOVERNOR_POLICY.md`.

## Planning

Planning occurs before local generation only when route policy permits. It returns rhetorical and
constraint guidance. It cannot return a final paragraph.

## Critique

Critique receives only a locally generated candidate that already passed every hard validator. It
evaluates soft concerns and returns issue codes and bounded instructions. The local writer performs
the revision. Critique cannot turn a hard-invalid candidate into a valid one.

## Diagnosis

Diagnosis occurs after bounded local failures. It returns an allowlisted action:

- improve context;
- change exemplar selection;
- retry once;
- abstain;
- route to human;
- open engineering investigation.

It cannot change validator settings or rewrite the document.

## Router

Routing inputs may include:

- privacy mode;
- user mode;
- style-profile coverage;
- exemplar sufficiency;
- local hard-valid count;
- local style distance;
- continuity risk;
- local abstention reasons;
- provider availability;
- remaining budgets.

Router output is deterministic and explainable. It records reason codes.

## Cost Controls

Enforce:

- call count per operation/block;
- tokens per request/response;
- cost per request/document/month;
- timeout;
- one retry;
- consecutive failure circuit breaker;
- user-configured hard ceiling.

A budget denial is a normal local/human fallback, not an error that risks data loss.

## Response Validation

- strict JSON schema;
- `additionalProperties: false`;
- exact request/candidate IDs;
- model ID;
- bounded strings/lists;
- no tools or arbitrary content;
- placeholder consistency;
- one bounded retry for empty/malformed JSON;
- no raw response logging.

## Privacy

- DeepSeek disabled in strict-local.
- Cloud mode disclosed.
- Full manuscripts and complete style vaults blocked by default.
- Protected values placeholder-locked.
- PHI/regulated data blocked absent separate approved policy.
- API key from secret provider.
- Request/response content not logged.
- encrypted private receipt optional.
- public artifact contains no governor metadata.

## Gold Data

Governor reports may become teacher artifacts only when consent and policy permit. They are labeled
and cannot become positive targets automatically.

## CLI Behavior

Potential commands:

```text
humanhand governor status
humanhand governor disclose
humanhand governor test --mock
humanhand governor budget
humanhand writer propose --mode local-first|hybrid-quality
```

No live call occurs without explicit configuration and live gate.

## Backward Compatibility

- DeepSeek package/credentials are optional.
- Disabling provider produces identical core capabilities.
- Existing LLM rewrite endpoint is separate and not silently reused.
- No provider call in normal CI.

## Tests

- Null governor equivalence.
- sanitizer/placeholder properties;
- packet classification;
- consent and strict-local denial;
- budget and circuit breaker;
- exact model pinning;
- schema/unknown-field rejection;
- empty response and retry;
- malformed placeholder references;
- no final prose field;
- router reason codes;
- mocked Flash/Pro escalation;
- no raw content logs;
- live tests gated;
- disable/uninstall path.

## Acceptance Criteria

- Optional governor improves the path without gaining writer authority.
- Every cloud transmission is disclosed, minimized, sanitized, budgeted, and policy-approved.
- Strict-local makes a network call impossible.
- Null governor and provider outage preserve local workflow.
- Governor reports cannot bypass hard validators or human approval.
