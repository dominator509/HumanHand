# HumanHand Model Release Gates

## Purpose

Define the non-negotiable qualification requirements for a local writer model bundle. A model is
not production-ready because a training loss is low or a base checkpoint performs well. The exact
merged, converted, quantized, runtime-loaded artifact must pass these gates.

## Candidate Identity

A candidate must have a complete `ModelBundleManifest`:

- bundle ID and semantic version;
- Qwen upstream repository and exact revision;
- tokenizer, processor, and template hashes;
- universal adapter hash;
- merged model hash;
- GGUF hash;
- quantization;
- llama.cpp/runtime build identity;
- grammar/schema versions;
- training code commit;
- dataset snapshots;
- experiment IDs;
- license and distribution status;
- supported hardware;
- rollback predecessor.

Missing identity is an automatic failure.

## Zero-Tolerance Accepted-Path Gates

Across the full release suite:

- malformed patch accepted: 0;
- wrong capsule/revision/block/base hash accepted: 0;
- unauthorized block change accepted: 0;
- stale revision applied: 0;
- protected span changed: 0;
- number/date/unit/currency/identifier drift accepted: 0;
- quotation or citation loss accepted: 0;
- claim, modality, negation, attribution, or entity corruption accepted: 0;
- structural signature corruption accepted: 0;
- private/internal identifiers in public output: 0;
- unreviewed model patch committed: 0;
- model/cloud data in final artifact metadata: 0.

A raw candidate may fail. The HumanHand acceptance path may not.

## Model-Level Targets

Initial release targets:

| Metric | Minimum |
|---|---:|
| valid patch schema pass@1 | 98% |
| valid anchors pass@1 | 99.5% |
| hard-validator pass@1 | 90% |
| hard-validator pass@3 | 98% |
| appropriate abstention | 95% |
| human acceptance without edit | 60% |
| human acceptance with minor/no edit | 85% |
| style win vs untuned base | statistically credible |
| unauthorized exemplar copying | below defined threshold |
| runtime crash rate | 0 in qualification suite |

Mature targets and DeepSeek retirement targets are defined in ADR-015.

## Evaluation Slices

Report all metrics by:

- unseen author;
- unseen document;
- register;
- genre;
- sample sufficiency;
- language;
- block length;
- claim/protected-span density;
- citation/quotation density;
- local-only versus governor-assisted;
- base, merged, and quantized artifact;
- Windows and Linux runtime.

Aggregate scores cannot hide a failing critical slice.

## Style Evaluation

Use:

- StyleEvidence metric distance;
- hard invariants;
- exact mechanics where applicable;
- human pairwise preference;
- edit time and edit magnitude;
- phrase-copy and nearest-neighbor analysis;
- cross-register generalization.

The evaluation never claims perfect authorship imitation.

## Abstention Evaluation

Measure precision and recall for:

- insufficient context;
- insufficient style evidence;
- conflicting constraints;
- unsupported language/register;
- unsafe scope;
- output limit.

Over-abstention is a quality issue. Under-abstention on unsafe or ambiguous cases is a safety issue.

## Memorization and Leakage

Required tests:

- longest exact overlap with training targets;
- nearest-neighbor lexical and embedding similarity;
- prefix completion extraction;
- membership-inference diagnostics;
- PII and rare-string probes;
- canary tests on a non-production shadow model;
- author and project leakage;
- teacher-style concentration;
- adapter/base lineage audit.

A high-risk leakage finding blocks release or restricts the bundle to a private adapter.

## Robustness

Test:

- invalid/corrupt capsules;
- prompt injection in source and exemplar text;
- duplicate/contradictory claims;
- Unicode controls;
- long context and truncation;
- runtime timeout;
- empty or extra fields;
- special-token leakage;
- tool-call/reasoning leakage;
- multiple candidate ordering;
- governor outage and malformed response;
- no-model and no-governor fallbacks.

## Performance on RTX A2000 6 GB

Record:

- cold startup;
- model load memory;
- prompt processing speed;
- generation tokens/second;
- peak VRAM/RAM;
- 4K and 8K context behavior;
- candidate batch behavior;
- timeout rate;
- power/thermal observations where available.

The initial bundle must fit the supported configuration or document a smaller context/candidate
limit.

## Quantization Delta

Compare full-precision merged adapter versus Q4_K_M:

- hard-validator pass;
- schema rate;
- style preference;
- abstention;
- latency;
- memorization indicators.

A material quality regression blocks Q4_K_M promotion and requires a different quantization or
training change.

## Privacy and Runtime

- Loopback-only verified.
- No automatic downloads.
- No prompt/response logs.
- No tools or filesystem write.
- Hash verification.
- No model name or runtime fields entering public content.
- Strict-local works without network.
- Crash recovery and process cleanup pass.

## Regression and Rollback

Candidate must beat or match the champion on every hard gate and not materially regress critical
soft slices. Rollback to the prior bundle and deterministic-only mode must be tested before
promotion.

## Promotion Decision

The release controller outputs:

```text
PASS
FAIL
HUMAN_REVIEW_REQUIRED
```

Only a human maintainer can activate or publish the bundle. A pass report is evidence, not
authorization.
