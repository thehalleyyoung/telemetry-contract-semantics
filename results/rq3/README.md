# RQ3 corpus study: raw results

Corpus: `benchmarks/corpus/corpus.json` (59 pinned subjects; 58 cloned, 1 repository
deleted upstream: `Alvoradozerouno/STEURER-Framework`, see `download_report.json`).
Run on 2026-10-06, local machine, Python 3.14.7, engine at the commit that adds this file.

| File | Produced by |
| --- | --- |
| `download_report.json` | `python3 -m telemetry_contracts.cli corpus-download --manifest benchmarks/corpus/corpus.json --output results/rq3/download_report.json` |
| `corpus_dataset.json`, `study.md` | `python3 -m telemetry_contracts.cli corpus-run --manifest benchmarks/corpus/corpus.json --repos-dir benchmarks/corpus/_repos --format markdown --output results/rq3/study.md --dataset-output results/rq3/corpus_dataset.json` (8.5 min wall) |
| `findings.jsonl` | `python3 scripts/rq3_extract_findings.py` (all 2,269 bug-class findings with their source event) |
| `validation_sample.jsonl` | same script: stratified sample, 15 per bug class that fired, at most 2 per (repo, class) |
| `validation_labels.csv` | manual labels (see below) |
| `validation_summary.json` | `python3 scripts/rq3_validation_summary.py` |

## How the sample was validated

Each of the 60 sampled findings was checked by LLM-assisted inspection: the
coordinating agent (an LLM, not a human expert) read the flagged event in the
pinned checkout, the file path, and the bug-class definition in
`telemetry_contracts/bug_classes.py`, and recorded three labels with a one-line
rationale:

* `matches_definition` (yes / no / borderline): does the flagged event meet the
  written bug-class definition? `borderline` is used for `session_id` fields,
  which the detector treats as user-linkable identifiers but which are often
  agent or UI session ids.
* `artifact_kind`: `runtime-log` (a log or telemetry file the project itself
  wrote and committed), `sample-telemetry` (synthetic or example telemetry
  shipped as demo data), `test-fixture`, or `non-telemetry` (datasets, issue
  trackers, model outputs that the file-discovery heuristic picked up).
* `actionable_in_project_telemetry` (yes / no / unclear): would a maintainer
  plausibly treat this as an observability or privacy defect in telemetry the
  project emits?

There was one rater and no adjudication. A second, human rater is listed as
remaining work (`docs/evaluation/annotation/`).

## Headline (from `validation_summary.json`)

* Definition-level precision over the 60 findings: 35/60 = 0.583 strict,
  44/60 = 0.733 counting borderline as correct.
  * missing-correlation 13/15, missing-error-evidence 12/15,
    sensitive-values 9/15, unclassified-sensitive 1/15 strict (10/15 lenient).
* Only 21/60 sampled findings come from runtime logs the project wrote; 22 are
  synthetic/example telemetry, 5 test fixtures, 12 non-telemetry JSON.
* 7/60 were judged actionable defects in the project's own telemetry.

Recurring false-positive causes: correlation ids and exception types nested
inside an `mdc`/`throwable` object, the OTel `error.type` attribute not being
credited as error evidence, the password-assignment and bearer regexes firing
on prose, and the `token` name heuristic firing on token counts.

Finding counts are lower bounds: `analyze_events` keeps at most 25 example
findings per code per file.
