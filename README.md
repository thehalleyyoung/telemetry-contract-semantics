# Telemetry Contracts

**Point it at the telemetry you already have and get value in one command — no contract to write first, no relabeling, no semantic-convention adoption required.**

Most observability tooling only pays off *later*, after you adopt a prescribed
instrumentation discipline. Telemetry Contracts is useful *right now* with the
logs, traces, and metrics you already emit — whatever their shape.

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

# An arbitrary GitHub project: shallow-clones it and scans whatever it ships.
python3 -m telemetry_contracts.cli scan-repo --repo owner/name --format markdown
```

`--repo` accepts `owner/name` shorthand or a full https/git URL, and `--ref`
selects a branch or tag. Both commands accept `--service`, `--fail-on
error|warning|never`, `--output`, `--format text|json|markdown`, and `--deep`
(see below). Output leads with a per-type rollup (most severe first) and
copy-pasteable next steps, and each finding is tagged with the file it came
from. Cloning uses `git clone --depth 1`; discovery is a pruned, bounded walk.

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
`normalize_events`, `scan_directory`, `scan_repo`, `load_contract`, `load_jsonl`,
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
