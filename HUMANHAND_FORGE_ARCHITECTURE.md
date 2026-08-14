# HumanHand Forge Architecture

## Purpose

HumanHand Forge is the autonomous experiment and training control plane. It turns approved
HumanHand records into reproducible SFT/DPO experiments and promotion proposals while remaining
separate from the production document system.

## Boundary

```text
Production HumanHand
  consent + accepted revisions + contracts + validators
        |
        | encrypted immutable dataset export
        v
HumanHand Forge
  snapshot -> pair build -> train -> evaluate -> red-team -> quantize -> report
        |
        | signed candidate model bundle + promotion report
        v
Human maintainer approval
        |
        v
Production model registry
```

Forge has no live project database credentials and cannot alter production state.

## Components

### Corpus Curator

- validates consent, rights, authorship, and classification;
- assigns deterministic splits;
- deduplicates;
- builds immutable snapshots;
- rejects ineligible items.

### Pair Builder

- constructs authentic-target reconstruction pairs;
- selects non-overlapping exemplars;
- creates deterministic and teacher-assisted degradations;
- builds exact production capsules;
- emits SFT, abstention, and preference schemas.

### Candidate Generator

- invokes the current student and optional approved teacher;
- creates hard negatives and red-team cases;
- labels model, prompt, settings, and lineage;
- cannot label correctness.

### Validator Farm

Runs version-pinned HumanHand validators and records:

- schema/anchor/scope;
- protected facts;
- claims/citations/structure;
- style;
- privacy;
- overlap/memorization;
- latency/resources.

Validator code is mounted read-only and identified by commit hash.

### Preference Miner

- discards hard-invalid outputs;
- selects deterministic wins;
- creates DPO pairs only when chosen and rejected share the same prompt;
- sends ambiguous style choices to human review;
- preserves rejection codes.

### Experiment Scientist

- creates bounded trial matrix;
- trains QLoRA SFT and optional DPO;
- applies early stopping;
- records environment, seed, data, code, hardware, and metrics;
- never changes release gates.

### Red-Team Agent

Generates adversarial capsules involving:

- stale revisions;
- prompt injection in source;
- conflicting style evidence;
- close numeric values;
- modality/negation traps;
- nested citations/quotations;
- multilingual and Unicode cases;
- exemplar-copy traps;
- long and sparse context;
- corrupted runtime responses.

### Quantization Builder

- merges adapter into full-precision base;
- converts from full precision to GGUF;
- creates Q4_K_M from the merged artifact;
- never requantizes a quantized model;
- records toolchain hashes.

### Release Controller

Deterministic code that evaluates `MODEL_RELEASE_GATES.md`. It can emit pass, fail, or
human-review-required. It cannot promote, publish, or deploy.

## Experiment Manifest

Every trial records:

- experiment and parent IDs;
- git commit and dirty-state assertion;
- dataset snapshot ID;
- upstream model revision;
- tokenizer/template;
- adapter method and targets;
- quantization config;
- optimizer, scheduler, precision;
- batch, accumulation, sequence length, packing;
- seeds and deterministic flags;
- hardware and software environment;
- checkpoints and hashes;
- evaluation outputs;
- cost and runtime;
- failure or stop reason.

## Autonomous Loop

```text
select approved snapshot
  -> construct trial matrix
  -> train bounded candidates
  -> reject obvious underperformers
  -> evaluate held-out suites
  -> generate validator-guided candidates
  -> mine preferences
  -> optional DPO candidates
  -> quantize finalists
  -> run exact-artifact release gates
  -> prepare champion/challenger report
  -> STOP for human promotion decision
```

Budgets bound trials, GPU-hours, provider calls, wall time, and storage. The loop cannot add data or
repeat indefinitely.

## SFT

SFT teaches:

- exact patch schema;
- integrity-anchor copying;
- bounded one-block editing;
- abstention;
- fact/citation/structure preservation;
- style-conditioned reconstruction;
- no reasoning or tool output.

Completion-only loss is preferred. The production chat template and schema must be used.

## DPO

DPO is optional. Pairs require:

- identical prompt/capsule;
- hard-valid chosen output;
- documented rejected defect or human preference;
- no split leakage;
- no detector-evasion reward.

The SFT champion remains deployable if DPO does not produce a statistically credible benefit.

## Tracking and Storage

Forge may use a local/self-hosted experiment tracker. Raw private content must remain encrypted and
access-controlled. Provider-hosted tracking is prohibited unless separately approved.

Artifacts are content-addressed. Checkpoints have retention policies. Release candidates and
manifests are immutable.

## Failure Handling

- Training failure: retain manifest and sanitized error, not secrets.
- Validator regression: fail candidate.
- Dataset integrity failure: stop all dependent trials.
- Cost overrun: cancel pending trials.
- Provider outage: continue local-only tasks or pause.
- Ambiguous promotion: require human review.
- Missing reproducibility evidence: candidate cannot promote.

## Initial Cost Strategy

- Run integration and corpus tooling locally.
- Use the RTX A2000 for quantized inference and small smoke experiments.
- Use short-lived 24 GB or larger workers for serious 2B QLoRA.
- Run small sweeps first.
- DPO only after sufficient preference data.
- Never purchase hardware as a prerequisite.

## Separation Option

Before live private training, the maintainer may move `forge/` to a dedicated private repository.
The contracts, manifests, and validator package remain versioned interfaces. This move requires an
ADR but not a change to model authority.
