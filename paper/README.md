# Observability is a Correctness Property

**Paper skeleton.** Section scaffolding for the ICSE submission. Headline numbers
below are transcribed from the deterministically regenerated artifacts under
`reports/` (`paper_tables.md`, `gold_evaluation.json`, `baseline_comparison.json`)
and are reproduced by `docs/artifact_evaluation/reproduce.sh --check`. Update the
prose, never hand-edit the numbers — regenerate and re-transcribe.

---

## Abstract

Software is routinely shipped with *blind spots*: code paths whose telemetry is
insufficient to answer "what happened, and why did it fail?" We argue that
**observability is a correctness property** — under-instrumentation is a
detectable, classifiable defect class, not a matter of taste — and we build a
static + finite-trace analysis that validates an *observability contract* against
the telemetry a project already emits. The tool is zero-config, format-agnostic,
pure standard library, and byte-deterministic. On a curated gold set of 112
labelled cases it reaches F1 0.953 (precision 0.962, recall 0.944) and
significantly outperforms a keyword baseline (F1 0.809), an OpenTelemetry
semantic-convention conformance baseline (0.771), and a recorded LLM-style
surrogate (0.563), with an exact paired McNemar test (p < 0.0001 vs. each).

## 1. Introduction

- The blind-spot problem: incidents that telemetry cannot explain.
- Thesis: observability gaps are bugs with a definable specification.
- Contributions:
  1. A formalization of observability gaps as violations of an observability
     contract over events, with an explicit approximation direction.
  2. A zero-config, format-agnostic, deterministic analysis that runs on
     unmodified third-party repositories.
  3. An evaluation against a frozen gold set and three baselines, plus a corpus
     study over public repositories, all reproducible by one command.

## 2. Motivating example

- The GitLab 2017 database-outage reconstruction
  (`case_studies/gitlab_2017_database_outage`): which questions the emitted
  telemetry can and cannot answer, and the gap the tool flags.

## 3. Approach and formalization

- Observability contract: required fields, correlation, error evidence,
  cardinality budgets, privacy/PII non-disclosure, temporal properties.
- Soundness framing: presence-abstraction is an *under-approximation* of what the
  program can emit; reported gaps are conservative. The 13 machine-checked
  guarantees in `telemetry_contracts/formal_model.py` (refinement-order axioms,
  staged-loop monotonicity, termination, assume–guarantee, abstract-domain
  presence soundness, transformation preservation), each discharged by an
  executable witness.
- Finite-trace hyperproperties for privacy non-disclosure.

## 4. Implementation

- Pure-stdlib engine; format-agnostic adapters (JSONL, JSON, logfmt, OTLP) with a
  tolerant mode. Zero-config inference of an initial contract from existing data.
- Determinism by construction: sorted aggregates, fixed-point arithmetic, no
  wall-clock, no RNG. A SHA-256 manifest plus a CI gate guarantee artifacts match
  their generators.
- Surfaces: CLI, GitHub Action, SARIF, scorecard badge, and a zero-install
  Pyodide browser playground.

## 5. Evaluation

### 5.1 Gold-set accuracy (RQ1)

From `reports/gold_evaluation.json` (N = 112; 54 positive, 58 negative):

| Metric | Value |
| --- | ---: |
| Precision | 0.962 |
| Recall | 0.944 |
| F1 | 0.953 |
| TP / FP / FN / TN | 51 / 2 / 3 / 56 |

### 5.2 Baseline comparison (RQ2)

Covered-class F1 (‰), from `reports/baseline_comparison.json`, every method scored
through the identical pipeline seeing only `(events, bug_class)`:

| Method | Covered-class F1 | McNemar vs. tool |
| --- | ---: | --- |
| **telemetry-contracts (this tool)** | **0.953** | — |
| rule-light keyword detector | 0.809 | tool-only correct 20 vs 1, p < 0.0001 |
| OTel semantic-convention conformance | 0.771 | significant at 0.05 |
| recorded-surrogate (LLM harness) | 0.563 | significant at 0.05 |

The recorded surrogate is a transparent hand-written stand-in, explicitly **not**
an LLM accuracy claim (see `docs/evaluation/baselines.md`).

### 5.3 Corpus study on real repositories (RQ3)

`mine-corpus` over pinned public repositories authored without this tool:
the share of telemetry-bearing, failure-bearing repositories that *cannot* answer
"why did this fail?" Reproduce with `TELEMETRY_CONTRACTS_NETWORK_TESTS=1`.

### 5.4 Determinism and reproducibility (RQ4)

Every offline figure and number is regenerated and diffed against the committed
manifest by one command; the `determinism` CI workflow enforces it on each push.

## 6. Threats to validity

See `docs/evaluation/threats_to_validity.md`.

## 7. Related work

- Specification mining and runtime verification.
- Log/telemetry quality and anomaly detection.
- Observability and SRE practice; OpenTelemetry semantic conventions.
- Static analysis for non-functional properties.

## 8. Conclusion

Observability gaps are a tractable, formally-grounded defect class that can be
detected on the data projects already have — no prescribed labeling practice
required.

---

### Reproducibility

```bash
docs/artifact_evaluation/reproduce.sh --check
```
