# JSON report schema documentation

The files in `docs/report_schemas/` document the stable envelope for public reports emitted by this prototype. They are intentionally permissive where individual finding details vary by command, but they require the fields that downstream CI, SARIF conversion, claims evidence, and benchmark accounting depend on.

| Report | Schema | Producer | Checked fixture |
| --- | --- | --- | --- |
| Findings list | `finding.schema.json` | `validate`, `static`, `semconv`, report subcommands | `reports/current_impact.json` nested findings |
| Import diagnostics | `import_diagnostics.schema.json` | `import-otlp --diagnostics-output` | `examples/otlp/collector_coverage_all_signals.diagnostics.json` |
| Scenario report | `scenario_report.schema.json` | `scenario` / incident-readiness scenario sections | `reports/gitlab_2017_incident_readiness.json` |
| Benchmark report | `benchmark_report.schema.json` | `benchmark --format json` | `reports/current_impact.json` |
| Service-owner report | `service_owner_report.schema.json` | `report service-owner --format json` | `reports/gitlab_2017_service_owner_sampled.json` |
| Claims/evidence matrix | `claims_evidence_matrix.schema.json` | `claims-matrix --format json` | `docs/claims_evidence_matrix.json` |

These schemas are documentation and compatibility guards, not a substitute for running the deterministic commands in the replication guide.
