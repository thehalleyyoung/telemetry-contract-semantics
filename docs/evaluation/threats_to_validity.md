# Threats to validity

We follow the standard internal / external / construct / conclusion taxonomy.
Each threat is paired with the mitigation actually present in the artifact.

## Internal validity

*Are the measured effects caused by what we claim?*

- **Gold-label bias.** The curated gold set
  (`benchmarks/ground_truth/curated.jsonl`) could be unconsciously tuned to the
  tool. **Mitigation:** the gold set is frozen before evaluation; every method —
  the tool and all three baselines — is scored through the *same*
  `score_gold_set` pipeline and sees only `(events, bug_class)`, never the label.
  No per-example tuning is performed after the snapshot.
- **Determinism masking real variance.** Byte-deterministic output could hide
  genuine sensitivity to inputs. **Mitigation:** determinism is a *property of the
  analysis*, not of the inputs — the same analysis is re-run across many distinct
  real repositories in the network suite, which exercises input variance directly.
- **Stale committed artifacts.** A checked-in report could drift from the code
  that produces it. **Mitigation:** the determinism manifest
  (`reports/reproduce_manifest.json`) plus the `determinism` CI workflow
  regenerate and diff every portable artifact on each push; drift fails the build.

## External validity

*Do the results generalize beyond our benchmark?*

- **Benchmark representativeness.** The built-in benchmark and case studies are a
  finite, curated set. **Mitigation:** the tool is evaluated on ≥4 independent
  public repositories that were authored without this tool in mind, via the
  network test suites (`tests/*_real.py`) and the corpus-mining study
  (`mine-corpus`). The tool runs on *any* repository, not only the benchmark.
- **Format coverage.** Real telemetry appears in many encodings. **Mitigation:**
  format-agnostic adapters (JSONL, JSON arrays, logfmt, OTLP) with a tolerant mode
  that skips unparseable lines; new formats plug in through a single adapter
  interface.
- **Reconstructed incidents.** Some case studies (e.g. the GitLab 2017 outage)
  use *reconstructed* event traces, not captured production telemetry.
  **Mitigation:** reconstructed cases are explicitly labelled as such and are used
  to demonstrate the analysis on a known failure shape, never presented as
  captured ground truth. Empirical headline numbers are sourced from the live
  corpus study over real repositories.

## Construct validity

*Do our metrics measure the intended concept?*

- **"Observability is a correctness property."** We operationalize this as
  detectable, classifiable instrumentation gaps with precision/recall against a
  gold set, rather than a subjective notion of "good telemetry." Limitations of
  each detector are recorded per claim in `docs/claims_evidence_matrix.json`.
- **Findings ≠ harm.** A reported gap is a *potential* observability defect; we do
  not claim every finding caused an incident. The corpus study reports the
  narrower, falsifiable construct "can this repo answer *why did this fail?*".
- **Synthesized fixes are evidence, not ground truth.** Generated instrumentation
  snippets are AST/compile-validated and, when proved, run in a hardened isolated
  subprocess for evidence only; they are never scored as repository findings and
  the tool never edits the target repository.

## Conclusion validity

*Are the statistical conclusions sound?*

- **Significance of tool-vs-baseline gaps.** **Mitigation:** comparisons use an
  exact two-sided paired **McNemar** test over the shared gold set, reported
  alongside per-class and macro/micro precision/recall/F1, so wins are not
  attributable to label imbalance or a single class.
- **Baseline honesty.** The "LLM" baseline ships a *transparent, hand-written
  recorded surrogate*, explicitly labelled recorded-surrogate and **not** an LLM
  accuracy claim, to avoid overstating a comparison we cannot reproduce offline.
- **Multiple comparisons.** Headline numbers are few and pre-registered in the
  frozen artifacts; we avoid fishing by regenerating the *complete* set of
  reported numbers from a single command rather than selecting favourable runs.
