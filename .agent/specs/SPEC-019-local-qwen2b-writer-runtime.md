# SPEC-019: Local Qwen3.5-2B Writer Runtime

## Purpose

Integrate an untuned local Qwen3.5-2B model behind `WriterClient` while preserving the proposal-only
authority boundary, strict-local privacy, runtime isolation, no-model fallback, and exact artifact
identity.

## Selected Model

- Integration checkpoint: `Qwen/Qwen3.5-2B`.
- Future training base: `Qwen/Qwen3.5-2B-Base`.
- Initial deployment artifact: pinned upstream or approved GGUF for development only.
- Production release artifact is built and qualified in EP-027.
- Text-only input.
- Non-thinking direct patch output.
- No multimodal features or tools.

At implementation time, verify model availability, license, tokenizer/template, architecture
support, and official revision from primary sources. Do not rely on a moving alias.

## Components

### `WriterClient`

```python
class WriterClient(Protocol):
    def propose(self, request: WriterRequest) -> WriterResult:
        ...
```

`WriterResult` contains candidates, runtime metadata without content, and bounded diagnostics.

### `NullWriterClient`

Returns a typed model-unavailable abstention and proves deterministic/manual workflows remain
functional.

### `LlamaCppWriterClient`

- calls loopback-only runtime;
- sends exact rendered prompt/grammar;
- validates response envelope;
- extracts only candidate content;
- never writes project state.

### Runtime Supervisor

Responsibilities:

- verify binary and model manifest/hash;
- select configured local port;
- create random session credential;
- launch with loopback binding;
- disable web UI when possible;
- disable request body logs and prompt caches;
- enforce slots, context, batch, timeout, and resource limits;
- health probe;
- process-tree cleanup;
- expose capability report;
- no automatic download.

### Model Registry

Stores immutable manifests and local paths, not model bytes in the project database. Registry
operations are explicit: register, verify, list, activate, deactivate, rollback.

## Prompt Rendering

The prompt renderer:

- uses a pinned template independent from arbitrary model self-identification;
- marks source/exemplar text as untrusted data;
- requests exactly one EditPatch;
- disables thinking;
- includes no secret, path, metadata inventory, or unrelated content;
- includes bounded optional governor guidance;
- includes the exact schema contract.

Rendered prompt may be held in memory only under strict mode. It is never logged.

## Decoding Modes

### Reproducible

- candidate count one;
- greedy or lowest-variance supported decoding;
- fixed runtime/model/template;
- one slot;
- no speculative decoding unless separately qualified;
- seed recorded when supported.

### Quality

- bounded candidate count, initially up to three;
- low temperature;
- each candidate independently validated;
- deterministic ranking among hard-valid candidates.

HumanHand must accurately report best-effort reproducibility rather than claiming cross-hardware
bit identity.

## Runtime Security

- loopback-only or OS IPC;
- external bind rejected;
- no outbound network;
- no shell/tool calling;
- no project filesystem mount;
- no exporter access;
- no secret provider access;
- bounded request and response;
- startup hash validation;
- strict timeout and process cleanup.

## Special-Token Policy

Build a deny registry from the pinned tokenizer/config plus known HumanHand-forbidden wrappers.
Reject:

- chat role delimiters;
- thinking blocks;
- tool calls;
- function markup;
- FIM tokens;
- image/video placeholders;
- end-of-text/control tokens;
- model self-attribution when prohibited by output policy;
- unexplained Unicode controls.

Detection causes rejection, not silent deletion.

## Privacy and Logging

Allowed runtime metrics:

- bundle/runtime ID;
- candidate count;
- token estimates/usage when available;
- latency;
- status and error class;
- retries;
- peak resources where available.

Forbidden:

- prompts;
- responses;
- document/style text;
- raw server envelopes;
- full content hashes in modes that prohibit matching records.

## Failure and Fallback

- Runtime unavailable: typed abstention and manual/deterministic fallback.
- Model corrupt/hash mismatch: refuse launch.
- Response malformed: one format retry at most.
- Timeout/crash: cleanup and circuit breaker.
- All candidates hard-invalid: human or optional governor escalation.
- Insufficient evidence: abstention.
- Registry missing: explicit setup error, never hidden download.

## CLI Behavior

Potential commands:

```text
humanhand model register
humanhand model verify
humanhand model list
humanhand model activate
humanhand model deactivate
humanhand model health
humanhand writer propose
```

Live model commands require explicit model setup and are skipped in normal CI. Mock runtime tests
remain default.

## Configuration

Add explicit environment/config entries for:

- writer enabled;
- runtime executable;
- model registry;
- active bundle;
- host/port or IPC;
- context/token/candidate limits;
- timeouts;
- reproducibility mode;
- live-test gate.

Defaults preserve no-model behavior until configured.

## Backward Compatibility

- Existing `rewrite` remains available and is not silently rerouted.
- Integrated workflow gains a separate writer proposal stage.
- Model is optional.
- No network is required for installation or tests.
- Wheel does not bundle model weights.

## Test Requirements

- mocked runtime success/failure;
- binary/model hash verification;
- external bind rejection;
- no-download behavior;
- special-token leakage;
- reasoning/tool wrapper rejection;
- malformed envelope and JSON;
- timeout/process cleanup;
- no-model fallback;
- privacy logs;
- candidate validation/ranking;
- Windows runtime supervisor tests;
- gated local smoke test on actual model;
- A2000 resource benchmark report.

## Acceptance Criteria

- Untuned Qwen3.5-2B can produce valid bounded patches through WriterClient.
- Every accepted candidate passes strict application validation.
- No model process can mutate HumanHand state.
- Strict-local and no-model modes remain functional.
- Runtime and model identity are pinned and inspectable.
- Mocked CI and gated live smoke tests pass.
