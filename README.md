# Telemetry Contracts

**Point it at the telemetry you already have and get value in one command — no contract to write first, no relabeling, no semantic-convention adoption required.**

Most observability tooling only pays off *later*, after you adopt a prescribed
instrumentation discipline. Telemetry Contracts is useful *right now* with the
logs, traces, and metrics you already emit — whatever their shape.

Its premise is that **observability is a correctness property**:
under-instrumentation (a failure you can't trace, an error with no cause, a span
with no duration, a secret in a log) is a *detectable bug class*, not a matter of
taste. Each bug class has a precise, testable definition and an explicit
statement of what a finding does and does not guarantee.

## Quickstart: use the data you already have

```bash
# 1. Find privacy & diagnosability gaps in existing data (zero config).
python3 -m telemetry_contracts.cli analyze --events your-logs.jsonl

# 2. Turn that data into a starter contract you can edit, instead of writing one by hand.
python3 -m telemetry_contracts.cli infer-contract --events your-logs.jsonl --service checkout > telemetry-contract.json

# 3. (Level up) Enforce the contract in CI — still against your existing data.
python3 -m telemetry_contracts.cli validate --contract telemetry-contract.json --events your-logs.jsonl --events-format auto
```

`analyze` and `infer-contract` accept the shapes teams actually have: arbitrary
JSON/JSONL log lines (Python `logging`, logrus, zap, pino, winston), a single
JSON array, logfmt (`key=value`) lines, Datadog-style `dd.trace_id` fields, the
native JSONL shape, and OTLP collector exports. Field aliases
(`level`/`severity`, `msg`/`message`, `service.name`, `traceId`, `@timestamp`, …)
are mapped automatically, the signal kind is inferred with a confidence score,
and unknown keys are preserved — nothing is silently dropped.

### What `analyze` finds with no contract

- Raw secrets/PII in telemetry (emails, bearer tokens, JWTs, password assignments, card/phone values in card/phone-named fields).
- Unclassified sensitive or tenant/customer/account identifier fields.
- Failure events with no correlation id (`trace_id`/`request_id`).
- Failure events with no error code, exception, or status evidence.
- Metric labels with likely-unbounded cardinality (sample-size gated).

Findings reuse the same taxonomy codes, SARIF export, and CI gating as the rest
of the tool, so you can wire `analyze` straight into code scanning today and
adopt contracts later for stronger guarantees.

## Scan any project or GitHub repo

Run the same contract-free checks across every telemetry/log file a project
ships — in whatever format — with no setup:

```bash
# A local project: scan the current directory (default) — discovers and
# analyzes telemetry files, skipping configs, lockfiles, and vendored dirs.
python3 -m telemetry_contracts.cli scan --format markdown

# Or point it at a specific folder.
python3 -m telemetry_contracts.cli scan --path ./my-service --format markdown

# An arbitrary project on any host: shallow-clones it and scans whatever it ships.
python3 -m telemetry_contracts.cli scan-repo --repo owner/name --format markdown
python3 -m telemetry_contracts.cli scan-repo --repo gl:group/project --format markdown
```

`--repo` accepts `owner/name` shorthand (defaults to GitHub),
`<host>/owner/name` for `gitlab.com`/`bitbucket.org`/`codeberg.org`, the
`gh:`/`gl:`/`bb:` host prefixes, or a full https/git URL; `--ref`
selects a branch or tag. Both commands accept `--service`, `--fail-on
error|warning|never`, `--output`, `--format text|json|markdown`, and `--deep`
(see below). Output leads with a per-type rollup (most severe first) and
copy-pasteable next steps, and each finding is tagged with the file it came
from. Cloning uses `git clone --depth 1`; discovery is a pruned, bounded walk.

### Study many repositories at once

To measure observability across a whole set of pre-existing repositories, point
`mine-corpus` at a pinned-commit corpus manifest. It clones each subject at its
exact commit SHA, scans it, and reduces the results to one deterministic dataset
and report — including the headline statistic *"what share of repositories
cannot answer 'why did this request fail?'"*:

```bash
python3 -m telemetry_contracts.cli mine-corpus --manifest benchmarks/corpus/tier1.json --format markdown
```

See [`docs/evaluation/`](docs/evaluation/) for the study design, the dataset
schema, and the soundness/incompleteness of each bug class.

Try the zero-config and scan commands against bundled fixtures:

```bash
cd telemetry-contracts-repo
python3 -m telemetry_contracts.cli analyze --events tests/fixtures/byod/app_logs.jsonl --format markdown
python3 -m telemetry_contracts.cli scan --path examples/otlp --format markdown
```

## Infer execution semantics from existing data

You don't have to write a contract to get the formal layer. `infer-semantics`
takes raw telemetry, infers a draft contract, and runs the small-step semantics
evaluator over it — producing a formal derivation, an observed event-structure
(happens-before) model, and an inferred execution order discovered from your
correlation IDs:

```bash
python3 -m telemetry_contracts.cli infer-semantics --events your-logs.jsonl --format markdown
```

The execution order is inferred conservatively: an `a → b` edge is kept only
when, in every correlation group containing both signals (and in at least two
such groups), `a` strictly precedes `b`. The result is emitted as a reviewable
`temporal_sequences` entry marked `required: false` — a candidate to promote
once you trust it, never an auto-enforced check. Add `--deep` to `scan` /
`scan-repo` to run this per service across a whole project, plus an
informational runtime-name vs source-literal alignment:

```bash
python3 -m telemetry_contracts.cli scan --deep --format markdown
python3 -m telemetry_contracts.cli scan-repo --repo owner/name --deep --format markdown
```

## Characterize, diagnose, and improve an existing repo

Three commands turn the analysis into an iterative workflow on a repo you did
not instrument yourself — no contract and no prescribed labeling required.

`characterize` inventories what telemetry a project already ships and which
instrumentation libraries it uses (detected from its source), straight from a
local checkout or a GitHub clone:

```bash
python3 -m telemetry_contracts.cli characterize --path .
```

`diagnose` scores how answerable common incident questions are with the data you
already emit ("which request failed?", "what was the error?", "how long did it
take?", "are we leaking sensitive values?"), and names the concrete gaps:

```bash
python3 -m telemetry_contracts.cli diagnose --path .
python3 -m telemetry_contracts.cli diagnose --events your-logs.jsonl --fail-under 80
```

`pipeline` runs the full staged loop end to end: characterize the repo →
first-pass analysis → diagnose incident-readiness → produce a high-impact,
LLM-fillable instrumentation plan (privacy-sensitive changes are held back for
review, never auto-applied) → apply the missing fields → re-analyze
differentially → repeat until the marginal impact converges. It works on a local
path or clones a GitHub repo directly:

```bash
python3 -m telemetry_contracts.cli pipeline --path .
python3 -m telemetry_contracts.cli pipeline --repo owner/name
```

Every round keeps an impact ledger (predicted vs. realized diagnosability gain)
so you can see whether each change actually paid off on your real data. Each
proposed change is scored by a written [high-impact filter](docs/high_impact_filter.md)
(analytic signal gained ÷ added surface area) and ships with a reviewable
companion patch generated against the exact cloned commit and verified with
`git apply --check`. Analysis deepens progressively across rounds — correlation →
ordering → temporal → privacy — as the data actually gets richer. Add
`--out-dir DIR` to persist every stage as a SHA-keyed, provenance-carrying
artifact; `--format sarif` for a CI-ready differential; and
`--fail-on-regression` to exit non-zero if any round would regress safety. See
[`docs/staged_pipeline.md`](docs/staged_pipeline.md) for a worked example.

## Optional: observability as a correctness property

A service is not merely correct when it returns the right response; for
production systems it should also emit the traces, metrics, logs, fields, and
retention/sampling assumptions needed to diagnose failures later. The optional
contract layer turns that thesis into executable checks: runtime validation,
static source analysis, semantic-convention linting, temporal/hyperproperty
checks, strict closed-world validation, refinement/composition, incident-
readiness scoring, OTLP import/analysis, benchmarking, SARIF + CI gating, and a
machine-readable finding taxonomy. See the docs below for the full surface.

### Contract enforcement quickstart

Requirements: Python 3.10+. The package uses only the standard library; tests
use `pytest`. Contracts are JSON (YAML accepted when `PyYAML` is installed).

```bash
python3 -m telemetry_contracts.cli validate \
  --contract examples/contracts/checkout.contract.json \
  --events examples/telemetry/passing.jsonl

python3 -m telemetry_contracts.cli static \
  --contract examples/contracts/checkout.contract.json examples/services

python3 -m telemetry_contracts.cli lint-contract \
  --contract examples/contracts/checkout.contract.json
```

A contract declares a service plus expected telemetry signals (spans, metrics,
logs) with required fields, types, allowed values, regex/forbidden patterns,
privacy classifications, numeric ranges/units, correlation policies, temporal
sequences/properties, conditional requirements, and more. See
`docs/contract.schema.json` for the full schema and `docs/report_schemas/` for
output envelopes.

### Runtime event format

Runtime validation reads newline-delimited JSON; events are collector-neutral:

```json
{"kind":"span","service":"checkout","name":"payment.authorize","trace_id":"trace-123","timestamp_ms":1000,"attributes":{"tenant_id":"tenant-acme"}}
{"kind":"metric","service":"checkout","name":"payment.latency_ms","trace_id":"trace-123","timestamp_ms":1100,"value":812.7,"tags":{"payment_provider":"stripe"}}
{"kind":"log","service":"checkout","name":"checkout.payment_failed","trace_id":"trace-123","timestamp_ms":1200,"severity":"ERROR","message":"payment failed","fields":{"tenant_id":"tenant-acme"}}
```

Use `--format json` for machine-readable output or `--format sarif` for code
scanning. `analyze`/`infer-contract`/`validate --events-format auto` also accept
the flexible shapes above.

## Public Python API

The package ships `py.typed` and exports stable helpers from
`telemetry_contracts`: `analyze_events`, `infer_contract`,
`infer_execution_semantics`, `infer_temporal_order`, `load_events_auto`,
`normalize_events`, `scan_directory`, `scan_repo`, `characterize_repo`,
`diagnose`, `baseline`, `instrumentation_plan`, `generate_code_proposals`,
`differential`, `semantic_differential`, `run_pipeline`,
`score_addition`, `feature_scorecard`,
`write_pipeline_artifacts`, `load_contract`, `load_jsonl`,
`validate_events`, `check_sources`, `run_compiled_monitor`,
`generate_incident_readiness_report`, `generate_service_owner_report`,
`run_benchmark`, and `import_otlp`.

```python
from telemetry_contracts import load_contract, load_jsonl, validate_events

contract = load_contract("examples/contracts/checkout.contract.json")
events = load_jsonl("examples/telemetry/passing.jsonl")
findings = validate_events(contract, events)
assert not findings
```

## CI and code scanning

`examples/ci/` contains a GitHub Actions template, shell script, pre-commit
hook, sample report, and an owned/expiring baseline:

```bash
python3 -m telemetry_contracts.cli validate --contract service.contract.json --events telemetry.jsonl --format sarif > telemetry-contracts.sarif
python3 -m telemetry_contracts.cli static --contract service.contract.json src --format json > telemetry-contracts.static.json
python3 -m telemetry_contracts.cli ci-gate --findings telemetry-contracts.static.json --baseline examples/ci/baseline.example.json --fail-on error
```

Baselines match exact `code`/`path`/`contract_path`/`event_index`/`path_suffix`
keys with optional `owner`/`expires_at`/`justification`; expired entries fail.

## OTLP, benchmarks, and case studies

- **OTLP**: `import-otlp`, `export-otlp`, and `analyze-collector-export` convert
  and inspect OpenTelemetry collector JSON/JSONL exports; see
  `examples/otlp/` and `docs/collector_file_exporter.md`.
- **Benchmarks**: `python3 -m telemetry_contracts.cli benchmark --config benchmarks/builtin.json`
  runs built-in or user corpora with label precision/recall and diff reports.
- **Case studies**: `case_studies/gitlab_2017_database_outage/` (reconstructed
  GitLab 2017 outage) and `case_studies/current/owasp_securetea_signin/`
  (public OWASP SecureTea sign-in code) demonstrate the checks on
  public-incident-derived and public-code data. Reconstructed values are
  synthetic placeholders, not private operational data.

## Docs

- `docs/operational_scorecards.md` — workload scorecards, privacy-safe examples, anti-patterns, CI/SARIF integration, OTLP limits.
- `docs/staged_pipeline.md` — the characterize → diagnose → plan → apply → differential loop, with a worked example on a public repo and every intermediate artifact.
- `docs/high_impact_filter.md` — the written rubric (analytic signal ÷ surface area) used to score every proposed change and re-score applied changes after the fact.
- `docs/tutorials/` — fixing a broken service; mapping SLO debugging questions to contract clauses.
- `docs/report_schemas.md` + `docs/report_schemas/*.schema.json` — JSON output envelopes.
- `docs/replication_guide.md` — exact commands to reproduce benchmark metrics and reports.
- `docs/finding_taxonomy.json` / `claims-matrix` — the finding-rule catalog and a claims-to-evidence matrix.

## Limitations

The prototype is intentionally non-AI: contracts are explicit files, telemetry
is concrete JSONL, and pass/fail comes from deterministic validators. No model
call is required to run or trust the checks. Static analysis uses Python AST
plus lightweight heuristics for JS/TS/Go/Java/C#/Ruby/Rust (not a full
interprocedural compiler). Semantic-convention linting, OTLP support,
cardinality, temporal/hyperproperty/strict checks, refinement/composition, and
incident-readiness scoring are all bounded to the supplied finite artifacts and
documented subsets — useful for CI and review, not universal proofs. See the
per-feature notes in `docs/release_checklist.md`.

## Development

```bash
python3 -m pytest
make smoke
```

Optional YAML support:

```bash
python3 -m pip install '.[yaml]'
```
