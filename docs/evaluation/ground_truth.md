# Ground-truth precision/recall evaluation (curated conformance benchmark)

This benchmark answers a question reviewers always ask: *how accurate are the
detectors?* It pairs a hand-labeled gold set with a deterministic scorer that
reports per-class and overall precision / recall / F1, a confusion matrix, a
representative error analysis, and an inter-rater agreement slot — with no
network and no randomness.

It is a **curated conformance benchmark**, not a prevalence-representative
estimate of real-world performance: the set is balanced and hand-built for
coverage of each bug class (including its boundary cases), so the reported
precision/recall describe *this set*, not deployed telemetry at large. The
real-world wiring of the same machinery is separately validated against an
independent field oracle on telemetry harvested from real repositories (see
"Real-corpus oracle agreement" below).

## Semantic ground truth vs. the operational detector

The gold label is **semantic ground truth**: would a human (incident responder
or privacy reviewer) say the bug class — defined by the incident question it
blocks — genuinely holds for this sample? This is deliberately distinct from the
**operational detector contract**, which is a *sound-but-incomplete* approximation
keyed on a recognized set of fields/patterns. The two coincide on ordinary cases
and diverge exactly on the documented incompleteness / false-positive sources;
measuring precision/recall is precisely measuring that divergence. Concretely:

- `mc-hard-altkey` carries a correlation id under an unrecognized field name
  (`correlationGuid`). *Semantically* the failure **is** correlated, so the
  missing-correlation gap is **absent** (gold negative); the field-keyed detector
  does not recognize the alias and reports it (a false positive). This is the
  documented "correlation id under an unrecognized key" incompleteness, not a
  relabeling to manufacture an error.

Labeling against semantic truth (and not against the detector's own field set) is
what makes precision/recall meaningful rather than tautological.

## Labeling protocol

- **Unit of evaluation.** One *(sample, bug-class)* pair. A *sample* is a small,
  self-contained list of telemetry events; the *bug class* is one of the six
  defined in [`bug_classes.py`](../../telemetry_contracts/bug_classes.py).
- **Label.** A boolean: `true` iff the bug class is *genuinely present* in the
  sample (a positive), `false` iff it is *genuinely absent* (a negative). The
  label is objective truth about the sample, independent of what the detector
  predicts.
- **Rationale.** Every item records a short human justification, so a second
  labeler (or a reviewer) can adjudicate.
- **Adjudication.** When two labelers disagree, the sample is re-examined against
  the bug-class definition; the definition — not majority vote — is decisive,
  because each class has a precise, testable definition.

## Gold-set format (`telemetry-contracts/gold@1`)

A gold set is a JSONL file, one object per line:

```json
{"id": "mc-pos-00", "bug_class": "missing-correlation", "label": true,
 "events": [{"kind": "event", "name": "handle_failed", "severity": "error"}],
 "rationale": "failure event carries no correlation id",
 "labeler": "primary", "second_label": true,
 "source": {"subject": "owner/repo", "sha": "<40-hex>", "host": "github"}}
```

`id` is unique; `events` is non-empty; `labeler`, `second_label`, and `source`
are optional. The curated set lives at
[`benchmarks/ground_truth/curated.jsonl`](../../benchmarks/ground_truth/curated.jsonl)
and is regenerable with `python3 scripts/gen_gold.py`.

## Running

```bash
python3 -m telemetry_contracts.cli evaluate-gold \
  --gold benchmarks/ground_truth/curated.jsonl --format markdown

# Enforce a quality bar in CI (per-mille, 0–1000):
python3 -m telemetry_contracts.cli evaluate-gold \
  --gold benchmarks/ground_truth/curated.jsonl --min-f1 900 --min-class-f1 850
```

## What the predictor runs

For each sample the scorer runs the *shipped* detectors, so the benchmark
measures the real tool:

- **missing-duration** is decided by the diagnosis component counts
  (`diagnose(...).components.spans_without_duration`), mirroring the engine.
- the other five classes are decided by `analyze_events(...)` findings whose
  code maps to the class via the single-source-of-truth `CODE_TO_BUG_CLASS`.

## Metrics

- **Per class and overall (micro):** precision = TP/(TP+FP), recall =
  TP/(TP+FN), F1 = 2·TP/(2·TP+FP+FN), all reported in per-mille (half-up) so the
  numbers are byte-identical across machines; macro averages are also reported.
- **Confusion matrix:** TP/FP/FN/TN per class, so error modes are explicit.
- **Error analysis:** up to eight representative false positives and false
  negatives with their rationale, feeding the discussion of limitations.
- **Inter-rater reliability:** Cohen's kappa over the doubly-labeled subset.

## Honesty: every residual error is a documented limitation

The curated set is deliberately *not* vacuously perfect. Its few residual errors
are exactly the documented incompleteness / false-positive sources:

| Case | Class | Why it is wrong on purpose |
| --- | --- | --- |
| `mc-hard-altkey` | missing-correlation (FP) | correlation id under an unrecognized field name |
| `me-hard-msgonly` | missing-error-evidence (FP) | error cause only in a free-text message |
| `sv-hard-b64` | sensitive-values (FN) | base64-encoded credential, not a raw pattern |
| `uc-hard-smallsample` | unbounded-cardinality (FN) | unbounded at scale but below the trust threshold |
| `us-hard-altname` | unclassified-sensitive (FN) | sensitive identifier under an unrecognized name |

These mirror the per-class `incompleteness` and `false_positive_sources`
statements, so the accuracy figures and the soundness statements cannot drift
apart.

## Real-corpus oracle agreement (wiring validation)

A network-gated test clones the frozen corpus, harvests real telemetry events,
and derives objective labels for the two *field-decidable* classes
(missing-correlation, missing-duration) with an **independent oracle** — a
separate, hardcoded key set kept outside the engine. It asserts the shipped
predictor agrees exactly with the oracle on every harvested instance. This
validates that the scorer is correctly wired to the engine on real-world data;
it is a wiring/agreement check, **not** an independent measurement of semantic
accuracy (the oracle and the engine share the same canonical-field assumption).
The pattern-based classes (sensitive values, cardinality) are not field-decidable
and are covered only by the curated set.

## Scope and threats to validity

- **Not a real-world estimator.** This is a curated, balanced conformance
  benchmark; its precision/recall describe the set, not a random sample of
  deployed telemetry. A prevalence-representative estimate would require a
  pre-registered stratified random sample of events, blind double labeling, and
  reported confidence intervals — future work tracked in the corpus.
- **Per-pair, not multilabel.** Each row scores one *(sample, bug-class)* pair;
  findings of *other* classes on the same events are ignored unless that pair is
  separately labeled. Overall figures are therefore per-class micro-averages, not
  event-level multilabel performance.
- **Construct.** Labels are tied to the testable bug-class definitions; the
  rationale field records the justification so the construct is inspectable. The
  semantic labels for "correlation" and "error evidence" depend on human
  interpretation, which the definitions pin down.
- **External.** The field-decidable classes are additionally cross-checked
  against an independent field oracle on real harvested telemetry (above). The
  synthetic hard cases may not match real-world distributions.
- **Conclusion.** All arithmetic is integer/fixed-point and the report is
  byte-stable, so the numbers are reproducible. (Cohen's kappa uses floating
  point over small rationals; it is stable across platforms but is not part of
  the byte-locked core.)
- **Inter-rater subset.** The doubly-labeled subset is small and includes the
  ambiguous hard cases plus representative clean cases; it is illustrative of the
  IRR mechanism rather than a powered agreement study.
