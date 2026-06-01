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
[`benchmarks/corpus/tier1.json`](../../benchmarks/corpus/tier1.json), and the
full curated corpus — 50+ verified subjects across multiple hosts, tiered so the
tier-1 subset stays fast — lives at
[`benchmarks/corpus/corpus.json`](../../benchmarks/corpus/corpus.json). Larger
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

## Scaling up: persistent checkouts, caching, and a resumable runner

`mine-corpus` clones each subject into a disposable temporary directory — ideal
for a small, one-shot run. For larger corpora that you re-run as the engine
evolves, a second toolchain keeps work persistent, content-addressed, and
crash-safe.

### Download the corpus once (gitignored)

The checkouts themselves are never committed. A user-facing helper clones every
pinned subject into a gitignored directory and verifies that each working tree is
parked at exactly the manifest SHA:

```bash
# Clones into benchmarks/corpus/_repos/ (gitignored) and verifies HEAD == sha:
scripts/download_corpus.sh --manifest benchmarks/corpus/tier1.json

# Or via the CLI directly, with an explicit destination and tier filter:
python3 -m telemetry_contracts.cli corpus-download \
  --manifest benchmarks/corpus/tier1.json --tier 1 \
  --repos-dir benchmarks/corpus/_repos
```

Downloading is idempotent: a subject whose checkout already sits at the pinned
SHA is skipped, so re-running only fetches what is missing. `corpus-verify`
re-checks every subject without modifying anything:

```bash
python3 -m telemetry_contracts.cli corpus-verify --manifest benchmarks/corpus/tier1.json
```

### Run with a content-addressed cache

`corpus-run` reuses the persistent checkouts and caches **analysis-derived facts**
keyed by `(subject SHA, engine fingerprint, scan options, cache schema)`. A run
recomputes a subject only when its commit, the engine source, or the scan options
change; otherwise it replays the cached facts. Manifest metadata (license, tier,
rationale) is merged at aggregation time, so a cache entry is reusable across any
manifest that pins the same commit.

```bash
python3 -m telemetry_contracts.cli corpus-run \
  --manifest benchmarks/corpus/tier1.json \
  --repos-dir benchmarks/corpus/_repos \
  --cache-dir benchmarks/corpus/.cache \
  --format markdown
```

The cache directory also holds a `status.json` progress table written atomically
after each subject, so an interrupted run resumes from where it stopped: cached
subjects are skipped instantly and only unfinished work is recomputed. Both the
cache and status directories are gitignored.

The engine fingerprint is fail-closed — it hashes every Python source file in the
package, so any change to analysis code invalidates the cache rather than risking
a stale result. Fresh and cached datasets are byte-identical because both paths
run the *same* analysis function.

## Correlation breakdowns and plots

`corpus-run` can slice the dataset and emit deterministic, dependency-free SVG
charts:

```bash
# Bug-class prevalence and headline broken down by language, instrumentation
# library, and event-volume bucket:
python3 -m telemetry_contracts.cli corpus-run \
  --manifest benchmarks/corpus/tier1.json --format correlation

# Standalone-stdlib SVG plots (score histogram + bug-class prevalence):
python3 -m telemetry_contracts.cli corpus-run \
  --manifest benchmarks/corpus/tier1.json --format plots \
  --plots-dir reports/corpus_plots
```

Each subject row is annotated with detected **characteristics** — primary
language (from file-extension counts) and whether a known instrumentation library
(OpenTelemetry, structured-logging frameworks, etc.) appears in a dependency
manifest. The correlation view groups the headline and per-class prevalence by
those characteristics so you can see, e.g., whether repositories that already
depend on a tracing library are less likely to ship uncorrelated failures. The
SVGs use integer geometry and XML-escaped text only, so they are byte-identical
across machines.

## Growing the corpus honestly

`corpus-discover` proposes candidate repositories (popular projects by language,
optionally including GitLab) as a **review seed only** — it is never run inside
the test suite and never auto-adds subjects:

```bash
python3 -m telemetry_contracts.cli corpus-discover \
  --language Python --language Go --min-stars 200 --output corpus_seed.json
```

Every proposed candidate must be manually verified to actually ship parseable
telemetry and then pinned to an exact SHA (via `corpus-verify`) before it earns a
place in a manifest. Subjects are added only when they genuinely clone and verify;
the manifest is the single source of truth and never contains an unverified
commit.

### Curating a new tier end to end

`corpus-curate` automates that honest path: it clones each candidate into a
gitignored directory, reads the **real** commit SHA at `HEAD` (never a fabricated
one), scans the checkout, and writes a manifest containing only the subjects that
genuinely clone and ship parseable telemetry. The bundled
[`scripts/curate_corpus.sh`](../../scripts/curate_corpus.sh) chains discovery and
curation into one reproducible command:

```bash
# Discover telemetry-bearing candidates and curate a verified tier into a manifest:
scripts/curate_corpus.sh --output benchmarks/corpus/tier2.json --limit 50

# Or curate from a candidate list you already reviewed:
python3 -m telemetry_contracts.cli corpus-curate \
  --candidates corpus_candidates.json \
  --work-dir benchmarks/corpus/_curate \
  --output benchmarks/corpus/tier2.json --tier 2 --limit 50
```

The cloned repositories stay under a gitignored work directory and are never
committed — only the small JSON manifest is. Because each SHA is read from an
actual checkout, the resulting corpus is replayable byte-for-byte and contains no
invented commits. Re-running the curation tooling against more candidates is how
the corpus grows toward larger tiers.



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
