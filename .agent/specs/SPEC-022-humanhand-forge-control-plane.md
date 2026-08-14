# SPEC-022: HumanHand Forge Autonomous Training Control Plane

## Purpose

Create a separate, policy-bounded training system that can autonomously build datasets, run
experiments, evaluate, red-team, quantize, and prepare promotion proposals without accessing live
projects or promoting models.

## Package Boundary

Initial path: `forge/`, separately installable and excluded from the normal HumanHand wheel.
Before private live training it may move to a dedicated private repository via ADR.

## Inputs

- signed/encrypted DatasetSnapshot;
- contract/schema package;
- version-pinned HumanHand validator package;
- upstream model manifest;
- experiment plan;
- compute/provider budget;
- human-approved policy.

## Outputs

- experiment manifests;
- checkpoints and adapters;
- evaluation and red-team reports;
- preference datasets;
- converted/quantized candidate bundles;
- release-controller report;
- human promotion proposal.

## Components

Corpus Curator, Pair Builder, Candidate Generator, Validator Farm, Preference Miner, Experiment
Scientist, Red-Team Agent, Quantization Builder, and deterministic Release Controller.

## Autonomy Policy

Allowed:

- bounded data construction;
- trial scheduling;
- early stopping;
- failure clustering;
- synthetic/adversarial generation;
- metric collection;
- report generation.

Blocked:

- new consent/authorship decisions;
- validator modification;
- release-gate modification;
- production write access;
- model promotion/publication;
- unapproved provider upload;
- unbounded compute/cost;
- detector-evasion optimization.

## Experiment Manifest

Must include code/data/model/environment/hardware/hyperparameter/seed/artifact/metric identity.
Dirty or unidentifiable code states are ineligible for promotion.

## Tracking

Use local/self-hosted tracking or file-backed manifests. Provider-hosted tracking requires a
separate privacy approval. Raw content is encrypted and access-controlled.

## Worker Isolation

Training workers receive only the snapshot and experiment config. They do not receive HumanHand
project keys, DeepSeek production key, or repository write credentials.

## Failure Behavior

- Snapshot integrity failure: stop dependent experiments.
- Missing dependency/hardware: mark blocked, no fabricated result.
- Trial failure: record bounded error and continue when policy permits.
- Budget exhaustion: stop pending trials.
- Validator mismatch: reject candidate.
- Promotion ambiguity: require human review.

## CLI

Potential separate commands:

```text
humanhand-forge snapshot verify
humanhand-forge pairs build
humanhand-forge train sft
humanhand-forge mine preferences
humanhand-forge train dpo
humanhand-forge evaluate
humanhand-forge redteam
humanhand-forge quantize
humanhand-forge release assess
```

## Reproducibility

- exact lock files/container definitions;
- pinned model and dataset revisions;
- explicit seeds and deterministic settings;
- hardware/software report;
- immutable manifests;
- rerun verification on a sample trial.

Where bitwise determinism is unavailable, report bounded reproducibility honestly.

## Tests

- synthetic snapshot only in CI;
- agent permission boundaries;
- budget cancellation;
- manifest completeness;
- dirty code rejection;
- validator read-only enforcement;
- no promotion permission;
- experiment resume/idempotence;
- artifact hash verification;
- mocked provider/GPU tasks;
- live GPU gate;
- separate-wheel/package isolation.

## Acceptance Criteria

- Forge is installable separately.
- A synthetic end-to-end experiment can run without production credentials.
- Agents cannot add data, alter gates, or promote.
- Every artifact has complete lineage.
- Failure/restart is safe and idempotent.
