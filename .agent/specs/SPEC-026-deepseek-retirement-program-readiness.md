# SPEC-026: DeepSeek Reduction, Retirement Gate, and Program Readiness

## Purpose

Measure whether the local 2B writer has learned enough to remove DeepSeek from the recommended path
and complete the post-SLM production-readiness program honestly.

## Metrics

Collect privacy-preserving aggregates:

- local candidate count;
- hard-valid pass@1/pass@3;
- abstention by reason;
- human acceptance/edit level;
- style distance and preference;
- DeepSeek plan/critique/diagnosis counts;
- cloud cost and latency;
- quality delta local-only versus hybrid;
- failure clusters;
- model/runtime version.

Raw text is not required for aggregate reporting.

## Evaluation Design

Blind A/B on held-out unseen authors/documents:

- local only;
- local + Flash critique;
- Pro plan + local;
- Pro plan + local + Flash critique.

Use preregistered metrics and confidence/uncertainty. Report slices and avoid hiding failures in
averages.

## Retirement Gate

Apply ADR-015 thresholds. DeepSeek is removed from the recommended path only when:

- local metrics meet thresholds;
- hybrid material benefit is below threshold;
- no critical slice remains dependent;
- no-governor disable equivalence passes;
- user-visible quality/edit time is acceptable.

## Outcomes

Possible:

- retain hybrid-quality recommendation;
- local-first default with bounded escalation;
- remove DeepSeek from recommended path but retain plugin;
- block release due to local regression.

## Full Readiness

EP-028 additionally requires:

- all EP-020–027 plans complete/audited;
- exact model bundle qualified;
- consent/data/Forge governance proven;
- docs/commands/security/operations updated;
- Windows/Linux CI green;
- rollback drill;
- remaining risks explicit;
- no detector-evasion feature;
- no automatic publication.

## CLI and Reports

Potential commands:

```text
humanhand metrics local-writer
humanhand governor retirement-report
humanhand model readiness
```

Report contains stable gate IDs, evidence references, status, limitations, and recommendation.

## Tests

- aggregate metrics contain no text;
- A/B assignment and analysis;
- threshold boundaries;
- insufficient sample status;
- slice regression blocks retirement;
- DeepSeek disabled/uninstalled;
- rollback;
- full program readiness report;
- docs and forbidden-policy scans.

## Acceptance Criteria

- Recommendation is evidence-based.
- DeepSeek remains optional at all times.
- Program readiness cannot be green with blocked required gates.
- Exact quantized local writer and fallback paths are proven.
