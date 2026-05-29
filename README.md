# Telemetry Contracts

Telemetry Contracts is a standalone prototype for testing **observability as a correctness property**. A service is not merely correct when it returns the right response; for production systems, it should also emit the traces, metrics, logs, fields, tags, and retention/sampling assumptions needed to diagnose failures later.

This repository turns that thesis into executable checks:

- Runtime validation of JSONL telemetry events against contracts.
- Static checks that resolve expected OpenTelemetry-style span, metric, and log names through Python ASTs and lightweight multi-language source heuristics, with source spans and contract-obligation details.
- Static telemetry security/API checks for credentials, PII, tenant identifiers, and unsafe payload previews in logs, precise justified suppression comments, optional high-cardinality/correlation policies, error-span exception/status/remediation/retryability evidence, tracer/meter scope names, metric unit/description metadata, and required semantic-convention attributes. Suppression comments must name the exact finding code, source span, owner, ISO expiry, reason, and disclosure sensitivity, so a stale or imprecise suppression does not hide unrelated findings.
- Diagnosability scenario checks that ask whether a concrete incident question can be answered from emitted telemetry.
- Alternative-obligation checks that let one of several equivalent logs/spans/metrics satisfy a required evidence path without duplicate false positives.
- Temporal-logic checks for safety invariants, bounded responses, absence properties, ordering, and deadlines over finite telemetry traces.
- Finite abstract-domain summaries for signal values, label sets, severity, units, privacy classifications, and path feasibility, including documented join/widening behavior.
- Hyperproperty checks for PII non-disclosure and tenant non-interference over finite sets/pairs of traces, producing privacy-risk witness findings.
- Assume-guarantee reports that partition finite-trace obligations into service emission guarantees, collector/exporter assumptions, environment assumptions, and on-call diagnostic obligations with layer-specific counterexamples.
- Strict validation that treats a contract as a closed-world model and reports unexpected fields, undeclared signal names, unmodeled services, and undocumented collector transformations, with bounded escape hatches.
- Observational-equivalence reports that compare two telemetry streams by incident-question answerability instead of byte equality.
- Transformation-preservation checks that compare source and post-transform streams to catch approved sampling, redaction, omission, retention, or aggregation that destroys contract or incident-question evidence.
- Contract-refinement checks that compare a base and candidate contract for preserved required evidence, strengthened predicates, privacy non-weakening, strict-mode policy preservation, and compatible collector/environment/on-call assumptions.
- Pull-request contract-diff reports that highlight new obligations, removed obligations, changed privacy classifications/transformations, and changed diagnosability claims between contract versions.
- Contract composition/inheritance for shared organization or team policies, with parent-refinement checks so service contracts cannot silently weaken inherited evidence requirements.
- Incident-readiness reports that score required evidence, temporal/correlation coverage, privacy risk, and remediation completeness.
- Incident-window event-structure diagrams that make parent-child spans, links, log attachments, metric exemplars, happens-before, and concurrency evidence visible in service-owner reports.
- OTLP JSON/JSONL import for testing OpenTelemetry collector/exporter captures, preserving spans, logs, metrics, exemplars, links, scope/resource metadata, provenance paths, and import diagnostics.
- Collector-export analysis for dropped evidence, unknown schemas, high-cardinality attributes, PII/secret patterns, metric temporality, and unsupported OTLP features, plus JSONL↔OTLP round-trip conversion for importer regression tests.
- A benchmark harness for built-in or user-provided contract/event/source corpora, with multi-contract cases, metadata, filters, label metrics, remediation grouping, diff reports, runtime/memory counters, OTLP import-loss accounting, a path-sensitive checkout fixture, a second current public-code static case study, a ten-service synthetic microservices fixture, and reconstructed incident-readiness blind-spot fixtures.
- A machine-readable finding taxonomy and taxonomy coverage report for JSON benchmark, validation, static, semantic-convention, incident-readiness, equivalence, and preservation outputs.
- SARIF export for runtime/static findings and benchmark reports, plus CI gate helpers that fail on new unbaselined findings while honoring owned, expiring baselines.
- Deterministic report regeneration and a public claims-to-evidence matrix that links bounded README/report claims to checked-in fixtures, generated artifacts, and tests.
- A deterministic `explain` command that turns a finding code into its formal clause, practical impact, example trace shape, concrete fix, CI baseline key, and optional observed examples from public or benchmark reports.
- An executable small-step `evaluate-semantics` command that emits contract-evaluation derivations and checks their denotation against the deterministic validator on golden and historical traces.
- A compiled `monitor` command that runs deterministic bounded-memory runtime monitors over finite JSONL traces, with sliding-window witnesses for temporal response/sequence obligations and an observed memory envelope.
- An `event-windows` report that groups events and findings by trace, request, tenant, deployment, scenario, incident id, or bounded incident time slice so failures localize to actionable ownership units.
- A `proof-obligations` command that instantiates well-formedness, satisfaction, preservation, refinement, monitor-soundness, and benchmark-label validity proof-goal templates against contracts, runtime traces, transformation pairs, and benchmark labels.
- A `semconv` command that lints declared and observed telemetry against bounded OpenTelemetry semantic-convention rules plus contract-local policies, citing the rule and exact attribute/name remediation.
- A `report service-owner` command that combines runtime, static, semantic-convention, and incident-readiness evidence into an owner-oriented coverage/remediation report with failing obligations, privacy risks, collector/export issues, source spans, and bounded limitations.
- A local `init` workflow that scaffolds a starter contract, example events, owner metadata, CI gate script, and incident-readiness report.
- A `doctor` command that checks Python/package/YAML availability, collector-export paths, report output paths, and CI environment assumptions before wiring the tool into automation.
- A type-check-friendly public Python API that exposes stable loaders, runtime/static validation, benchmark execution, OTLP import, and report generation entry points from `telemetry_contracts`.
- Common `--output`, `--code`, and `--severity` filtering on finding-producing validation commands, and report-level finding filters on service-owner/report subcommands.
- A reconstructed public historical case study based on the GitLab.com 2017 database outage postmortem.
- A current public-code case study that flags potential sensitive-value logging in an OWASP SecureTea sign-in sample.
- A strict-mode drift fixture and report over the GitLab 2017 reconstruction that demonstrates closed-world checks on public incident-derived data.
- Passing and failing examples for a checkout/payment service, `examples/path_sensitive/` for feature flags, retries, exceptions, and fallbacks, plus `examples/microservices/` for a correlated checkout flow across checkout, payment, inventory, shipping, auth, notification, queue, cache, database, and collector contracts.
- Operational scorecards and authoring guidance for HTTP APIs, batch jobs, message consumers, cron tasks, stateful workers, privacy-safe telemetry, operational ranges, anti-patterns, CI/review integration, and OTLP importer limitations in `docs/operational_scorecards.md`.
- JSON report schema documentation for finding, import-diagnostic, scenario, benchmark, service-owner, and claims-evidence report envelopes under `docs/report_schemas/`, real-world fixture templates under `case_studies/templates/`, with a replication guide and release checklist for bounded public claims.

The prototype is intentionally non-AI runtime software. LLMs may help humans draft scenarios or contracts, but the validation path is deterministic Python code and test fixtures.

Roadmap status: the local planning file `100_STEPS.md` currently has 100 of 100 items checked and is intentionally gitignored; README summarizes committed roadmap progress. Checked items are limited to capabilities backed by code, tests, fixtures, reports, or documentation in this repository.

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

python3 -m telemetry_contracts.cli report assume-guarantee \
  --contract case_studies/gitlab_2017_database_outage/contract.json \
  --events case_studies/gitlab_2017_database_outage/reconstructed_events_sampled_missing_alert.jsonl \
  --format markdown --fail-on never

python3 -m telemetry_contracts.cli import-otlp \
  --input examples/real_world/otel_checkout_missing_tenant.otlp.json \
  --output checkout.otlp.jsonl \
  --diagnostics-output checkout.otlp.diagnostics.json

python3 -m telemetry_contracts.cli analyze-collector-export \
  --input examples/otlp/collector_coverage_all_signals.otlp.json \
  --format markdown

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

python3 -m telemetry_contracts.cli benchmark \
  --config benchmarks/builtin.json \
  --case-id synthetic-microservices-checkout-pass \
  --format markdown

python3 -m telemetry_contracts.cli benchmark \
  --config benchmarks/builtin.json \
  --case-id reconstructed-incident-blind-spots \
  --format markdown

python3 -m telemetry_contracts.cli abstract-domains \
  --contract examples/path_sensitive/contract.json \
  --events examples/path_sensitive/passing.jsonl \
  --format markdown

python3 -m telemetry_contracts.cli static \
  --contract case_studies/current/public_static_patterns/contract.json \
  case_studies/current/public_static_patterns \
  --format json --fail-on never

python3 -m telemetry_contracts.cli taxonomy \
  --findings reports/current_impact.json \
  --format markdown

python3 -m telemetry_contracts.cli validate \
  --contract examples/contracts/checkout.contract.json \
  --events examples/telemetry/failing.jsonl \
  --format sarif

python3 -m telemetry_contracts.cli ci-gate \
  --findings examples/ci/static_findings.example.json \
  --baseline examples/ci/baseline.example.json \
  --format markdown

python3 -m telemetry_contracts.cli regenerate-artifacts --format markdown

python3 -m telemetry_contracts.cli claims-matrix --format markdown

python3 -m telemetry_contracts.cli explain telemetry.strict_unexpected_field \
  --examples reports/gitlab_2017_strict_validation.json \
  --format markdown

python3 -m telemetry_contracts.cli describe-model \
  --events case_studies/gitlab_2017_database_outage/reconstructed_events.jsonl \
  --format markdown

python3 -m telemetry_contracts.cli evaluate-semantics \
  --contract case_studies/gitlab_2017_database_outage/contract.json \
  --events case_studies/gitlab_2017_database_outage/reconstructed_events_strict_drift.jsonl \
  --strict --format markdown --fail-on never

python3 -m telemetry_contracts.cli monitor \
  --contract case_studies/gitlab_2017_database_outage/contract.json \
  --events case_studies/gitlab_2017_database_outage/reconstructed_events_sampled_missing_alert.jsonl \
  --format markdown --fail-on never

python3 -m telemetry_contracts.cli report event-windows \
  --contract case_studies/gitlab_2017_database_outage/contract.json \
  --events case_studies/gitlab_2017_database_outage/reconstructed_events_sampled_missing_alert.jsonl \
  --dimension incident --incident-slice-ms 2000 \
  --format markdown --fail-on never

python3 -m telemetry_contracts.cli report service-owner \
  --contract case_studies/gitlab_2017_database_outage/contract.json \
  --events case_studies/gitlab_2017_database_outage/reconstructed_events_sampled_missing_alert.jsonl \
  --scenario restore-readiness \
  --format markdown --fail-on never

python3 -m telemetry_contracts.cli doctor \
  --collector-export examples/otlp/collector_coverage_all_signals.otlp.json \
  --report-path reports/current_impact.md \
  --format markdown

python3 -m telemetry_contracts.cli init \
  --service checkout --owner payments-team \
  --output-dir telemetry-contracts-starter

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

python3 -m telemetry_contracts.cli refinement \
  --base-contract case_studies/gitlab_2017_database_outage/refinement_base_contract.json \
  --candidate-contract case_studies/gitlab_2017_database_outage/contract.json \
  --format markdown

python3 -m telemetry_contracts.cli contract-diff \
  --base-contract case_studies/gitlab_2017_database_outage/refinement_base_contract.json \
  --candidate-contract case_studies/gitlab_2017_database_outage/refinement_candidate_weakened_contract.json \
  --format markdown

python3 -m telemetry_contracts.cli compose-contract \
  --contract case_studies/gitlab_2017_database_outage/composed_contract.json \
  --format markdown

python3 -m telemetry_contracts.cli proof-obligations \
  --contract case_studies/gitlab_2017_database_outage/contract.json \
  --events case_studies/gitlab_2017_database_outage/reconstructed_events_strict_drift.jsonl \
  --strict \
  --before-events case_studies/gitlab_2017_database_outage/reconstructed_events.jsonl \
  --after-events case_studies/gitlab_2017_database_outage/reconstructed_events_sampled_missing_alert.jsonl \
  --benchmark-config benchmarks/builtin.json \
  --format markdown

python3 -m telemetry_contracts.cli semconv \
  --contract case_studies/gitlab_2017_database_outage/contract.json \
  --events case_studies/gitlab_2017_database_outage/reconstructed_events.jsonl \
  --format markdown --fail-on never

python3 -m telemetry_contracts.cli validate \
  --contract examples/temporal_logic/contract.json \
  --events examples/temporal_logic/failing.jsonl \
  --format json --fail-on never

python3 -m telemetry_contracts.cli validate \
  --contract case_studies/gitlab_2017_database_outage/contract.json \
  --events case_studies/gitlab_2017_database_outage/reconstructed_events_sampled_missing_alert.jsonl \
  --format json --fail-on never

python3 -m telemetry_contracts.cli validate \
  --contract examples/hyperproperties/contract.json \
  --events examples/hyperproperties/failing.jsonl \
  --format json --fail-on never

python3 -m telemetry_contracts.cli validate \
  --contract case_studies/current/owasp_securetea_signin/contract.json \
  --events case_studies/current/owasp_securetea_signin/reconstructed_console_events.jsonl \
  --format json --fail-on never
```

If installed as a package, the same CLI is available as `telemetry-contracts`; wheel and editable-install console-script smoke tests are part of the test suite.

## Operational and replication docs

- `docs/operational_scorecards.md` maps workload scorecards, privacy-safe telemetry examples, operational range clauses, authoring anti-patterns, CI/SARIF/review integration, and OTLP importer limitations to checked-in commands and fixtures.
- `docs/tutorials/broken_service_tutorial.md` and `docs/tutorials/slo_debugging_contract_clauses.md` walk through fixing a broken service and mapping SLO debugging questions to contract clauses and passing/failing traces.
- `docs/performance_budgets.md` records the bounded event-indexing memory/performance budgets for large finite traces and OTLP fixtures.
- `docs/report_schemas.md` and `docs/report_schemas/*.schema.json` document the JSON envelopes consumed by CI, SARIF, benchmark, service-owner, and claims-evidence workflows.
- `docs/replication_guide.md` gives exact commands for benchmark metrics, generated reports, historical GitLab analysis, current OWASP SecureTea case-study claims, OTLP importer diagnostics, and paper-table artifacts.
- `docs/release_checklist.md` records limitations and release gates for mechanized-core scope, static-analysis boundaries, reconstructed-data claims, benchmark validity threats, privacy safeguards, archival metadata, checksums, and deterministic non-AI validation.

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
- `forbidden_patterns`, including built-ins such as `email`, `phone`, `bearer_token`, `jwt`, `password_assignment`, `credit_card`, and `tenant_identifier`.
- Sensitivity classification for PII, credentials, tokens, secrets, raw payload previews, and declared tenant identifiers, with warnings for unclassified sensitive-looking fields and runtime risk details for credentials, email, phone, tenant, and payload-preview exposures.
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
- Temporal properties under `temporal_properties`: `safety`, `bounded_response`, `absence`, `ordering`, and `deadline`, with selectors, field predicates, optional grouping keys, and concrete finding codes such as `telemetry.temporal_response`. The validator builds a finite event index by kind/name, service, correlation keys, and timestamp buckets before signal checks, preserving existing semantics while supporting larger traces.
- Runtime monitor compilation via `monitor`: required signal predicates become matched-bit monitors, safety/absence properties become per-event checks, bounded responses and temporal sequences keep active sliding-window witnesses, and ordering/deadline properties keep per-group prefix summaries. JSON/Markdown reports expose the compiled monitor counts, formal judgement, findings, and observed memory envelope.
- Abstract-domain summaries via `abstract-domains`: deterministic prototype domains summarize bounded string values, attribute presence, severity joins, units, privacy classes, and condition-sensitive path feasibility, with each domain reporting its join, widening, and limitations.
- Event-window grouping via `report event-windows`: the report first evaluates `T ⊨ C`, then assigns event-local findings to every observed trace, request/correlation, tenant, deployment, scenario, incident-id, or bounded incident-slice ownership unit. Findings without an event witness remain in a global contract window, preserving missing-signal evidence without inventing an owner.
- Hyperproperties under `hyperproperties`: `pii_non_disclosure` checks raw sensitive fields reaching configured telemetry sinks, and `tenant_non_interference` checks pairwise that distinct tenants do not share configured isolation keys such as `trace_id` or `request_id`. Findings include concrete event-index witnesses (`telemetry.hyper_pii_disclosure`, `telemetry.hyper_tenant_interference`).
- Duplicate signal and duplicate field diagnostics during contract linting.
- Machine-readable sampling and retention policy stubs under `metadata.sampling` and `metadata.retention`; transformation-preservation defaults may be declared under `metadata.transformation_preservation` with `approved_transformations` and `preserve_scenarios`.
- Alternative obligations under `alternative_obligations`, where a required finite disjunction passes when at least one declared option has a witness event containing all required fields; `minimum_observations` scenario entries may also use `any_of` for equivalent evidence paths.
- Assume-guarantee obligations under `assume_guarantee`, grouped as `service_guarantees`, `collector_assumptions`, `environment_assumptions`, and `oncall_obligations`. `report assume-guarantee` checks signal/field witnesses, field predicates, scenarios, temporal properties, alternative evidence, and documented collector transformations, then reports which layer is accountable for each missing or non-preserved witness.
- Strict validation via `validate --strict` or `metadata.strict_validation.enabled`. Strict mode adds closed-world obligations: each event service must match the modeled service or `allow_unmodeled_services`; each span/log/metric name must be declared in signal sections, scenarios, temporal sequences, or alternative obligations unless `allow_undeclared_signals` names it; emitted attributes/tags/fields must be declared unless `allowed_extra_fields` or `allow_unexpected_fields` permits them; collector transformations must appear in `metadata.transformation_preservation.approved_transformations` or `allow_collector_transformations`.
- OpenTelemetry semantic-convention linting via `semconv`. The checker reports `semconv.*` warnings for legacy attributes such as `http.method`/`db.system`, missing convention attributes such as `http.request.method`, `http.route`, `http.response.status_code`, `db.system.name`, or `messaging.system`, metric names that encode units without declaring `value.unit`, and `metadata.semantic_conventions.required_attributes` local-policy obligations. Each finding includes the cited convention/local policy and an exact rename/add remediation.
- Source static analysis via `static`. The checker extracts telemetry observations from Python ASTs and lightweight supported-language source patterns, reports missing required instrumentation with `details.obligation`, records source line/column spans, resolves constants/wrappers/simple string construction, and can enforce optional `static_rules` for correlated error logs, high-cardinality labels, error-span exception/status/remediation/retryability fields, tracer/meter names, metric unit/description API metadata, and required semantic-convention attributes. Suppression comments must name the exact finding code, source span, owner, ISO expiry, reason, and disclosure sensitivity, so a stale or imprecise suppression does not hide unrelated findings.
- Incident-readiness scoring over finite telemetry files. The report combines runtime and scenario findings into required-evidence coverage, temporal coverage, correlation coverage, privacy risk, remediation completeness, unanswered incident questions, and top remediation groups.
- Diagnosability adequacy checks for incident questions. A scenario may declare `minimum_observations`: each item either names the span, log, or metric plus required fields and a `purpose`, or declares an `any_of` set of equivalent options. The finite trace is adequate for that question iff every minimum observation or required alternative is witnessed and all required fields are present; reports include matching event indices and exact missing evidence.
- Observational equivalence for debugging tasks. `equivalence` compares two finite telemetry files against selected scenario questions and treats them as equivalent only when the same questions are answerable with the same minimum-observation and required-field signature. This allows sampled, reordered, scrubbed, or aggregated streams to be evaluated by retained debugging utility rather than byte equality.
- Transformation preservation for approved telemetry changes. `preservation` implements an obligation-local relation: if a runtime contract obligation or selected scenario witness is satisfied before transformation, it must remain satisfied after transformation. Reports identify new contract failures plus lost incident-question signals/fields, and checked-in GitLab 2017 reports demonstrate a sampled/exported derivative that removes the backup-failure alert witness.
- Contract refinement for version and scope comparisons. `refinement` checks `C′ ⊑ C`: a candidate contract must preserve required base signals, fields, scenarios, temporal properties, alternative obligations, and service guarantees; predicate changes must be equal or stronger; privacy classifications and transformation policies must not expand allowed exposure; strict-mode escape hatches must not widen; and collector/environment/on-call assumptions must not become harder to satisfy. Reports include exact weakened-requirement, privacy, transformation, and assumption findings.
- Pull-request contract diffs via `contract-diff`: compare two contract versions and summarize added/removed telemetry obligations, privacy metadata changes, and changed scenario/temporal/alternative diagnosability claims. JSON findings use `contract_diff.*` taxonomy codes so CI can review these separately from refinement gates.
- Contract composition/inheritance via top-level `extends` or `inherits`. `load_contract` resolves relative parent policies deterministically (`C = P₁ ⊕ … ⊕ Pₙ ⊕ Δ`), merging shared fields, signal clauses, scenarios, temporal properties, alternatives, metadata, and assume-guarantee structure. `compose-contract` reports inherited, declared, overridden, and resolved signal keys and runs parent refinement checks to prove the resolved service contract preserves inherited evidence.
- Proof-obligation reports for the implemented contract language. `proof-obligations` catalogs 27 feature groups and instantiates templates for well-formedness, satisfaction, preservation, refinement, monitor soundness, and benchmark-label validity. When concrete runtime/benchmark artifacts are supplied, non-refinement obligations are marked `discharged` or `violated`; use the dedicated `refinement` command for executable contract-version checks.
- Event-structure summaries and Mermaid diagrams over incident windows, including parent-child spans, span links, attached logs, metric exemplars, timestamp happens-before edges, and concurrent spans when that evidence is present.

## Runtime event format

Runtime validation reads newline-delimited JSON. Events are intentionally simple and collector-neutral:

```json
{"kind":"span","service":"checkout","name":"payment.authorize","trace_id":"trace-123","timestamp_ms":1000,"attributes":{"tenant_id":"tenant-acme","payment_provider":"stripe","retry_count":2}}
{"kind":"metric","service":"checkout","name":"payment.authorization.latency_ms","trace_id":"trace-123","timestamp_ms":1100,"value":812.7,"tags":{"payment_provider":"stripe"}}
{"kind":"log","service":"checkout","name":"checkout.payment_failed","trace_id":"trace-123","timestamp_ms":1200,"severity":"ERROR","message":"payment authorization failed","fields":{"tenant_id":"tenant-acme"}}
```

Findings include severity, code, message, event path, contract path, and details when useful. Use `--format json` for machine-readable output or `--format sarif` on runtime/static finding commands for code-scanning upload. JSON findings are also annotated with taxonomy metadata: category, formal clause (for example `SAT.required-field` or `STRICT.signal-closed-world`), remediation, disclosure sensitivity, service-owner routing, SARIF-compatible level, and CI baseline keys. `python3 -m telemetry_contracts.cli taxonomy` emits the canonical taxonomy from `docs/finding_taxonomy.json`; with `--findings`, it summarizes which semantic clauses and categories appear in a concrete JSON report. `python3 -m telemetry_contracts.cli sarif --findings report.json` converts saved JSON finding or benchmark reports to SARIF 2.1.0.

## Observation model and satisfaction relation

`python3 -m telemetry_contracts.cli describe-model` prints the executable observation domain used by the checker. It maps spans, logs, metrics, resources, scopes, exemplars, timestamps, attributes, and provenance to the repository JSONL fields and the OTLP JSON fields currently normalized by `import-otlp`.

The core satisfaction relation is reported as `T ⊨ C`: a finite telemetry trace `T` satisfies a contract `C` when every well-formed contract obligation evaluates to true over observations relevant to `C.service`. For strict mode, this relation is strengthened with closed-world side conditions over service identity, declared signal names, declared event fields, and documented collector transformations. For alternative obligations, the executable clause is a finite disjunction: a required group is satisfied iff at least one option has a concrete witness event with every declared field; optional groups record acceptable evidence paths without failing absent telemetry. The model page defines how present, absent, malformed, partial, unknown, and transformed evidence is interpreted. Passing `--events` adds an artifact summary and a finite event-structure view, which is useful for checking what kinds, names, fields, correlation keys, timestamps, parent/child edges, log attachments, metric exemplars, and incident-window happens-before diagrams are actually present in a historical or current fixture.

## Public Python API

The package includes `py.typed` and exports stable embedding helpers from `telemetry_contracts`: `load_contract`, `load_jsonl`, `validate_events`, `check_sources`, `run_compiled_monitor`, `generate_incident_readiness_report`, `generate_service_owner_report`, `run_benchmark`, and `import_otlp`. These functions operate on plain dictionaries, lists, paths, and typed finding objects so downstream CI or notebooks can call the deterministic checks without shelling out:

```python
from telemetry_contracts import load_contract, load_jsonl, validate_events

contract = load_contract("examples/contracts/checkout.contract.json")
events = load_jsonl("examples/telemetry/passing.jsonl")
findings = validate_events(contract, events)
assert not findings
```

## Architecture

- `telemetry_contracts.core_semantics` implements the mechanizable small-step contract-evaluation model and reports denotation alignment with `validate_events`.
- `telemetry_contracts.monitor` compiles contract clauses to deterministic runtime monitors for finite JSONL streams and reports bounded sliding-window state.
- `telemetry_contracts.windows` groups concrete events and validation findings into trace/request/tenant/deployment/scenario/incident ownership windows.
- `telemetry_contracts.loader` loads JSON/YAML contracts, resolves relative `extends`/`inherits` chains, and reads JSONL events with explicit errors.
- `telemetry_contracts.schema` provides the canonical contract JSON Schema used by linting and tests.
- `telemetry_contracts.validator` checks emitted telemetry against signal, field, privacy/PII/secret transformation, correlation, temporal-sequence, temporal-property, hyperproperty, and alternative-obligation specifications, using an `EventIndex` for kind/name, service, correlation, and time-window lookups.
- `telemetry_contracts.abstract_domains` computes finite prototype domains used by the `abstract-domains` CLI.
- `telemetry_contracts.semantics` defines the observation-domain page, satisfaction-relation states, finite event structures, and artifact summaries used by `describe-model` and service-owner reports.
- `telemetry_contracts.alternatives` evaluates finite disjunctions over semantically equivalent evidence paths and emits witness/counterexample reports.
- `telemetry_contracts.assume_guarantee` evaluates layer-partitioned service, collector, environment, and on-call obligations over finite telemetry artifacts.
- `telemetry_contracts.cli lint-contract` validates contract schema semantics before events exist.
- `telemetry_contracts.static_checker` scans Python ASTs and supported source files (`.py`, `.js`, `.jsx`, `.ts`, `.tsx`, `.go`, `.java`, `.cs`, `.rb`, `.rs`) for expected instrumentation names, local constants/concatenations/templates/wrappers, source spans, OpenTelemetry API metadata, and telemetry/logging anti-patterns.
- `telemetry_contracts.scenario` defines diagnosability adequacy for incident questions and verifies minimum observations against emitted telemetry.
- `telemetry_contracts.equivalence` compares two traces by their scenario answerability signatures.
- `telemetry_contracts.preservation` checks pre/post transformation preservation for runtime obligations and scenario witnesses.
- `telemetry_contracts.refinement` implements the executable finite-contract refinement relation and JSON/Markdown reports.
- `telemetry_contracts.contract_diff` implements pull-request contract-diff summaries for obligation, privacy, and diagnosability-claim review.
- `telemetry_contracts.composition` analyzes inherited contract denotations and parent-refinement evidence for `compose-contract`.
- `telemetry_contracts.proof_obligations` instantiates formal proof-goal templates and links them to checker, assume-guarantee, semantics, hyperproperty, preservation, and benchmark evidence.
- `telemetry_contracts.semconv` checks declared and observed signal names/attributes against bounded OpenTelemetry HTTP, database, messaging, and metric-unit conventions plus contract-local semantic policies.
- `telemetry_contracts.incident_report` generates service-owner incident-readiness JSON/Markdown from the deterministic validator and scenario checks.
- `telemetry_contracts.service_report` generates owner-oriented coverage, failing-obligation, privacy-risk, collector/export, source-span, and remediation-priority reports.
- `telemetry_contracts.init_workflow` scaffolds a starter local contract project with owner metadata, CI gate script, fixtures, and incident-readiness outputs.
- `telemetry_contracts.doctor` checks local runtime, optional dependency, path, and CI assumptions before automation.
- `telemetry_contracts.benchmark` runs benchmark suites and computes summary/label metrics.
- `telemetry_contracts.taxonomy` emits the finding-rule catalog and summarizes observed findings by code, category, formal clause, SARIF level, and service-owner route.
- `telemetry_contracts.sarif` converts validation, static, and benchmark finding reports to SARIF 2.1.0 with taxonomy-backed rule metadata.
- `telemetry_contracts.ci_gate` evaluates saved finding reports against exact owned/expiring baselines so CI can block only new high-severity findings.
- `telemetry_contracts.regenerate` writes deterministic public report artifacts and a paper-style benchmark table from checked-in benchmark config.
- `telemetry_contracts.claims` emits a claims-to-evidence matrix linking public claims to artifacts, fixtures, tests, and limitations.
- `telemetry_contracts.explain` renders finding-code explanations with formal meaning, practical impact, example trace shape, concrete fixes, CI baseline metadata, and optional concrete examples mined from JSON reports.
- `telemetry_contracts.cli` exposes `init`, `doctor`, `validate` (including `--strict`), `import-otlp`, `export-otlp`, `analyze-collector-export`, `semconv`, `monitor`, `static`, `scenario`, `equivalence`, `preservation`, `refinement`, `compose-contract`, `proof-obligations`, `describe-model`, `evaluate-semantics`, `report incident-readiness`, `report service-owner`, `report alternative-obligations`, `report assume-guarantee`, `report event-windows`, `benchmark`, `benchmark-diff`, `taxonomy`, `sarif`, `ci-gate`, `regenerate-artifacts`, `claims-matrix`, and `explain` commands.
- `examples/` contains the checkout contract, sample telemetry, source instrumentation, and scenario prompt.
- `benchmarks/` contains runnable benchmark configs.
- `case_studies/` contains public historical fixtures and metadata.
- `tests/` covers parser behavior, validator behavior, CLI behavior, static checks, scenarios, benchmark behavior, and examples.

## Example workflow

1. Write a contract for the telemetry needed to debug checkout failures.
2. Run static checks in CI to catch missing instrumentation names, incomplete error-path evidence, and risky telemetry logging before execution.
3. Run service tests or staging traffic and export JSONL telemetry.
4. Validate emitted telemetry against the contract.
5. Add scenario checks for incident questions such as: “Can on-call identify tenant, cart, provider, retry count, and error class for a payment timeout?”

## CI and code-scanning workflow

`examples/ci/` contains a GitHub Actions template, generic shell script, pre-commit hook example, sample finding report, and owned expiring baseline. The CI pattern is:

```bash
python3 -m telemetry_contracts.cli validate --contract service.contract.json --events telemetry.jsonl --format sarif > telemetry-contracts.sarif
python3 -m telemetry_contracts.cli static --contract service.contract.json src --format json > telemetry-contracts.static.json
python3 -m telemetry_contracts.cli ci-gate --findings telemetry-contracts.static.json --baseline examples/ci/baseline.example.json --fail-on error
```

Baselines match exact `code`, `path`, `contract_path`, `event_index`, or `path_suffix` keys and may include `owner`, `expires_at`, and `justification`; expired entries fail the gate.

## Real-world finding workflow

The repo is designed to be run on real telemetry captures, not only synthetic fixtures. Export OTLP JSON or newline-delimited OTLP JSON from an OpenTelemetry Collector, convert it, inspect importer diagnostics, then validate the converted JSONL. The JSONL loader processes one collector export record at a time, so event streaming is bounded by the largest single OTLP record rather than the whole capture. The collector analysis command summarizes dropped evidence, schema surprises, finite-window cardinality risks, PII/secret patterns, temporality, and unsupported features before users make contract claims from a partial export:

```bash
python3 -m telemetry_contracts.cli import-otlp --input otlp-export.json --output captured.jsonl --diagnostics-output captured.diagnostics.json
python3 -m telemetry_contracts.cli import-otlp --input-format jsonl --input otlp-stream.jsonl --output captured-stream.jsonl
python3 -m telemetry_contracts.cli analyze-collector-export --input otlp-export.json --format markdown
python3 -m telemetry_contracts.cli export-otlp --events captured.jsonl --output captured.roundtrip.otlp.json
python3 -m telemetry_contracts.cli validate --contract service.contract.json --events captured.jsonl --format json
```

`examples/otlp/collector_mixed_signals.*` is an OpenTelemetry collector-style fixture with a correlated span, histogram exemplar, and structured log; its generated JSONL validates against `collector_mixed_signals.contract.json`, and the alias JSONL fixture demonstrates streaming snake_case normalization diagnostics. `examples/otlp/collector_coverage_all_signals.*` covers spans, logs, sums, gauges, histograms, exponential histograms, summaries, exemplars, links, span events, resource/scope metadata, temporality, dropped evidence, unsupported OTLP features, and PII/cardinality analysis inputs. `docs/collector_file_exporter.md` gives a vendor-neutral OpenTelemetry Collector file-exporter workflow, and `examples/otlp/collector_pipeline_*` shows redaction, sampling, aggregation, and routing preservation checks over finite before/after artifacts.

`examples/real_world/otel_checkout_missing_tenant.*` is a case-study fixture modeled on a common production observability bug: payment failure traces and logs exist, but neither carries the tenant identifier needed to scope blast radius. The validator confirms the bug by reporting `telemetry.missing_field` for `tenant_id`.

`case_studies/current/owasp_securetea_signin/` is a reproducible public-code static and finite-trace hyperproperty case study. It analyzes OWASP SecureTea Project's `react_gui/src/views/Signin.js` at commit `7a2da8756e6addbe379ae9b23905dcdbe68b3814`, produces labeled `static.secret_logging` findings for logging a password value and a cookie value, and validates a bounded reconstructed console-log JSONL fixture that produces three `telemetry.hyper_pii_disclosure` findings. The reconstructed values are synthetic placeholders derived from public code paths, not private operational data. The repository records source URL, retrieval date, commit, file SHA, license, generated reports, and exact reproduction commands.


## Benchmark harness

Run the built-in benchmark suite:

```bash
python3 -m telemetry_contracts.cli benchmark --config benchmarks/builtin.json --format json
python3 -m telemetry_contracts.cli benchmark --config benchmarks/builtin.json --format markdown
```

A benchmark config is JSON with a `cases` list. Each case can point to one contract or multiple contracts plus JSONL events, source paths, import diagnostics, or a mix of those inputs; optional scenario ids; optional `strict: true`; optional dataset metadata/provenance; optional tags/check types/failure modes/semantic features; and optional `expected_findings` labels. Paths are resolved relative to the config file, so external datasets can be benchmarked without changing package code. Reports include runtime/static/scenario/strict/import-diagnostic check flags, number of contracts, events, findings, findings by code/severity, label precision/recall/F1, runtime and runtime-per-1K-events, findings-per-1K-events, observed memory envelope, dataset ids, import loss rate, grouped remediations with effort/benefit hints, and pass/fail. Use `--case-id`, `--tag`, `--check-type`, `--dataset`, `--expected-failure-mode`, `--semantics-feature`, `--service-owner`, or `--disclosure-status` to slice a suite, and `benchmark-diff` to compare two saved JSON benchmark reports. The checked-in built-in benchmark currently covers 10 cases, 8 contract-backed cases, 30 runtime events, 35 labeled findings, and 1.0 precision/recall/F1 on all labeled cases, including four `telemetry.hyper_pii_disclosure` findings, collector dropped-evidence/unsupported-feature diagnostics, and one labeled partial OTLP import diagnostic.

To refresh checked-in public artifacts from current fixtures:

```bash
python3 -m telemetry_contracts.cli regenerate-artifacts --write --format markdown
python3 -m telemetry_contracts.cli claims-matrix --output docs/claims_evidence_matrix.json
```

This rewrites `reports/current_impact.{json,md,sarif}`, `reports/current_impact_taxonomy.{json,md}`, `reports/paper_tables.md`, and `docs/claims_evidence_matrix.json`.

## Public historical case study

`case_studies/gitlab_2017_database_outage/` contains a reconstructed fixture derived from GitLab's public January 31, 2017 database outage reports:

- <https://about.gitlab.com/blog/postmortem-of-database-outage-of-january-31/>
- <https://about.gitlab.com/blog/2017/02/01/gitlab-dot-com-database-incident/>

The fixture is clearly labeled as reconstructed, not raw GitLab telemetry. It encodes public facts such as replication lag/failure, a destructive command intended for the secondary but run on the primary, failed pg_dump backups from a PostgreSQL version mismatch, rejected cron notifications, and recovery from a roughly six-hour-old LVM snapshot. Its contract also includes a required alternative obligation for destructive-command location evidence, temporal properties for backup-failure alert response and reconstruction ordering, and assume-guarantee obligations assigning missing guard/backup evidence to service, collector, environment, or on-call layers. `reports/gitlab_2017_temporal_logic_validation.json` shows that the degraded sampled/exported derivative reports `telemetry.temporal_response` when the failed-backup metric has no `backup.pg_dump.failed` response witness within 1500ms; `reports/gitlab_2017_event_windows.md` localizes that response failure to `incident:slice_ms=2000` while leaving the absent alert signal in `global:contract=all`; `reports/gitlab_2017_assume_guarantee_sampled.md` turns the same bounded derivative into layer-specific counterexamples. `reports/gitlab_2017_refinement.json` shows that the reconstructed incident contract refines the checked-in broader team baseline, while `reports/gitlab_2017_refinement_weakened.json` shows a deliberate weakened candidate losing required alert-delivery evidence. `reports/gitlab_2017_contract_diff.md` renders that weakened-candidate comparison as a PR-oriented diff and flags the removed `alert_delivered` obligation for review. `case_studies/gitlab_2017_database_outage/composed_contract.json` extends `org_incident_policy.contract.json`; `reports/gitlab_2017_composition.json` records `valid=true` with five inherited signal obligations and zero parent-refinement findings, and `reports/gitlab_2017_composed_validation.json` shows the composed contract produces the same bounded historical findings as the service contract over reconstructed events.

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

`reports/gitlab_2017_strict_validation.json` records 14 findings on that bounded derivative, including one undeclared signal, one unmodeled collector service, two unexpected fields, and one undocumented collector transformation. `reports/gitlab_2017_strict_explain.md` explains the `telemetry.strict_unexpected_field` code against those concrete observed examples. This demonstrates closed-world utility on a historical public-data reconstruction without claiming access to GitLab private telemetry.

Generate the checked-in small-step semantic-evaluation report for the same drift derivative:

```bash
python3 -m telemetry_contracts.cli evaluate-semantics \
  --contract case_studies/gitlab_2017_database_outage/contract.json \
  --events case_studies/gitlab_2017_database_outage/reconstructed_events_strict_drift.jsonl \
  --strict \
  --format markdown \
  --output reports/gitlab_2017_semantic_evaluation.md \
  --fail-on never
```

`reports/gitlab_2017_semantic_evaluation.md` records `aligned_with_checker=true`: the small-step denotation and `validate_events` both produce the same 14 finding signatures over 7 input events and 12 small steps, including temporal-property and strict closed-world rules. This is mechanized alignment evidence for this implementation and fixture, not a proof about all possible telemetry systems.

Generate the checked-in compiled runtime-monitor report for the sampled/exported derivative:

```bash
python3 -m telemetry_contracts.cli monitor \
  --contract case_studies/gitlab_2017_database_outage/contract.json \
  --events case_studies/gitlab_2017_database_outage/reconstructed_events_sampled_missing_alert.jsonl \
  --format markdown \
  --output reports/gitlab_2017_runtime_monitor.md \
  --fail-on never
```

`reports/gitlab_2017_runtime_monitor.md` records `bounded-runtime-monitor-v1` over 4 reconstructed events, compiling 5 signal monitors and 2 temporal-property monitors. It reports the same bounded backup-alert `telemetry.temporal_response` counterexample as the batch validator, with an observed memory envelope of 2 active groups, 1 pending response, and 0 sequence-window events. This is finite-trace runtime-monitor evidence over checked-in reconstructed public facts, not a production memory guarantee for arbitrary traffic.

Generate the checked-in event-window report for the same sampled/exported derivative:

```bash
python3 -m telemetry_contracts.cli report event-windows \
  --contract case_studies/gitlab_2017_database_outage/contract.json \
  --events case_studies/gitlab_2017_database_outage/reconstructed_events_sampled_missing_alert.jsonl \
  --dimension incident \
  --incident-slice-ms 2000 \
  --format markdown \
  --output reports/gitlab_2017_event_windows.md \
  --fail-on never
```

`reports/gitlab_2017_event_windows.md` records `event-window-grouping-v1` over the same 4 reconstructed events and 10 validation findings. It localizes the backup-alert `telemetry.temporal_response` counterexample to `incident:slice_ms=2000`, keeps the missing `backup.pg_dump.failed` signal in `global:contract=all`, and reports five windows total. This is finite-artifact ownership localization, not evidence about GitLab private ownership routing.

Generate the checked-in proof-obligation report for the same public reconstruction, its strict drift derivative, the sampled/exported derivative, and the built-in benchmark labels:

```bash
python3 -m telemetry_contracts.cli proof-obligations \
  --contract case_studies/gitlab_2017_database_outage/contract.json \
  --events case_studies/gitlab_2017_database_outage/reconstructed_events_strict_drift.jsonl \
  --strict \
  --before-events case_studies/gitlab_2017_database_outage/reconstructed_events.jsonl \
  --after-events case_studies/gitlab_2017_database_outage/reconstructed_events_sampled_missing_alert.jsonl \
  --benchmark-config benchmarks/builtin.json \
  --format markdown \
  --output reports/gitlab_2017_proof_obligations.md
```

`reports/gitlab_2017_proof_obligations.md` catalogs 27 feature groups and 99 instantiated obligations for those supplied artifacts: 82 discharged, 14 violated, and 3 pending refinement templates. The violations are bounded to the checked-in strict-drift, assume-guarantee, and sampled/exported fixtures; the report does not claim access to GitLab private telemetry or prove universal monitor soundness.

Generate the checked-in semantic-convention lint report for the reconstructed GitLab metric/log/span names and event attributes:

```bash
python3 -m telemetry_contracts.cli semconv \
  --contract case_studies/gitlab_2017_database_outage/contract.json \
  --events case_studies/gitlab_2017_database_outage/reconstructed_events.jsonl \
  --format markdown \
  --output reports/gitlab_2017_semconv_lint.md \
  --fail-on never
```

`reports/gitlab_2017_semconv_lint.md` records 7 warning-level `semconv.*` findings over 5 reconstructed events. The report cites OpenTelemetry database/metric conventions and a contract-local policy requiring `db.system.name="postgresql"` on the `postgres.replication.lag_bytes` metric, plus exact remediation to add the attribute and declare or normalize metric units. This is naming/attribute quality evidence over the checked-in reconstruction, not a claim about GitLab private instrumentation.

Generate the checked-in refinement reports over the same public reconstruction:

```bash
python3 -m telemetry_contracts.cli refinement \
  --base-contract case_studies/gitlab_2017_database_outage/refinement_base_contract.json \
  --candidate-contract case_studies/gitlab_2017_database_outage/contract.json \
  --format markdown \
  --output reports/gitlab_2017_refinement.md

python3 -m telemetry_contracts.cli refinement \
  --base-contract case_studies/gitlab_2017_database_outage/refinement_base_contract.json \
  --candidate-contract case_studies/gitlab_2017_database_outage/refinement_candidate_weakened_contract.json \
  --format markdown \
  --output reports/gitlab_2017_refinement_weakened.md \
  --fail-on never

python3 -m telemetry_contracts.cli contract-diff \
  --base-contract case_studies/gitlab_2017_database_outage/refinement_base_contract.json \
  --candidate-contract case_studies/gitlab_2017_database_outage/refinement_candidate_weakened_contract.json \
  --format markdown \
  --output reports/gitlab_2017_contract_diff.md \
  --fail-on never
```

The passing report records `refines=true` with zero findings for the reconstructed GitLab contract against a broader checked-in baseline. The weakened-candidate report records `refines=false` and a concrete `refinement.required_field_removed` finding for removed backup alert-delivery evidence. The companion `contract-diff` report records one `contract_diff.removed_obligation` finding for the same `alert_delivered` field, formatted for pull-request review. These are finite artifact comparisons over public incident-derived fixtures, not claims about GitLab private contract history.

Generate the checked-in composition/inheritance report over the same public reconstruction:

```bash
python3 -m telemetry_contracts.cli compose-contract \
  --contract case_studies/gitlab_2017_database_outage/composed_contract.json \
  --format markdown \
  --output reports/gitlab_2017_composition.md

python3 -m telemetry_contracts.cli validate \
  --contract case_studies/gitlab_2017_database_outage/composed_contract.json \
  --events case_studies/gitlab_2017_database_outage/reconstructed_events.jsonl \
  --format json --fail-on never > reports/gitlab_2017_composed_validation.json
```

The composition report records `valid=true`, five inherited signal obligations, five overridden service-specific signal clauses, and zero parent-refinement findings for the resolved GitLab reconstruction. The validation report confirms the inherited contract is immediately executable on the checked-in historical fixture; findings remain bounded to reconstructed public facts.

Generate the checked-in alternative-obligation witness report:

```bash
python3 -m telemetry_contracts.cli report alternative-obligations \
  --contract case_studies/gitlab_2017_database_outage/contract.json \
  --events case_studies/gitlab_2017_database_outage/reconstructed_events.jsonl \
  --format markdown \
  --output reports/gitlab_2017_alternative_obligations.md
```

The report records `pass=true`: the structured log witnesses the destructive-command location obligation, while the equivalent span option is absent without creating a duplicate false positive.

Generate the checked-in assume-guarantee layer report for the sampled/exported derivative:

```bash
python3 -m telemetry_contracts.cli report assume-guarantee \
  --contract case_studies/gitlab_2017_database_outage/contract.json \
  --events case_studies/gitlab_2017_database_outage/reconstructed_events_sampled_missing_alert.jsonl \
  --format markdown \
  --output reports/gitlab_2017_assume_guarantee_sampled.md \
  --fail-on never
```

The report records 8 layer-partitioned obligations over the bounded public reconstruction: 3 satisfied and 5 violated. The environment evidence obligations are satisfied, while service, collector-preservation, and on-call obligations carry concrete `ag.*` counterexamples. These are evidence claims about the checked-in reconstructed artifacts, not claims about GitLab private telemetry.

## Current public-code case study

`case_studies/current/owasp_securetea_signin/` contains a public-code defensive analysis fixture:

- Source: <https://github.com/OWASP/SecureTea-Project/blob/7a2da8756e6addbe379ae9b23905dcdbe68b3814/react_gui/src/views/Signin.js>
- Retrieval date: 2026-05-29
- Finding type: potential telemetry privacy/security anti-patterns in public sample code (`static.secret_logging`) plus finite-trace PII non-disclosure witnesses (`telemetry.hyper_pii_disclosure`) over a bounded reconstructed console-log fixture, not an exploit or vulnerability disclosure.
- Generated evidence: `reports/current_impact.json`, `reports/current_impact.md`, and `reports/owasp_securetea_hyperproperties.json`.

## LLM-process separation note

The idea document suggests LLMs can help generate realistic incident questions, propose telemetry requirements, and mutate services to create diagnosability bugs. This repository keeps that process separate from the correctness mechanism: contracts are explicit files, telemetry is concrete JSONL, and pass/fail results come from deterministic validators. No model call is required to run or trust the checks.

## Limitations

- Static checking now uses Python AST extraction plus lightweight source heuristics for JavaScript, TypeScript, Go, Java, C#, Ruby, and Rust. It resolves local constants, simple concatenation/templates, and common telemetry APIs, but it is not a full interprocedural compiler analysis and may miss dynamic instrumentation.
- Semantic-convention linting intentionally covers a bounded subset of OpenTelemetry HTTP, database, messaging, and metric-unit guidance plus explicit local policies; it is not a complete semantic-convention compliance suite.
- OTLP support covers common JSON and JSONL exports for spans, metrics, and logs, including resource/scope metadata, span links/events/status, structured log bodies, observed timestamps, metric exemplars, alias normalization, provenance paths, collector-export analysis, round-trip JSON conversion, and importer diagnostics; protobuf/gRPC collector ingestion is future work.
- Cardinality is checked over the supplied sample window, not a production time series backend.
- Sampling and retention stubs are linted for machine-readable contract shape, but not verified against live collector or backend configuration.
- Strict mode is a closed-world check over the supplied finite event artifact; escape hatches are explicit but do not prove a collector pipeline is correctly configured.
- Scenario matching is intentionally simple; robust incident-question synthesis is future work.
- Temporal-property monitoring is finite-trace and bounded by supplied timestamps/grouping keys; it is not an unbounded temporal-logic model checker.
- Hyperproperty monitoring is finite-artifact and pair/set bounded by supplied JSONL events; it identifies concrete privacy-risk witnesses, not universal non-interference over all executions.
- Assume-guarantee reports assign finite-artifact findings to declared layers; they do not prove organizational accountability or production workflow behavior beyond the supplied contract and trace.
- Refinement and composition reports compare finite checked-in contracts. The checker is conservative about regex/arbitrary predicate implication and does not prove that an organization's private contract evolution was safe.
- Incident-readiness scores are computed over the supplied finite artifact; they are useful for CI trend and review, not a guarantee of production incident success.
- The small-step semantic evaluator is an executable artifact aligned with the current checker through tests and reports; it is not a separately machine-checked theorem prover.
- The compiled runtime monitor reports an implementation-level memory envelope over finite JSONL streams. Bounded-response and temporal-sequence state is window-bounded by declared timestamps and grouping keys, but the tool is not a formally verified streaming monitor for all possible collector delivery orders.
- Event-window grouping is deterministic ownership localization over observed finite event keys plus optional bounded time slices. Findings without event witnesses deliberately remain global instead of guessing ownership.
- Proof-obligation reports are executable evidence checklists over finite artifacts. They are useful for review and reproducibility; dedicated contract-version refinement evidence is produced by the `refinement` command.

## Development

```bash
python3 -m pytest
make smoke
```

Optional YAML support:

```bash
python3 -m pip install '.[yaml]'
```
