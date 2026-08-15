# ADR-013: HumanHand Forge Is a Separate Training Control Plane

- Date: 2026-08-13
- Status: Accepted

## Context

The production HumanHand CLI is designed to remain small, local, deterministic, and installable
from a normal wheel. Training requires PyTorch, Transformers, PEFT, bitsandbytes, TRL, GPU
orchestration, experiment tracking, large artifacts, and autonomous agents. Combining these
surfaces would increase attack surface, dependency weight, and operational risk.

## Decision

Create HumanHand Forge as a separate package boundary under `forge/` initially, with a documented
option to move it to a separate private repository before live GPU use.

Forge owns:

- dataset snapshot building;
- training pair generation;
- synthetic degradation and negatives;
- SFT and optional DPO;
- experiment tracking;
- hyperparameter search;
- validator-guided candidate mining;
- red-team generation;
- model conversion/quantization;
- promotion-report preparation.

Production HumanHand owns:

- consent and gold-record capture;
- encrypted dataset export;
- model bundle verification;
- local inference;
- deterministic validators;
- human acceptance;
- public export.

## Trust Boundary

Forge receives an explicit encrypted dataset bundle and public contract schemas. It receives no
production database credentials, secret keys, cloud project credentials, or write access to user
projects.

Forge may call production validators as version-pinned libraries or CLI processes, but it cannot
modify validator code during an experiment.

## Autonomy

Agents may autonomously:

- construct eligible datasets;
- run bounded experiments;
- stop poor trials;
- generate adversarial cases;
- cluster failures;
- prepare a promotion report.

Agents may not:

- change release gates;
- add data without consent;
- infer authorship;
- publish or promote models;
- upload private data outside an approved provider configuration.

## Consequences

- Production installation stays lightweight.
- Training can evolve independently.
- Cross-package schema compatibility must be versioned and tested.
- Model promotion requires signed manifests and explicit human approval.
