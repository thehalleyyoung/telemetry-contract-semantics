# Evaluation

This directory is the home of the project's empirical story. It is written so it
also serves as the outline of a research paper's evaluation: a reproducible study
over real repositories, the metrics it reports, and the threats to its validity.

The guiding thesis is that **observability is a correctness property** —
under-instrumentation is a detectable bug class, not a matter of taste. Each bug
class has a precise, testable definition and an explicit statement of what a
finding does and does not guarantee (see
[`../bug_classes` source of truth](../../telemetry_contracts/bug_classes.py)).

## Research statement

Production telemetry is routinely under-instrumented in ways that make incidents
hard to diagnose, yet "good observability" is usually treated as a style
preference rather than a checkable property. We claim that observability is a
**correctness property**: a small set of incident questions ("why did this
request fail?", "what error caused it?", "how long did it take?", "is this data
safe to retain?") induces a bug class of *missing evidence* that can be defined
precisely, detected statically from the telemetry and code a project already
ships, scored deterministically, and improved in measurable stages — with each
detector carrying an explicit soundness/incompleteness statement. We evaluate
this on a frozen, pinned-commit corpus of repositories authored without this
tool in mind, reporting bug-class prevalence and a diagnosability-score
distribution, and we lead with a single reproducible headline statistic: the
share of telemetry-bearing repositories that cannot answer "why did this request
fail?".

## Contents

- [`corpus_study.md`](corpus_study.md) — the corpus mining study: how a frozen,
  pinned-commit set of pre-existing repositories is scanned and reduced to a
  single deterministic dataset and report, including the headline statistic.
- [`ground_truth.md`](ground_truth.md) — the precision/recall benchmark: a
  hand-labeled gold set scored against the shipped detectors, reporting per-class
  and overall precision / recall / F1, a confusion matrix, error analysis, and an
  inter-rater agreement slot.
- [`baselines.md`](baselines.md) — the baseline comparison: the detectors scored
  head-to-head, through the same gold-set pipeline, against deterministic
  capability baselines (rule-light, OTel-convention conformance, and an offline
  LLM-baseline harness), with covered-class metrics, a symmetric win/loss
  analysis, and an exact paired significance test.
- [`../formal_model.md`](../formal_model.md) — the formal model: the semantic
  guarantees (refinement order, monotonicity, termination, assume-guarantee,
  abstract-domain soundness, transformation preservation) stated precisely, tied
  to code and tests, and discharged by deterministic executable witnesses
  (`python3 -m telemetry_contracts.cli formal-model`).

## Reproducing the study

The study runs over a declarative, pinned-commit corpus manifest. The bundled
tier-1 corpus is a small multi-host set that runs quickly:

```bash
python3 -m telemetry_contracts.cli mine-corpus \
  --manifest benchmarks/corpus/tier1.json \
  --format markdown
```

Every subject is pinned to an exact 40-character commit SHA, so a given corpus
produces a byte-identical dataset on any machine with network access. The
analytic core of the dataset (headline statistic, per-class prevalence, score
distribution, and per-subject rows) is deterministic by construction: all
collections are sorted and all arithmetic is integer or fixed-point.

## What the study measures

- **Headline statistic** — the share of telemetry-bearing repositories that
  cannot answer the question _"why did this request fail?"_, defined as carrying
  at least one failure event with no correlation identifier.
- **Bug-class prevalence** — for each bug class, how many repositories exhibit
  it (with a per-host breakdown) and the total number of findings.
- **Diagnosability-score distribution** — min / p25 / median / p75 / max / mean
  of the 0–100 diagnosability score across telemetry-bearing repositories.

## Soundness and incompleteness

Every bug class carries a guarantee (what a finding establishes) and an
incompleteness statement (what a clean result does *not* establish, and the
known false-negative and false-positive sources). The headline statistic uses
the conservative, finding-based definition of the correlation gap, so it never
over-reports relative to the per-class prevalence.
