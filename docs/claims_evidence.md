# Claims and evidence

## What was achieved

- Added a benchmark CLI that runs one or more telemetry contracts against JSONL event corpora and optional diagnosability scenarios.
- Added JSON and Markdown benchmark reports with contract, event, finding, finding-by-code, finding-by-severity, label precision/recall, runtime, and pass/fail metrics.
- Added a reconstructed public historical case study for the GitLab.com 2017 database outage with source citations, fixture metadata, expected findings, and tests.

## Bounded novelty claim

We are not aware of an existing open-source benchmark that turns public incident postmortems into executable telemetry diagnosability contracts with reproducing tests. This is a bounded claim about this repository and this public-fixture workflow, not proof that no comparable private or unpublished system exists.

## What is not proven

- The GitLab fixture is reconstructed from public facts, not original production telemetry.
- The contracts do not prove an incident would have been prevented.
- The benchmark does not establish recall over all possible observability failures.
- Static checks are literal checks, not full semantic instrumentation analysis.

## Reproducibility protocol

```bash
python3 -m pytest
python3 -m telemetry_contracts.cli benchmark --config benchmarks/builtin.json --format json
python3 -m telemetry_contracts.cli benchmark --config benchmarks/builtin.json --format markdown
python3 -m telemetry_contracts.cli validate \
  --contract case_studies/gitlab_2017_database_outage/contract.json \
  --events case_studies/gitlab_2017_database_outage/reconstructed_events.jsonl \
  --format json --fail-on never
```

The benchmark passes when all expected labels in `case_studies/gitlab_2017_database_outage/metadata.json` match the produced findings and no extra findings appear.
