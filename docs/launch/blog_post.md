# Observability is a correctness property

*Launch post — reproducible numbers from a frozen corpus study.*

Most teams treat observability as a matter of taste: add more logs if you feel
like it. We think that's wrong. **Under-instrumentation is a detectable bug
class.** If a failure is recorded but can't be joined to the request that caused
it, you have a defect — the same way an off-by-one is a defect — and it can be
found mechanically, before the incident.

`telemetry-contracts` is a pure-stdlib tool that points at the telemetry you
*already* have (JSON logs, traces, metrics, logfmt, OTLP — whatever shape) and
tells you which incident questions you can't answer yet. No contract to write
first, no relabeling, no semantic-convention adoption.

## The headline

We ran the engine over a small, frozen corpus of public repositories that were
authored **without this tool in mind** (pinned commits, recorded in
`benchmarks/corpus/tier1.json`). Of the telemetry-bearing repositories that
actually record failures, **half cannot answer the most basic incident question —
"which request/trace did this failure belong to?"** — because the failure events
carry no correlation id.

This is a *small, demonstrative* corpus (a handful of subjects), and we report it
honestly as such: the point is the method, which scales to any corpus you point
it at. The exact numbers are not hand-picked — they fall out of a deterministic
pipeline.

### Reproduce it yourself

```bash
# one-time: enable network corpus cloning
export TELEMETRY_CONTRACTS_NETWORK_TESTS=1

# regenerate the headline statistic and full per-repo dataset
python3 -m telemetry_contracts.cli mine-corpus \
  --manifest benchmarks/corpus/tier1.json \
  --format markdown
```

The `headline` block reports `cannot_answer` / `denominator` over the
failure-bearing, telemetry-bearing subjects, with an explicit definition of the
denominator and the conservative, finding-based correlation check it uses. Every
number in the study is a pure function of the pinned commits — run it twice and
the bytes match.

## A 10-second demo

Point it at a real repo:

```
$ telemetry-contracts scan-repo --repo almbayedahmad/medflux
Scanned …: 5 telemetry file(s), 61 event(s), 4 finding(s) (0 error, 4 warning).
  WARNING telemetry.correlation_missing   — a failure log with no trace/request id
  WARNING telemetry.sensitive_unclassified — a raw tenant id emitted without classification
```

That's a real repository, found with no configuration. Or
[try it in your browser](../playground.md) — the same engine runs client-side via
Pyodide; nothing you paste is uploaded.

## Why this is research, not just a linter

- A **formal model** (`docs/formal_model.md`): each guarantee is tied to code and
  a test, annotated with its approximation direction, and discharged by an
  executable witness.
- **Baselines** (`docs/evaluation/baselines.md`): the tool is compared against
  rule-light, semantic-convention-only, and an offline LLM-surrogate baseline
  through the *same* gold-set pipeline, with a paired McNemar test.
- **Ground truth** (`docs/evaluation/ground_truth.md`): precision/recall on a
  labeled set.
- **Determinism everywhere**: SARIF, badges, the browser report, and the corpus
  study are all byte-reproducible.

## Try it

```bash
# Install from GitHub (not yet on PyPI)
pip install "git+https://github.com/thehalleyyoung/telemetry-contract-semantics.git"
telemetry-contracts scan-repo --repo <owner>/<name>
```

If it finds a real gap in your telemetry, that's a bug you can fix before the
next incident — which is the whole point.
