# SPEC-025: Quantized Runtime, Model Registry, and Release Qualification

## Purpose

Convert the selected universal adapter to an immutable local Q4_K_M GGUF bundle, integrate it with
the isolated runtime, and qualify the exact release artifact on supported hardware.

## Build Pipeline

1. Verify upstream base and adapter hashes.
2. Merge universal adapter into full-precision base.
3. Verify merged model behavior.
4. Convert merged model to GGUF.
5. Build importance matrix when required and documented.
6. Quantize from full precision to Q4_K_M.
7. Verify GGUF metadata and tokenizer/template.
8. Run exact-artifact evaluation.
9. Build signed ModelBundleManifest.
10. Stage for human promotion.

No re-quantization of a quantized artifact.

## Registry

Operations:

- register;
- verify;
- list;
- stage;
- activate;
- rollback;
- quarantine;
- remove only with explicit maintainer action.

Registry entries are immutable. Active pointer changes atomically.

## Runtime Manifest

Includes supported command line, loopback policy, context/candidate limits, GPU layer settings,
runtime version, expected capabilities, and privacy flags.

## Qualification

Run every gate in `MODEL_RELEASE_GATES.md` on:

- merged full precision;
- unquantized GGUF;
- Q4_K_M GGUF;
- Windows RTX A2000 configuration;
- CPU fallback;
- local-only and optional hybrid paths.

## Distribution

No model weights in normal source wheel. Distribution location, license, and access are explicit.
No automatic download in strict-local.

## Rollback

Keep prior champion and deterministic/manual mode. Test process:

- stop writer;
- atomically change active bundle;
- start/verify prior champion;
- resume workflow with no project migration.

## Tests

- manifest/hash tamper;
- incompatible schema/runtime;
- activation/rollback atomicity;
- missing model;
- startup health;
- Q4_K_M behavior;
- Windows A2000 resource benchmark;
- CPU fallback;
- no automatic download;
- no logs/tool/filesystem access;
- quantization delta;
- exact artifact release-controller report.

## Acceptance Criteria

- Exact Q4_K_M bundle passes all zero-tolerance gates.
- Performance fits documented target.
- Registry activation and rollback are safe.
- Bundle identity and license are complete.
- Deterministic/manual and no-governor fallbacks remain green.
