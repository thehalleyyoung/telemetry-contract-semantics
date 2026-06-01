# Baseline comparison

ICSE-grade evaluations need baselines: a detector is only interesting relative to
what a simpler or differently-scoped method would catch. This page documents the
deterministic, offline baselines this project ships and the head-to-head result
on the curated gold set (see [`ground_truth.md`](ground_truth.md) for the gold
set itself).

Run it yourself:

```bash
python3 -m telemetry_contracts.cli compare-baselines \
  --gold benchmarks/ground_truth/curated.jsonl
```

All methods are scored through the **identical** pipeline
(`telemetry_contracts.evaluation.score_gold_set`) over the same 112 hand-labeled
`(sample, bug-class)` items, so the comparison is apples-to-apples. Every method
sees only `(events, bug_class)` — never the gold label or rationale.

## The baselines

These are **capability baselines**, chosen to answer a specific question, not
claimed state-of-the-art detectors. Their definitions are frozen before the
comparison is snapshotted and no threshold is tuned on the gold set.

- **rule-light** — a deliberately naive detector that checks only whether an
  *obvious field name* is present (e.g. `trace_id`, `duration_ms`). No
  thresholds, no statistics, no failure gating, no value inspection. It answers:
  *what would a keyword linter catch?* It is value-blind, so it misses raw
  secrets hidden in innocently-named fields, and it has no statistical notion, so
  it cannot see unbounded cardinality at all (that class is out of scope for it).

- **semantic-convention-only** — flags solely missing OpenTelemetry
  semantic-convention fields (trace context, span duration, exception/status
  fields). It answers: *is convention conformance the same as correctness?* For
  sensitive values, unclassified identifiers, and unbounded cardinality the
  conventions define no detector, so those classes are reported **out of scope**
  — a coverage result, not an accuracy penalty. We therefore report both an
  all-class score (which shows the coverage limit) and a covered-class score
  (which is the fair within-scope accuracy).

- **recorded-surrogate (LLM-baseline harness)** — a deterministic
  prompt + parser + replay-cache harness designed to host an LLM-only "find the
  gaps" comparator entirely offline (`build_llm_prompt`, `parse_llm_verdict`,
  `llm_cache_key`, and a cached response per item). **Important honesty note:**
  the artifact ships no network access and no commercial-model output, so the
  cache is filled by a *transparent, hand-written surrogate policy* (a
  high-recall, over-flagging reviewer). This row is **not** an LLM result and
  makes **no** claim about real LLM accuracy. It exists to (1) prove the harness
  is deterministic and offline, and (2) provide a comparator with a deliberately
  different (over-flagging) error profile. To obtain a real LLM-baseline row, an
  evaluator records actual model outputs (with model, version, date, prompt, and
  decoding parameters) into the same cache; the harness then replays them
  deterministically.

## Head-to-head on the curated gold set

> Baseline definitions are fixed before snapshotting; no threshold is tuned on
> the gold set; every method sees only `(events, bug_class)`, never the gold
> label or rationale. Out-of-scope classes are reported as coverage gaps, not
> accuracy failures.

### All-class (micro-averaged)

| Method | Kind | Precision | Recall | F1 | Macro F1 | Predicted+ | TP/FP/FN/TN |
| --- | --- | ---: | ---: | ---: | ---: | ---: | --- |
| telemetry-contracts (this tool) | tool | 96.2% | 94.4% | 95.3% | 95.2% | 53 | 51/2/3/56 |
| rule-light keyword detector | baseline | 85.7% | 66.7% | 75.0% | 65.3% | 42 | 36/6/18/52 |
| OTel semantic-convention conformance | baseline | 62.8% | 50.0% | 55.7% | 39.6% | 43 | 27/16/27/42 |
| recorded-surrogate (LLM harness check) | surrogate | 46.9% | 70.4% | 56.3% | 50.1% | 81 | 38/43/16/15 |

### Covered-class only (excludes each method's out-of-scope classes)

| Method | Covered classes | Precision | Recall | F1 |
| --- | --- | ---: | ---: | ---: |
| telemetry-contracts (this tool) | 6/6 | 96.2% | 94.4% | 95.3% |
| rule-light keyword detector | 5/6 | 85.7% | 76.6% | 80.9% |
| OTel semantic-convention conformance | 3/6 | 62.8% | 100.0% | 77.1% |
| recorded-surrogate (LLM harness check) | 6/6 | 46.9% | 70.4% | 56.3% |

The covered-class view is the *fairest* read of each baseline: even when
semantic-convention-only is scored only on the three classes it can express, it
still trades precision for recall (it flags every failure-ish event lacking an
OTel field), and it remains structurally blind to half the taxonomy.

### Paired significance vs the tool (exact two-sided McNemar)

Because every method is scored on the same 112 items, the right test is a
*paired* one. We report an exact two-sided McNemar/sign test over the discordant
pairs (items one method gets right and the other gets wrong).

| Baseline | Tool-only correct | Baseline-only correct | Exact p | Sig. @0.05 |
| --- | ---: | ---: | ---: | :---: |
| rule-light keyword detector | 20 | 1 | 0.0000 | yes |
| OTel semantic-convention conformance | 38 | 0 | 0.0000 | yes |
| recorded-surrogate (LLM harness check) | 55 | 1 | 0.0000 | yes |

The tool significantly outperforms every baseline on this set. The test applies
to this curated benchmark; it is not a claim of generalization to all telemetry.

### Symmetric win/loss

The comparison reports, for each baseline, the items the **tool** gets right and
the baseline misses, the items the **baseline** gets right and the tool misses,
and the **shared** false positives and false negatives. This is deliberately
two-sided: the tool has five documented residual errors, and a fair baseline
section must show whether a simpler method happens to avoid any of them. (It
does: rule-light's name-only sensitive rule gets `us-hard-altname` right where
the tool's name list misses it — at the cost of much lower recall elsewhere.)

## Cost / feasibility

Accuracy is not the only axis. The method's practical advantage is that it needs
**no setup and assumes no conventions**, runs **offline and deterministically**,
and is the only comparator that is both **value-aware** and **statistical** (so
it can see raw secrets in oddly-named fields and unbounded cardinality):

| Method | Setup | Conventions | Deterministic | Offline | Value-aware | Statistical |
| --- | --- | --- | :---: | :---: | :---: | :---: |
| telemetry-contracts (this tool) | none | none | yes | yes | yes | yes |
| rule-light | none | none | yes | yes | no | no |
| semantic-convention-only | adopt OTel | OpenTelemetry | yes | yes | no | no |
| recorded-surrogate | model access (surrogate shipped offline) | none | yes | yes | no | no |

## Threats to validity

- **Curated, balanced set.** The numbers describe the curated conformance set,
  not a prevalence-representative sample; treat the paired test as evidence about
  this benchmark.
- **Author-designed baselines.** rule-light and semantic-convention-only are
  intentionally simple; we mitigate strawman risk by reporting covered-class
  metrics, a symmetric win/loss, and a frozen-before-snapshot protocol.
- **Surrogate, not an LLM.** The LLM-baseline row is a deterministic surrogate;
  it demonstrates the offline harness and a different error profile only.
- **Future work.** Detector ablations (value-inspection off, failure-gating off,
  statistical-cardinality off) and a recorded real-LLM row would further
  strengthen this section.

## Reproducing

```bash
# Regenerate the recorded-surrogate cache from the gold set (deterministic).
python3 scripts/gen_llm_baseline_cache.py

# Emit the comparison as JSON (the full machine-readable dataset).
python3 -m telemetry_contracts.cli compare-baselines \
  --gold benchmarks/ground_truth/curated.jsonl --format json
```

The offline snapshot test `tests/test_baselines.py` locks the headline numbers;
`tests/test_baselines_real.py` (network-gated) proves the baselines run
correctly and deterministically on real GitHub/GitLab/Bitbucket repositories
authored without this tool in mind.
