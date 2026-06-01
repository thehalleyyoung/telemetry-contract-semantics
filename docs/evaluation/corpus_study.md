# Corpus mining study

The corpus study turns the deterministic per-repository engine into a
reproducible, corpus-scale measurement of observability quality across
repositories that were authored without this tool in mind.

## Inputs: a frozen, pinned-commit corpus

A corpus is a small JSON manifest (`telemetry-contracts/corpus@1`) that pins each
subject to an exact commit SHA and records the selection protocol and each
subject's license:

```json
{
  "schema": "telemetry-contracts/corpus@1",
  "selection_protocol": {
    "description": "...",
    "criteria": ["public repo", "ships parseable telemetry", "authored independently"],
    "exclusions": ["forks", "archived", "auth-required"]
  },
  "subjects": [
    {"target": "owner/repo", "sha": "<40-hex>", "host": "github",
     "license": "MIT", "rationale": "ships JSONL logs", "tier": 1}
  ]
}
```

`target` accepts the same shorthand as `scan-repo` (`owner/repo`,
`<host>/owner/repo`, `gh:`/`gl:`/`bb:` prefixes, or a full URL). Subjects are
pinned by full SHA and fetched with a depth-1 fetch of that exact object, so the
study never depends on a moving default branch.

A small, multi-host tier-1 corpus is bundled at
[`benchmarks/corpus/tier1.json`](../../benchmarks/corpus/tier1.json). Larger
tiers can be appended without changing the schema; mine a fast subset with
`--tier N`.

## Running

```bash
# Markdown report:
python3 -m telemetry_contracts.cli mine-corpus --manifest benchmarks/corpus/tier1.json --format markdown

# Full JSON dataset (for tables/plots) plus a saved copy:
python3 -m telemetry_contracts.cli mine-corpus --manifest benchmarks/corpus/tier1.json \
  --format json --dataset-output reports/corpus_dataset.json
```

Each subject is cloned into a fresh temporary directory that is removed
immediately after scanning, so disk usage stays bounded regardless of corpus
size. A subject that fails to clone or scan is recorded under `errors` and the
study continues rather than aborting.

## Output: the study dataset

The dataset (`telemetry-contracts/corpus-dataset@1`) contains:

- `headline` — the share of telemetry-bearing repositories **that exhibit at
  least one failure event** which cannot be joined to a recognized
  request/trace identifier from telemetry alone (cannot answer _"why did this
  request fail?"_). Reported over two explicit denominators: the **primary**
  `cannot_answer_permille` uses the stricter *failure-bearing* denominator
  (repos with `failure_events > 0`, since a repo with no observed failures
  vacuously "can answer"), while `share_of_telemetry_permille` uses the broader
  *telemetry-bearing* denominator for context. The headline carries an explicit
  `definition` and `denominator_basis`.
- `bug_class_prevalence` — per bug class: how many repositories exhibit it, the
  permille, the total findings, and a per-host breakdown.
- `score_distribution` — min / p25 / median / p75 / max (nearest-rank) and a
  fixed-point mean of the diagnosability score over telemetry-bearing subjects.
- `subjects` — one flat, sorted row per subject (host, license, event count,
  formats, services, score, verdict, per-bug-class counts).

The analytic core is byte-reproducible: every collection is sorted and every
number is an integer or fixed-point value, so the same corpus yields an
identical dataset on any machine.

## Determinism and honesty

- The headline statistic uses the conservative, finding-based correlation check,
  so its count can never exceed the per-class prevalence it is drawn from, and
  it is reported over the stricter failure-bearing denominator so repositories
  with no observed failures cannot inflate it.
- Per-bug-class `findings` counts are **lower bounds**: the per-file scan caps
  the number of retained examples per finding code, so a repository's true
  finding total may be higher. The boolean *presence* of a bug class (and hence
  prevalence and the headline) is unaffected by this cap.
- The diagnosability score and the finding-based bug-class presence are computed
  over the **same** set of telemetry files (identical `max_files` /
  `max_file_bytes` discovery bounds), so the score and presence are always
  internally consistent for a subject.
- Scores and prevalence are computed over the sampled telemetry a repository
  actually ships; a clean result reflects the sample, not a proof of full
  coverage (see the per-class incompleteness statements).
- No wall-clock time or randomness enters the dataset.

## Limitations

- The corpus is a curated sample; prevalence figures describe the sampled
  repositories, not all software. Selection criteria are recorded in the
  manifest so the sample is inspectable.
- Detection inherits the per-bug-class incompleteness: gaps expressed only
  through unrecognised field names or unstructured text are not credited, and
  failure classification is heuristic.
- Licenses are recorded per subject; only derived metrics and findings are
  retained, never copied source.
