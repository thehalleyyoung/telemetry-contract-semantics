# Telemetry Contracts

Telemetry Contracts is a standalone prototype for testing **observability as a correctness property**. A service is not merely correct when it returns the right response; for production systems, it should also emit the traces, metrics, logs, fields, tags, and retention/sampling assumptions needed to diagnose failures later.

This repository turns that thesis into executable checks:

- Runtime validation of JSONL telemetry events against contracts.
- Static checks that source code contains expected OpenTelemetry-style span, metric, and log names.
- Static telemetry security checks for sensitive values in logs and optional high-cardinality/correlation policies.
- Diagnosability scenario checks that ask whether a concrete incident question can be answered from emitted telemetry.
- Alternative-obligation checks that let one of several equivalent logs/spans/metrics satisfy a required evidence path without duplicate false positives.
- Strict validation that treats a contract as a closed-world model and reports unexpected fields, undeclared signal names, unmodeled services, and undocumented collector transformations, with bounded escape hatches.
- Observational-equivalence reports that compare two telemetry streams by incident-question answerability instead of byte equality.
- Transformation-preservation checks that compare source and post-transform streams to catch approved sampling, redaction, omission, retention, or aggregation that destroys contract or incident-question evidence.
- Incident-readiness reports that score required evidence, temporal/correlation coverage, privacy risk, and remediation completeness.
- Incident-window event-structure diagrams that make parent-child spans, links, log attachments, metric exemplars, happens-before, and concurrency evidence visible in service-owner reports.
- OTLP JSON import for testing real OpenTelemetry collector/exporter captures.
- A benchmark harness for built-in or user-provided contract/event corpora.
- A machine-readable finding taxonomy and taxonomy coverage report for JSON benchmark, validation, static, incident-readiness, equivalence, and preservation outputs.
- A reconstructed public historical case study based on the GitLab.com 2017 database outage postmortem.
- A current public-code case study that flags potential sensitive-value logging in an OWASP SecureTea sign-in sample.
- A strict-mode drift fixture and report over the GitLab 2017 reconstruction that demonstrates closed-world checks on public incident-derived data.
- Passing and failing examples for a checkout/payment service.

The prototype is intentionally non-AI runtime software. LLMs may help humans draft scenarios or contracts, but the validation path is deterministic Python code and test fixtures.

Roadmap status: `100_STEPS.md` currently has 28 of 100 items checked. Checked items are limited to capabilities backed by code, tests, fixtures, reports, or documentation in this repository.

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

python3 -m telemetry_contracts.cli lint-contract \
  --contract examples/contracts/checkout.contract.json

python3 -m telemetry_contracts.cli scenario \
  --contract examples/contracts/checkout.contract.json \
  --events examples/telemetry/passing.jsonl \
  --id payment-timeout

python3 -m telemetry_contracts.cli report incident-readiness \
  --contract examples/contracts/checkout.contract.json \
  --events examples/telemetry/passing.jsonl \
  --format markdown

python3 -m telemetry_contracts.cli report alternative-obligations \
  --contract case_studies/gitlab_2017_database_outage/contract.json \
  --events case_studies/gitlab_2017_database_outage/reconstructed_events.jsonl \
  --format markdown

python3 -m telemetry_contracts.cli import-otlp \
  --input examples/real_world/otel_checkout_missing_tenant.otlp.json \
  --output checkout.otlp.jsonl

python3 -m telemetry_contracts.cli validate \
  --contract examples/real_world/otel_checkout_missing_tenant.contract.json \
  --events checkout.otlp.jsonl

python3 -m telemetry_contracts.cli validate \
  --contract case_studies/gitlab_2017_database_outage/contract.json \
  --events case_studies/gitlab_2017_database_outage/reconstructed_events_strict_drift.jsonl \
  --strict --format json --fail-on never

python3 -m telemetry_contracts.cli benchmark \
  --config benchmarks/builtin.json \
  --format markdown

python3 -m telemetry_contracts.cli taxonomy \
  --findings reports/current_impact.json \
  --format markdown

python3 -m telemetry_contracts.cli describe-model \
  --events case_studies/gitlab_2017_database_outage/reconstructed_events.jsonl \
  --format markdown

python3 -m telemetry_contracts.cli equivalence \
  --contract case_studies/gitlab_2017_database_outage/contract.json \
  --left-events case_studies/gitlab_2017_database_outage/reconstructed_events.jsonl \
  --right-events case_studies/gitlab_2017_database_outage/reconstructed_events_sampled_missing_alert.jsonl \
  --scenario restore-readiness --format markdown

python3 -m telemetry_contracts.cli preservation \
  --contract case_studies/gitlab_2017_database_outage/contract.json \
  --before-events case_studies/gitlab_2017_database_outage/reconstructed_events.jsonl \
  --after-events case_studies/gitlab_2017_database_outage/reconstructed_events_sampled_missing_alert.jsonl \
  --format markdown --fail-on never
```

If installed as a package, the same CLI is available as `telemetry-contracts`.

## Contract language

Executable examples use JSON so the project runs without third-party YAML libraries. YAML files (`.yaml`/`.yml`) are accepted only when `PyYAML` is installed; otherwise the loader fails loudly with a clear error.

A contract declares a service plus expected telemetry signals:

```json
{
  "version": "1.0",
  "service": "checkout",
  "metadata": {
    "sampling": {
      "traces": {"strategy": "parent_based", "minimum_rate": 0.1, "always_sample_errors": true},
      "logs": {"strategy": "always_on", "minimum_rate": 1.0}
    },
    "retention": {"traces_days": 7, "metrics_days": 30, "logs_days": 14}
  },
  "privacy_classifications": {
    "token": {"allowed_transformations": ["redacted", "hashed", "tokenized", "omitted"]},
    "identifier": {"allowed_transformations": ["raw", "hashed", "tokenized"]}
  },
  "correlation": {"keys": ["trace_id", "request_id"], "require_on": ["spans", "logs"]},
  "field_definitions": {
    "tenant_id": {"type": "string", "required": true, "pattern": "tenant-[a-z0-9-]+"}
  },
  "temporal_sequences": [{
    "id": "payment-failure-flow",
    "group_by": ["trace_id"],
    "window_ms": 5000,
    "steps": [
      {"kind": "span", "name": "checkout.request"},
      {"kind": "span", "name": "payment.authorize"},
      {"kind": "log", "name": "checkout.payment_failed"}
    ]
  }],
  "spans": [{
    "name": "payment.authorize",
    "required": true,
    "fields": {
      "tenant_id": {"$ref": "#/field_definitions/tenant_id"},
      "auth_token": {"type": "string", "classification": "token", "transformation": "redacted", "forbidden_patterns": ["bearer_token"]},
      "retry_count": {"type": "integer", "unit": "count", "min": 0, "max": 3},
      "payment_provider": {"type": "string", "allowed_values": ["stripe", "adyen", "test"]},
      "duration_ms": {"type": "number", "unit": "ms", "min": 0, "max": 30000},
      "error_code": {"type": "string", "required": false},
      "remediation_hint": {"type": "string", "required": false},
      "retryable": {"type": "boolean", "required": false}
    },
    "conditional_requirements": [
      {"if": {"field": "error_code", "present": true}, "then": {"fields": ["remediation_hint", "retryable"]}}
    ]
  }]
}
```

Supported checks include:

- Signal presence for spans, metrics, and logs.
- Contract structure validation against the published JSON Schema in `docs/contract.schema.json`.
- Required fields/tags/attributes.
- Reusable `field_definitions` referenced with `$ref`/`ref`, with per-use overrides.
- Primitive field types: string, integer, number, boolean, object, array, null.
- Allowed values.
- Regex patterns.
- `forbidden_patterns`, including built-ins such as `email`, `bearer_token`, `jwt`, `password_assignment`, and `credit_card`.
- Sensitivity classification for PII, credentials, tokens, and secrets, with warnings for unclassified sensitive-looking fields.
- Schema-level `privacy_classifications` that restrict fields to allowed transformations: `redacted`, `hashed`, `tokenized`, `bucketed`, or `omitted`.
- Numeric `min`/`max` ranges.
- Unit validation for durations, bytes, percentages, ratios, counts, timestamps, and currency-like values.
- Metric `value` checks.
- Log severity and message pattern checks.
- Log `severity_policy` minimum thresholds, for example `{"min": "ERROR"}`.
- Conditional requirements, for example requiring `remediation_hint` and `retryable` whenever `error_code` is present.
- Cardinality hints and bounded-cardinality policies as warnings.
- Cross-signal correlation policies requiring shared keys such as `trace_id` or `request_id` across configured signal kinds.
- Temporal sequence checks over spans, metrics, and logs using timestamps and optional `group_by` incident windows.
- Duplicate signal and duplicate field diagnostics during contract linting.
- Machine-readable sampling and retention policy stubs under `metadata.sampling` and `metadata.retention`; transformation-preservation defaults may be declared under `metadata.transformation_preservation` with `approved_transformations` and `preserve_scenarios`.
- Alternative obligations under `alternative_obligations`, where a required finite disjunction passes when at least one declared option has a witness event containing all required fields; `minimum_observations` scenario entries may also use `any_of` for equivalent evidence paths.
- Strict validation via `validate --strict` or `metadata.strict_validation.enabled`. Strict mode adds closed-world obligations: each event service must match the modeled service or `allow_unmodeled_services`; each span/log/metric name must be declared in signal sections, scenarios, temporal sequences, or alternative obligations unless `allow_undeclared_signals` names it; emitted attributes/tags/fields must be declared unless `allowed_extra_fields` or `allow_unexpected_fields` permits them; collector transformations must appear in `metadata.transformation_preservation.approved_transformations` or `allow_collector_transformations`.
- Incident-readiness scoring over finite telemetry files. The report combines runtime and scenario findings into required-evidence coverage, temporal coverage, correlation coverage, privacy risk, remediation completeness, unanswered incident questions, and top remediation groups.
- Diagnosability adequacy checks for incident questions. A scenario may declare `minimum_observations`: each item either names the span, log, or metric plus required fields and a `purpose`, or declares an `any_of` set of equivalent options. The finite trace is adequate for that question iff every minimum observation or required alternative is witnessed and all required fields are present; reports include matching event indices and exact missing evidence.
- Observational equivalence for debugging tasks. `equivalence` compares two finite telemetry files against selected scenario questions and treats them as equivalent only when the same questions are answerable with the same minimum-observation and required-field signature. This allows sampled, reordered, scrubbed, or aggregated streams to be evaluated by retained debugging utility rather than byte equality.
- Transformation preservation for approved telemetry changes. `preservation` implements an obligation-local relation: if a runtime contract obligation or selected scenario witness is satisfied before transformation, it must remain satisfied after transformation. Reports identify new contract failures plus lost incident-question signals/fields, and checked-in GitLab 2017 reports demonstrate a sampled/exported derivative that removes the backup-failure alert witness.
- Event-structure summaries and Mermaid diagrams over incident windows, including parent-child spans, span links, attached logs, metric exemplars, timestamp happens-before edges, and concurrent spans when that evidence is present.

## Runtime event format

Runtime validation reads newline-delimited JSON. Events are intentionally simple and collector-neutral:

```json
{"kind":"span","service":"checkout","name":"payment.authorize","trace_id":"trace-123","timestamp_ms":1000,"attributes":{"tenant_id":"tenant-acme","payment_provider":"stripe","retry_count":2}}
{"kind":"metric","service":"checkout","name":"payment.authorization.latency_ms","trace_id":"trace-123","timestamp_ms":1100,"value":812.7,"tags":{"payment_provider":"stripe"}}
{"kind":"log","service":"checkout","name":"checkout.payment_failed","trace_id":"trace-123","timestamp_ms":1200,"severity":"ERROR","message":"payment authorization failed","fields":{"tenant_id":"tenant-acme"}}
```

Findings include severity, code, message, event path, contract path, and details when useful. Use `--format json` for machine-readable output. JSON findings are also annotated with taxonomy metadata: category, formal clause (for example `SAT.required-field` or `STRICT.signal-closed-world`), remediation, disclosure sensitivity, service-owner routing, SARIF-compatible level, and CI baseline keys. `python3 -m telemetry_contracts.cli taxonomy` emits the canonical taxonomy from `docs/finding_taxonomy.json`; with `--findings`, it summarizes which semantic clauses and categories appear in a concrete JSON report.

## Observation model and satisfaction relation

`python3 -m telemetry_contracts.cli describe-model` prints the executable observation domain used by the checker. It maps spans, logs, metrics, resources, scopes, exemplars, timestamps, attributes, and provenance to the repository JSONL fields and the OTLP JSON fields currently normalized by `import-otlp`.

The core satisfaction relation is reported as `T ⊨ C`: a finite telemetry trace `T` satisfies a contract `C` when every well-formed contract obligation evaluates to true over observations relevant to `C.service`. For strict mode, this relation is strengthened with closed-world side conditions over service identity, declared signal names, declared event fields, and documented collector transformations. For alternative obligations, the executable clause is a finite disjunction: a required group is satisfied iff at least one option has a concrete witness event with every declared field; optional groups record acceptable evidence paths without failing absent telemetry. The model page defines how present, absent, malformed, partial, unknown, and transformed evidence is interpreted. Passing `--events` adds an artifact summary and a finite event-structure view, which is useful for checking what kinds, names, fields, correlation keys, timestamps, parent/child edges, log attachments, metric exemplars, and incident-window happens-before diagrams are actually present in a historical or current fixture.

## Architecture

- `telemetry_contracts.loader` loads JSON/YAML contracts and JSONL events with explicit errors.
- `telemetry_contracts.schema` provides the canonical contract JSON Schema used by linting and tests.
- `telemetry_contracts.validator` checks emitted telemetry against signal, field, correlation, and alternative-obligation specifications.
- `telemetry_contracts.semantics` defines the observation-domain page, satisfaction-relation states, finite event structures, and artifact summaries used by `describe-model` and service-owner reports.
- `telemetry_contracts.alternatives` evaluates finite disjunctions over semantically equivalent evidence paths and emits witness/counterexample reports.
- `telemetry_contracts.cli lint-contract` validates contract schema semantics before events exist.
- `telemetry_contracts.static_checker` scans source files for expected instrumentation literals and common telemetry/logging anti-patterns.
- `telemetry_contracts.scenario` defines diagnosability adequacy for incident questions and verifies minimum observations against emitted telemetry.
- `telemetry_contracts.equivalence` compares two traces by their scenario answerability signatures.
- `telemetry_contracts.preservation` checks pre/post transformation preservation for runtime obligations and scenario witnesses.
- `telemetry_contracts.incident_report` generates service-owner incident-readiness JSON/Markdown from the deterministic validator and scenario checks.
- `telemetry_contracts.benchmark` runs benchmark suites and computes summary/label metrics.
- `telemetry_contracts.taxonomy` emits the finding-rule catalog and summarizes observed findings by code, category, formal clause, SARIF level, and service-owner route.
- `telemetry_contracts.cli` exposes `validate` (including `--strict`), `static`, `scenario`, `equivalence`, `preservation`, `describe-model`, `report incident-readiness`, `report alternative-obligations`, `benchmark`, and `taxonomy` commands.
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

`case_studies/current/owasp_securetea_signin/` is a reproducible public-code static case study. It analyzes OWASP SecureTea Project's `react_gui/src/views/Signin.js` at commit `7a2da8756e6addbe379ae9b23905dcdbe68b3814` and produces labeled `static.secret_logging` findings for logging a password value and a cookie value. The repository records source URL, retrieval date, commit, file SHA, license, generated reports, and exact reproduction commands.


## Benchmark harness

Run the built-in benchmark suite:

```bash
python3 -m telemetry_contracts.cli benchmark --config benchmarks/builtin.json --format json
python3 -m telemetry_contracts.cli benchmark --config benchmarks/builtin.json --format markdown
```

A benchmark config is JSON with a `cases` list. Each case points to a contract plus JSONL events, source paths, or both; optional scenario ids; optional `strict: true`; optional metadata; and optional `expected_findings` labels. Paths are resolved relative to the config file, so external datasets can be benchmarked without changing package code. Reports include runtime/static/scenario/strict check flags, number of contracts, events, findings, findings by code/severity, label precision/recall when labels are present, runtime, and pass/fail.

## Public historical case study

`case_studies/gitlab_2017_database_outage/` contains a reconstructed fixture derived from GitLab's public January 31, 2017 database outage reports:

- <https://about.gitlab.com/blog/postmortem-of-database-outage-of-january-31/>
- <https://about.gitlab.com/blog/2017/02/01/gitlab-dot-com-database-incident/>

The fixture is clearly labeled as reconstructed, not raw GitLab telemetry. It encodes public facts such as replication lag/failure, a destructive command intended for the secondary but run on the primary, failed pg_dump backups from a PostgreSQL version mismatch, rejected cron notifications, and recovery from a roughly six-hour-old LVM snapshot. Its contract also includes a required alternative obligation for destructive-command location evidence: either a structured log or an equivalent span can satisfy the same host/role evidence requirement.

See `docs/claims_evidence.md` for the bounded novelty claim, evidence, limitations, and reproduction protocol.

Generate a bounded incident-readiness report for this historical reconstruction:

```bash
python3 -m telemetry_contracts.cli report incident-readiness \
  --contract case_studies/gitlab_2017_database_outage/contract.json \
  --events case_studies/gitlab_2017_database_outage/reconstructed_events.jsonl \
  --scenario restore-readiness \
  --format markdown \
  --fail-on never
```

The command reports missing evidence for the declared restore-readiness question and phrases the result as artifact-scoped evidence over reconstructed public facts, not as a claim about GitLab's private telemetry.

Generate the checked-in strict-mode validation report for a bounded drift derivative of the same public reconstruction:

```bash
python3 -m telemetry_contracts.cli validate \
  --contract case_studies/gitlab_2017_database_outage/contract.json \
  --events case_studies/gitlab_2017_database_outage/reconstructed_events_strict_drift.jsonl \
  --strict --format json --fail-on never
```

`reports/gitlab_2017_strict_validation.json` records 14 findings on that bounded derivative, including one undeclared signal, one unmodeled collector service, two unexpected fields, and one undocumented collector transformation. This demonstrates the closed-world utility on a historical public-data reconstruction without claiming access to GitLab private telemetry.

Generate the checked-in alternative-obligation witness report:

```bash
python3 -m telemetry_contracts.cli report alternative-obligations \
  --contract case_studies/gitlab_2017_database_outage/contract.json \
  --events case_studies/gitlab_2017_database_outage/reconstructed_events.jsonl \
  --format markdown \
  --output reports/gitlab_2017_alternative_obligations.md
```

The report records `pass=true`: the structured log witnesses the destructive-command location obligation, while the equivalent span option is absent without creating a duplicate false positive.

## Current public-code case study

`case_studies/current/owasp_securetea_signin/` contains a public-code defensive analysis fixture:

- Source: <https://github.com/OWASP/SecureTea-Project/blob/7a2da8756e6addbe379ae9b23905dcdbe68b3814/react_gui/src/views/Signin.js>
- Retrieval date: 2026-05-29
- Finding type: potential telemetry privacy/security anti-patterns in public sample code (`static.secret_logging`), not an exploit or vulnerability disclosure.
- Generated evidence: `reports/current_impact.json` and `reports/current_impact.md`.

## LLM-process separation note

The idea document suggests LLMs can help generate realistic incident questions, propose telemetry requirements, and mutate services to create diagnosability bugs. This repository keeps that process separate from the correctness mechanism: contracts are explicit files, telemetry is concrete JSONL, and pass/fail results come from deterministic validators. No model call is required to run or trust the checks.

## Limitations

- Static checking is literal-based, not a full AST or OpenTelemetry semantic analysis.
- OTLP support covers common JSON exports for spans, metrics, and logs; protobuf/gRPC collector ingestion is future work.
- Cardinality is checked over the supplied sample window, not a production time series backend.
- Sampling and retention stubs are linted for machine-readable contract shape, but not verified against live collector or backend configuration.
- Strict mode is a closed-world check over the supplied finite event artifact; escape hatches are explicit but do not prove a collector pipeline is correctly configured.
- Scenario matching is intentionally simple; robust incident-question synthesis is future work.
- Incident-readiness scores are computed over the supplied finite artifact; they are useful for CI trend and review, not a guarantee of production incident success.

## Development

```bash
python3 -m pytest
make smoke
```

Optional YAML support:

```bash
python3 -m pip install '.[yaml]'
```
