# Benchmark: built-in telemetry contracts benchmark

- Pass: `true`
- Cases: 10
- Contracts: 8
- Events: 30
- Findings: 35
- Runtime: 25.419 ms
- Runtime per K events: 847.3 ms
- Findings per K events: 1166.666667
- Import loss rate: 1.0
- Label precision/recall/F1: 1.0 / 1.0 / 1.0
- Findings by code: `{"otlp.dropped_evidence": 2, "otlp.malformed_record": 1, "otlp.unsupported_metric": 1, "otlp.unsupported_top_level": 1, "scenario.missing_field": 3, "static.missing_correlation": 1, "static.secret_logging": 3, "static.unbounded_label": 1, "telemetry.allowed_values": 4, "telemetry.cardinality": 1, "telemetry.correlation_missing": 2, "telemetry.hyper_pii_disclosure": 4, "telemetry.missing_field": 3, "telemetry.numeric_max": 2, "telemetry.sensitive_value": 1, "telemetry.temporal_absence": 1, "telemetry.temporal_deadline": 1, "telemetry.temporal_order": 1, "telemetry.temporal_response": 1, "telemetry.temporal_safety": 1}`
- Findings by severity: `{"error": 27, "info": 1, "warning": 7}`

| Case | Tags | Checks | Pass | Events | Findings | Validation pass | Label precision | Label recall | Label F1 | Runtime ms | Findings/K events | Import loss |
| --- | --- | --- | --- | ---: | ---: | --- | ---: | ---: | ---: | ---: | ---: | ---: |
| checkout-payment-timeout-pass | none | runtime,scenario | `true` | 5 | 0 | `true` | n/a | n/a | n/a | 1.44 | 0.0 | 0.0 |
| gitlab-2017-database-outage-reconstructed | none | runtime,scenario | `true` | 5 | 12 | `false` | 1.0 | 1.0 | 1.0 | 1.545 | 2400.0 | 0.0 |
| owasp-securetea-signin-current-static-and-hyperproperty | none | runtime,static | `true` | 3 | 5 | `false` | 1.0 | 1.0 | 1.0 | 6.326 | 1666.666667 | 0.0 |
| otlp-collector-mixed-signals-pass | none | runtime | `true` | 3 | 0 | `true` | n/a | n/a | n/a | 0.894 | 0.0 | 0.0 |
| otlp-collector-coverage-analysis | otlp,collector,diagnostics | import_diagnostics | `true` | 0 | 4 | `true` | 1.0 | 1.0 | 1.0 | 0.033 | 0.0 | 3.0 |
| temporal-logic-properties-fail | none | runtime | `true` | 8 | 5 | `false` | 1.0 | 1.0 | 1.0 | 0.913 | 625.0 | 0.0 |
| benchmark-missing-correlation | correlation,diagnosability,runtime | runtime | `true` | 3 | 2 | `false` | 1.0 | 1.0 | 1.0 | 0.692 | 666.666667 | 0.0 |
| benchmark-cardinality-budget | cardinality,operability,runtime | runtime | `true` | 2 | 1 | `true` | 1.0 | 1.0 | 1.0 | 0.769 | 500.0 | 0.0 |
| benchmark-privacy-static-source | privacy,security,static,runtime | runtime,static | `true` | 1 | 5 | `false` | 1.0 | 1.0 | 1.0 | 1.31 | 5000.0 | 0.0 |
| benchmark-partial-otlp-diagnostics | otlp,import,diagnostics | import_diagnostics | `true` | 0 | 1 | `true` | 1.0 | 1.0 | 1.0 | 0.012 | 0.0 | 0.333333 |

## Top remediations

| Severity | Semantic property | Owner | Effort | Benefit | Findings | Remediation |
| --- | --- | --- | --- | --- | ---: | --- |
| error | privacy-security | contract service owner | medium | reduces sensitive telemetry exposure | 4 | Redact, hash, tokenize, bucket, or omit sensitive values before they reach public telemetry sinks. |
| error | schema | contract service owner | medium | improves benchmark semantic coverage | 4 | Normalize the field to one of the declared allowed values. |
| error | diagnosability | contract service owner | medium | restores incident question evidence | 3 | Attach the required attribute/tag/field to the signal. |
| warning | input | contract service owner | small-to-medium | bounds importer claim validity | 2 | Inspect collector/exporter dropped-count fields before relying on complete contract evidence. |
| warning | diagnosability | contract service owner | small-to-medium | restores incident question evidence | 1 | Include a trace_id, request_id, or configured correlation field in error logs. |
| warning | operability | contract service owner | small-to-medium | reduces noisy or costly telemetry | 1 | Bucket, hash, drop, or bound labels with excessive cardinality. |
| info | input | contract service owner | small-to-medium | bounds importer claim validity | 1 | Document unsupported top-level OTLP fields as validity threats or add bounded importer support. |

