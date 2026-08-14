# SPEC-023: Qwen3.5-2B QLoRA Supervised Fine-Tuning

## Purpose

Train the universal HumanHand Writer Core on Qwen3.5-2B-Base using QLoRA SFT and authentic-target
reconstruction, while preserving contract compliance, factual fidelity, abstention, and
generalization to unseen authors.

## Preconditions

- EP-020 contracts frozen.
- EP-023 dataset governance complete.
- EP-024 Forge operational.
- Eligible immutable dataset snapshot.
- Official upstream revision and license verified.
- Held-out authors/documents frozen.
- Compute budget approved.

## Training Tasks

Mixture includes:

- exact EditPatch schema;
- anchor copying;
- bounded block replacement;
- style-conditioned reconstruction;
- copyedit and recompose operations encoded by policy;
- fact/citation/structure preservation;
- continuity bridging;
- minimal revision;
- abstention;
- adversarial instruction rejection.

## Dataset Format

Use production WriterRequest as prompt and strict EditPatch as completion. Exemplar and target
leakage is prohibited. Completion-only loss is preferred.

## Initial QLoRA Search Space

Bounded starting search:

- rank 8, 16, 32, 64;
- alpha 2x rank;
- dropout 0.0 or 0.05;
- learning rate 5e-5, 1e-4, 2e-4;
- sequence length 2048, 4096, optional 8192;
- one to three epochs;
- NF4 double quantization;
- BF16 where supported, otherwise validated FP16;
- gradient checkpointing;
- packed and unpacked comparison;
- language-model linear modules selected by architecture inspection.

Do not blindly train vision components, embeddings, or LM head without an evidence-backed trial.

## Objectives

Primary selection is lexicographic:

1. zero-tolerance system acceptance gates;
2. patch schema/anchor rate;
3. hard-validator pass;
4. abstention;
5. style/human preference;
6. latency/resource use.

Training loss is diagnostic only.

## Evaluation

Evaluate every checkpoint on unseen authors/documents and slices in `MODEL_RELEASE_GATES.md`.
Include base-model baseline and exemplar-only conditioning.

## Early Stopping

Stop or reject trials for:

- hard-gate regression;
- validation-loss divergence;
- schema degradation;
- memorization increase;
- no improvement versus smaller/cheaper trial;
- budget limit.

## Artifacts

- adapter weights;
- trainer state if retained;
- config;
- manifest;
- checkpoint metrics;
- dataset snapshot;
- evaluation reports;
- model card draft;
- privacy/memorization report.

## Security and Privacy

Training workers use approved snapshots only. No automatic hub upload. External GPU storage and
cleanup follow policy. Secrets are isolated. Checkpoints are treated as sensitive until leakage
qualification passes.

## Tests

- tiny synthetic SFT smoke test;
- exact template/label masking;
- architecture target-module discovery;
- resume checkpoint;
- data split assertion;
- metric pipeline;
- failed trial handling;
- no upload;
- manifest completeness;
- gated real 2B run;
- base/champion comparison.

## Acceptance Criteria

- At least one SFT candidate materially beats untuned base on HumanHand task metrics.
- No critical held-out slice regresses below policy.
- Memorization and privacy tests are within thresholds.
- Full lineage and reproducibility evidence exists.
- Human maintainer selects the SFT champion; Forge cannot.
