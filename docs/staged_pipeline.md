# The staged pipeline: from "data you already have" to diagnosability

This is a worked example of running the staged improvement loop end to end on a
**real public repository the project did not author**, with every intermediate
artifact written to disk and reproducible from the inputs.

The loop has seven stages:

1. **Characterize** — inventory the telemetry and instrumentation libraries a
   repo already ships (from its data and its source imports).
2. **Diagnose** — score how answerable common incident questions are, and name
   the exact missing field behind each gap.
3. **Baseline** — anchor an inferred-execution-semantics snapshot (proof
   obligations discharged/outstanding, candidate ordering with auditable
   support, candidate concurrency risks).
4. **Plan** — rank high-impact, additive instrumentation changes; privacy
   changes are held back for human review, never auto-generated.
5. **Apply (offline)** — deterministically synthesize the telemetry the planned
   changes *would* produce, and emit standalone, validated code proposals.
6. **Differential** — diff before vs. after (score, findings, answerable
   questions, semantics) and detect regressions.
7. **Iterate** — repeat to convergence, gating each round for safety.

## One command

```bash
python3 -m telemetry_contracts.cli pipeline \
  --repo Vannut97/web-refinery \
  --out-dir ./pipeline-artifacts
```

Or, on a checkout you already have:

```bash
python3 -m telemetry_contracts.cli pipeline --path . --out-dir ./pipeline-artifacts
```

## What the run reports

On `Vannut97/web-refinery` the loop characterizes an HTTP API, diagnoses it as
`under-instrumented for incidents` at a baseline diagnosability score of
**87/100**, plans the single highest-leverage additive change (propagate a
`trace_id`/`request_id` onto the failing signal), applies it offline, and
re-scores to **100/100** in one round — `1 question newly answerable, 0
regressions` — before stopping because no further safety-approved high-impact
change remains.

## Intermediate artifacts

With `--out-dir`, every stage is persisted under a directory keyed to the
acquisition commit SHA. Each artifact wraps its payload in a provenance block
(source commit, stage, generator, pipeline options, and a content hash of the
canonical bytes), so a run is fully reconstructable and auditable:

```
pipeline-artifacts/<commit-sha>/
  index.json                              # manifest of every artifact + content hash
  characterization.json                   # stage 1
  baseline.json                           # stage 3 (proof obligations, ordering evidence)
  rounds/round-001/
    plan.json                             # stage 4 (ranked additive changes + prompt packs)
    code-proposals.json                   # stage 5 (validated standalone snippets)
    application-manifest.json             # what was accepted / deferred / quarantined
    differential.json                     # stage 6 (score + findings + questions delta)
  differential-overall.json               # before vs. final
  impact_ledger.json                      # predicted vs. realized gain per round
  pipeline.json                           # the whole run
```

The artifacts are byte-stable: re-running on the same commit produces identical
content hashes across machines (no wall-clock timestamps are recorded).

## Code proposals are proposals, not edits

For each non-privacy gap the run emits a standalone instrumentation **proposal**
in `code-proposals.json`, using the repo's detected library. Every proposal is
parsed (`ast.parse`), compiled (`compile`), and run through the project's own
static source extractor to confirm it actually introduces the intended runtime
name (e.g. `trace_id`). Proposals carry `applied_to_repo: false` and
`target_repo_build_not_run: true`: they are reviewable helper sketches, and
adopting them into production code remains a human step. The repository is never
modified.

## Safety never regresses

Each round is applied to a *candidate* copy and gated before it advances the
loop. A round whose differential introduces a new finding, drops the score, or
makes a question newly unanswerable is **quarantined and rolled back**: its
gaps are excluded from later rounds (so the loop still terminates), it
contributes zero realized impact to the ledger, and `regressed` is set. A
CI-ready differential is available with `--format sarif` (rule namespace
`pipeline.diff.*`), and `--fail-on-regression` makes the command exit non-zero.

## Reproducing the numbers

Every number above is a claim reproducible from checked-in inputs by the
documented command. The capability is mapped to its tests and real-repo
demonstration in [`claims_evidence_matrix.json`](claims_evidence_matrix.json)
under the `staged-pipeline-existing-repos` claim. Offline unit tests
(`tests/test_pipeline.py`, `tests/test_pipeline_artifacts.py`) enforce
determinism with local fixtures; network-gated integration tests
(`TELEMETRY_CONTRACTS_NETWORK_TESTS=1`) clone real GitHub repositories and assert
the artifacts and validated proposals on live data.
