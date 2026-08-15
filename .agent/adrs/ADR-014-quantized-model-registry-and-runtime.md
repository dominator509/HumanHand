# ADR-014: Quantized Model Registry and Runtime Bundle

- Date: 2026-08-13
- Status: Accepted

## Context

A model checkpoint that passes evaluation before conversion may regress after adapter merge,
GGUF conversion, quantization, or runtime changes. A filename is not sufficient identity.
HumanHand needs reproducible, reversible model deployment without hidden downloads.

## Decision

HumanHand deploys an immutable model bundle registered by manifest.

The initial target is Q4_K_M GGUF. The bundle includes:

- exact upstream model revision;
- universal adapter hash;
- merged full-precision model hash;
- GGUF hash and quantization;
- tokenizer and chat-template hashes;
- grammar/schema version;
- runtime binary/build identity and launch policy;
- dataset and experiment manifests;
- license and distribution restrictions;
- qualification results and supported hardware;
- rollback predecessor.

The universal adapter is merged before quantization. Quantization is performed from the
full-precision merged model, never from an already quantized artifact.

## Runtime

- Runtime binds to loopback only.
- No automatic model download occurs in strict-local mode.
- Startup verifies hashes and compatibility.
- Prompt/response logging and prompt caches are disabled by policy.
- Model process has no project filesystem or exporter access.
- Model absence or failure falls back to deterministic/manual HumanHand.

## Promotion

A bundle is promoted only after the exact quantized artifact passes `MODEL_RELEASE_GATES.md`.
Promotion changes a local registry pointer; it does not delete the previous champion.

## Consequences

- Release qualification is slower but trustworthy.
- Runtime upgrades require requalification.
- Rollback is fast.
- Distribution and licensing remain explicit.
