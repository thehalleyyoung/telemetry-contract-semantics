# Operational telemetry scorecards and authoring guide

This guide turns the repository's deterministic contract checks into operational scorecards. Each scorecard is bounded by checked-in contracts, JSONL/OTLP fixtures, and source files; it is not a claim about private production telemetry.

## Diagnosability scorecards

Use these scorecards for HTTP APIs, batch jobs, message consumers, cron tasks, and stateful workers. The service-owner report and incident-readiness report together:

```bash
python3 -m telemetry_contracts.cli report service-owner \
  --contract case_studies/gitlab_2017_database_outage/contract.json \
  --events case_studies/gitlab_2017_database_outage/reconstructed_events_sampled_missing_alert.jsonl \
  --scenario restore-readiness \
  --format markdown --fail-on never

python3 -m telemetry_contracts.cli report incident-readiness \
  --contract case_studies/gitlab_2017_database_outage/contract.json \
  --events case_studies/gitlab_2017_database_outage/reconstructed_events.jsonl \
  --scenario restore-readiness \
  --format markdown --fail-on never
```

| Workload | Adequacy criteria | Primary clauses | Fixture proof point |
| --- | --- | --- | --- |
| HTTP APIs | Request span has route/status, error logs carry trace/request correlation, latency metric has unit/range, privacy fields are transformed. | `SAT.required-field`, `SAT.correlation-presence`, `SAT.unit`, `SAT.privacy-preservation` | `examples/contracts/checkout.contract.json` with `examples/telemetry/*.jsonl` |
| Batch jobs | Start/end/failure events are ordered, retry count is bounded, remediation is present, missing terminal evidence fails. | `SAT.temporal-order`, `SAT.temporal-deadline`, `STATIC.remediation-evidence` | `examples/temporal_logic/` |
| Message consumers | Queue depth/lag is bounded, message id or trace id joins spans/logs/metrics, poison-message handling is observable. | `SAT.cardinality-bound`, `SAT.correlation-intersection`, `ADEQ.required-field` | `case_studies/gitlab_2017_database_outage/contract.json` |
| Cron tasks | Expected run, duration, outcome, and alert evidence appear inside a time window. | `SAT.temporal-response`, `SAT.temporal-window` | `reports/gitlab_2017_temporal_logic_validation.json` |
| Stateful workers | Saturation, pool/cache/replica state, rollback/deployment id, and on-call action evidence are present. | `AG.required-field`, `PRES.adequacy-field`, `STRICT.field-closed-world` | GitLab 2017 reconstructed and sampled derivatives |

Interpret a scorecard as actionable if the failing finding includes a stable code, owner, source/contract path, and remediation. Event-less missing-signal findings remain global because no finite event window can localize absent evidence.

## Privacy-safe design examples

| Workflow | Safe telemetry pattern | Avoid | Checked command |
| --- | --- | --- | --- |
| Authentication | Tokenize account identifiers, log bounded error codes and trace ids. | Raw emails, passwords, bearer tokens, session cookies. | `python3 -m telemetry_contracts.cli benchmark --config benchmarks/builtin.json --tag privacy --format markdown` |
| Payments | Emit amount bucket/currency/status and idempotency surrogate; keep PAN/CVV out of events. | Card numbers, full billing addresses, prose-only failure logs. | `python3 -m telemetry_contracts.cli validate --contract examples/contracts/checkout.contract.json --events examples/telemetry/passing.jsonl` |
| Tenant isolation | Use stable tenant buckets or hashed tenant ids plus trace ids. | Raw tenant identifiers in public logs or cross-tenant trace keys. | `python3 -m telemetry_contracts.cli validate --contract examples/hyperproperties/contract.json --events examples/hyperproperties/failing.jsonl --fail-on never` |
| Incident retrospectives | Preserve reconstruction status, source citations, limitations, and transformations. | Treating reconstructed data as original production telemetry. | `python3 -m telemetry_contracts.cli claims-matrix --format markdown` |
| Support workflows | Include ticket-safe correlation ids and bounded remediation hints. | Free-form payload previews or customer secrets. | `python3 -m telemetry_contracts.cli report service-owner --contract case_studies/gitlab_2017_database_outage/contract.json --events case_studies/gitlab_2017_database_outage/reconstructed_events_sampled_missing_alert.jsonl --scenario restore-readiness --format markdown --fail-on never` |
| Audit trails | Emit actor role, action, outcome, policy version, and hash/token surrogates. | Raw payload bodies or unverifiable timestamp-only causality. | `python3 -m telemetry_contracts.cli report event-windows --contract case_studies/gitlab_2017_database_outage/contract.json --events case_studies/gitlab_2017_database_outage/reconstructed_events_sampled_missing_alert.jsonl --dimension incident --incident-slice-ms 2000 --format markdown --fail-on never` |

## Operational ranges to encode

| Range | Contract location | Failure surfaced as |
| --- | --- | --- |
| Latency | Metric `value` or field `max` with `unit: ms`. | `telemetry.numeric_max`, `contract.unit` |
| Retry count | Span/log field with integer `min`/`max`. | `telemetry.numeric_max` |
| Queue depth | Metric value or field with bounded `max`. | `telemetry.numeric_max` |
| Saturation | Gauge percent with `min: 0`, `max: 100`, `unit: percent`. | `telemetry.unit`, `telemetry.numeric_max` |
| Error budget | Metric with `unit: percent` and scenario requirement. | `scenario.missing_field` |
| Collector drop rate | OTLP diagnostics `invalidating_diagnostics / records`. | Benchmark `import_loss_rate`, `otlp.dropped_evidence` |
| Sampling budget | `metadata.sampling` and transformation-preservation scenarios. | `preservation.contract_obligation` |

## Authoring anti-patterns

- Ambiguous names: prefer `checkout.payment.timeout` over `timeout`.
- Unit-free metrics: declare `unit` and descriptions for source/static checks.
- Unbounded cardinality: bucket/hash user-controlled labels and declare cardinality budgets.
- PII previews: forbid raw emails, phone numbers, tokens, tenant ids, and payload previews unless transformed.
- Timestamp-only causality: use parent span ids, links, exemplars, and correlation keys.
- Prose-only remediation: encode `remediation_hint`, `retryable`, owner, and scenario fields.

## CI and review integration

| Surface | Command or artifact |
| --- | --- |
| pytest | `python3 -m pytest -q` |
| Make | `make smoke` |
| GitHub Actions | `examples/ci/github-actions.yml` |
| Generic CI | `examples/ci/generic-ci.sh` |
| Artifact upload | Write command output with `--output reports/<name>.json` or `.md`. |
| SARIF consumers | `python3 -m telemetry_contracts.cli sarif --findings examples/ci/static_findings.example.json` |
| Incident review | Attach service-owner, event-window, preservation, and claims-matrix reports. |
| Responsible disclosure | Keep privacy/security outputs bounded, redacted, owner-routed, and cite only public inputs. |

## OTLP importer limitations as report validity threats

The importer documents unsupported or lossy inputs as diagnostics instead of hiding them. Treat these as validity threats when a report claims complete evidence:

- Malformed JSONL records can be skipped with `otlp.malformed_record`.
- Dropped span/log/metric counts become `otlp.dropped_evidence`.
- Unsupported metrics or top-level fields become `otlp.unsupported_metric` or `otlp.unsupported_top_level`.
- JSON/JSONL collector exports are supported; protobuf/gRPC ingestion and vendor backend queries are outside this prototype.

Validate the limitation surface with:

```bash
python3 -m telemetry_contracts.cli analyze-collector-export \
  --input examples/otlp/collector_coverage_all_signals.otlp.json \
  --format markdown
python3 -m telemetry_contracts.cli benchmark \
  --config benchmarks/builtin.json --check-type import_diagnostics --format markdown
```
