# Contributing

Thanks for your interest! The highest-leverage way to help is to make the
empirical claims stronger and broader. Two contribution types are especially
welcome and make great **good first issues**:

## 1. Add a corpus subject

The corpus study (`docs/evaluation/corpus_study.md`) runs the engine over real,
public repositories that were authored *without this tool in mind*. More subjects
= a stronger, more representative headline statistic.

To add one, append an entry to `benchmarks/corpus/tier1.json` (or a higher tier):

```json
{
  "target": "owner/repo",                 // or gl:group/repo, bb:owner/repo, or a full clone URL
  "sha": "<exact commit SHA>",            // pin it so the study is replayable byte-for-byte
  "host": "github",                       // github | gitlab | bitbucket
  "license": "MIT",
  "rationale": "ships JSONL request logs under logs/",
  "tier": 1
}
```

Selection rules (see the manifest's `selection_protocol`): public, not a fork,
not archived, clonable without auth, and it must **ship at least one parseable
telemetry/log file** in a recognized format (JSON lines, a JSON array, logfmt, or
an OTLP JSON export). Pick a project that adopted *no* convention from this tool.

Verify your addition (requires network):

```bash
export TELEMETRY_CONTRACTS_NETWORK_TESTS=1
python3 -m telemetry_contracts.cli mine-corpus --manifest benchmarks/corpus/tier1.json --format markdown
python3 -m pytest tests/ -k real -o addopts=""   # the >=4-real-repo network tests
```

## 2. Add or refine a gold label

The ground-truth benchmark (`docs/evaluation/ground_truth.md`) measures
precision/recall against labeled examples. Adding a carefully labeled
`(events, expected bug class)` case — especially a tricky true/false positive —
directly improves the evaluation. Keep labels conservative and document the
reasoning in the fixture.

## Ground rules for any change

This project values **determinism and honesty** above features:

- **Pure standard library + the git CLI.** No third-party runtime dependencies.
- **Byte-deterministic output.** No wall-clock, no RNG, no unsorted iteration in
  anything that lands in an artifact. Sort, use `Counter`, use fixed-point math.
- **No network in unit tests.** Real-repo tests are gated behind
  `TELEMETRY_CONTRACTS_NETWORK_TESTS=1` and live in `tests/*_real.py`.
- **Claims must cite evidence.** If you add a capability, add a claim in
  `telemetry_contracts/claims.py` pointing at real artifacts and tests, then
  regenerate the matrix:
  `python3 -m telemetry_contracts.cli claims-matrix --output docs/claims_evidence_matrix.json`.

## Running the tests

```bash
# offline suite (what CI runs by default)
python3 -m pytest --deselect tests/test_packaging.py::test_wheel_and_editable_console_script_smoke -p no:benchmark

# real-repo / network suite
TELEMETRY_CONTRACTS_NETWORK_TESTS=1 python3 -m pytest tests/ -k real -o addopts=""
```

All tests should be green before you open a PR.
