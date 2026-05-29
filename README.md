# Telemetry Contracts

Telemetry Contracts is a standalone prototype for testing **observability as a correctness property**. A service is not merely correct when it returns the right response; for production systems, it should also emit the traces, metrics, logs, fields, tags, and retention/sampling assumptions needed to diagnose failures later.

This repository turns that thesis into executable checks:

- Runtime validation of JSONL telemetry events against contracts.
- Static checks that source code contains expected OpenTelemetry-style span, metric, and log names.
- Diagnosability scenario checks that ask whether a concrete incident question can be answered from emitted telemetry.
- OTLP JSON import for testing real OpenTelemetry collector/exporter captures.
- A benchmark harness for built-in or user-provided contract/event corpora.
- A reconstructed public historical case study based on the GitLab.com 2017 database outage postmortem.
- Passing and failing examples for a checkout/payment service.

The prototype is intentionally non-AI runtime software. LLMs may help humans draft scenarios or contracts, but the validation path is deterministic Python code and test fixtures.

## Quickstart

Requirements: Python 3.10+. The package itself uses only the Python standard library. Tests use `pytest`.

```bash
cd telemetry-contracts-repo
python3 -m telemetry_contracts.cli validate \
  --contract examples/contracts/checkout.contract.json \
  --events examples/telemetry/passing.jsonl

python3 -m telemetry_contracts.cli validate \
  --contract examples/contracts/checkout.contract.json \
  --events examples/telemetry/failing.jsonl --format json

python3 -m telemetry_contracts.cli static \
  --contract examples/contracts/checkout.contract.json \
  examples/services

python3 -m telemetry_contracts.cli scenario \
  --contract examples/contracts/checkout.contract.json \
  --events examples/telemetry/passing.jsonl \
  --id payment-timeout

python3 -m telemetry_contracts.cli import-otlp \
  --input examples/real_world/otel_checkout_missing_tenant.otlp.json \
  --output checkout.otlp.jsonl

python3 -m telemetry_contracts.cli validate \
  --contract examples/real_world/otel_checkout_missing_tenant.contract.json \
  --events checkout.otlp.jsonl

python3 -m telemetry_contracts.cli benchmark \
  --config benchmarks/builtin.json \
  --format markdown
```

If installed as a package, the same CLI is available as `telemetry-contracts`.

## Contract language

Executable examples use JSON so the project runs without third-party YAML libraries. YAML files (`.yaml`/`.yml`) are accepted only when `PyYAML` is installed; otherwise the loader fails loudly with a clear error.

A contract declares a service plus expected telemetry signals:

```json
{
  "version": "1.0",
  "service": "checkout",
  "spans": [{
    "name": "payment.authorize",
    "required": true,
    "fields": {
      "tenant_id": {"type": "string", "required": true},
      "retry_count": {"type": "integer", "min": 0, "max": 3},
      "payment_provider": {"type": "string", "allowed_values": ["stripe", "adyen", "test"]}
    }
  }]
}
```

Supported checks include:

- Signal presence for spans, metrics, and logs.
- Required fields/tags/attributes.
- Primitive field types: string, integer, number, boolean, object, array, null.
- Allowed values.
- Regex patterns.
- Numeric `min`/`max` ranges.
- Metric `value` checks.
- Log severity and message pattern checks.
- Cardinality hints as warnings.
- Sampling and retention metadata as documented assumptions.

## Runtime event format

Runtime validation reads newline-delimited JSON. Events are intentionally simple and collector-neutral:

```json
{"kind":"span","service":"checkout","name":"payment.authorize","attributes":{"tenant_id":"tenant-acme","payment_provider":"stripe","retry_count":2}}
{"kind":"metric","service":"checkout","name":"payment.authorization.latency_ms","value":812.7,"tags":{"payment_provider":"stripe"}}
{"kind":"log","service":"checkout","name":"checkout.payment_failed","severity":"ERROR","message":"payment authorization failed","fields":{"tenant_id":"tenant-acme"}}
```

Findings include severity, code, message, event path, contract path, and details when useful. Use `--format json` for machine-readable output.

## Architecture

- `telemetry_contracts.loader` loads JSON/YAML contracts and JSONL events with explicit errors.
- `telemetry_contracts.validator` checks emitted telemetry against signal and field specifications.
- `telemetry_contracts.static_checker` scans source files for expected instrumentation literals.
- `telemetry_contracts.scenario` verifies incident-question requirements against emitted telemetry.
- `telemetry_contracts.benchmark` runs benchmark suites and computes summary/label metrics.
- `telemetry_contracts.cli` exposes `validate`, `static`, `scenario`, and `benchmark` commands.
- `examples/` contains the checkout contract, sample telemetry, source instrumentation, and scenario prompt.
- `benchmarks/` contains runnable benchmark configs.
- `case_studies/` contains public historical fixtures and metadata.
- `tests/` covers parser behavior, validator behavior, CLI behavior, static checks, scenarios, benchmark behavior, and examples.

## Example workflow

1. Write a contract for the telemetry needed to debug checkout failures.
2. Run static checks in CI to catch missing instrumentation names before execution.
3. Run service tests or staging traffic and export JSONL telemetry.
4. Validate emitted telemetry against the contract.
5. Add scenario checks for incident questions such as: “Can on-call identify tenant, cart, provider, retry count, and error class for a payment timeout?”

## Real-world finding workflow

The repo is designed to be run on real telemetry captures, not only synthetic fixtures. Export OTLP JSON from an OpenTelemetry Collector, convert it, then validate the converted JSONL:

```bash
python3 -m telemetry_contracts.cli import-otlp --input otlp-export.json --output captured.jsonl
python3 -m telemetry_contracts.cli validate --contract service.contract.json --events captured.jsonl --format json
```

`examples/real_world/otel_checkout_missing_tenant.*` is a case-study fixture modeled on a common production observability bug: payment failure traces and logs exist, but neither carries the tenant identifier needed to scope blast radius. The validator confirms the bug by reporting `telemetry.missing_field` for `tenant_id`.


## Benchmark harness

Run the built-in benchmark suite:

```bash
python3 -m telemetry_contracts.cli benchmark --config benchmarks/builtin.json --format json
python3 -m telemetry_contracts.cli benchmark --config benchmarks/builtin.json --format markdown
```

A benchmark config is JSON with a `cases` list. Each case points to a contract, JSONL events, optional scenario ids, optional metadata, and optional `expected_findings` labels. Paths are resolved relative to the config file, so external datasets can be benchmarked without changing package code. Reports include number of contracts, events, findings, findings by code/severity, label precision/recall when labels are present, runtime, and pass/fail.

## Public historical case study

`case_studies/gitlab_2017_database_outage/` contains a reconstructed fixture derived from GitLab's public January 31, 2017 database outage reports:

- <https://about.gitlab.com/blog/postmortem-of-database-outage-of-january-31/>
- <https://about.gitlab.com/blog/2017/02/01/gitlab-dot-com-database-incident/>

The fixture is clearly labeled as reconstructed, not raw GitLab telemetry. It encodes public facts such as replication lag/failure, a destructive command intended for the secondary but run on the primary, failed pg_dump backups from a PostgreSQL version mismatch, rejected cron notifications, and recovery from a roughly six-hour-old LVM snapshot.

See `docs/claims_evidence.md` for the bounded novelty claim, evidence, limitations, and reproduction protocol.

## LLM-process separation note

The idea document suggests LLMs can help generate realistic incident questions, propose telemetry requirements, and mutate services to create diagnosability bugs. This repository keeps that process separate from the correctness mechanism: contracts are explicit files, telemetry is concrete JSONL, and pass/fail results come from deterministic validators. No model call is required to run or trust the checks.

## Limitations

- Static checking is literal-based, not a full AST or OpenTelemetry semantic analysis.
- OTLP support covers common JSON exports for spans, metrics, and logs; protobuf/gRPC collector ingestion is future work.
- Cardinality is checked over the supplied sample window, not a production time series backend.
- Sampling and retention are represented as contract metadata rather than verified against infrastructure.
- Scenario matching is intentionally simple; robust incident-question synthesis is future work.

## Development

```bash
python3 -m pytest
make smoke
```

Optional YAML support:

```bash
python3 -m pip install '.[yaml]'
```
