# Benchmark: built-in telemetry contracts benchmark

- Pass: `true`
- Cases: 13
- Contracts: 23
- Events: 68
- Findings: 67
- Runtime: 26.897 ms
- Runtime per K events: 395.544118 ms
- Findings per K events: 985.294118
- Import loss rate: 1.0
- Label precision/recall/F1: 1.0 / 1.0 / 1.0
- Findings by code: `{"otlp.dropped_evidence": 2, "otlp.malformed_record": 1, "otlp.unsupported_metric": 1, "otlp.unsupported_top_level": 1, "scenario.missing_field": 3, "static.missing_correlation": 2, "static.pii_logging": 3, "static.secret_logging": 4, "static.unbounded_label": 1, "static.unsafe_payload_preview": 1, "telemetry.allowed_values": 4, "telemetry.cardinality": 1, "telemetry.correlation_missing": 2, "telemetry.forbidden_pattern": 2, "telemetry.hyper_pii_disclosure": 4, "telemetry.missing_field": 17, "telemetry.missing_signal": 1, "telemetry.numeric_max": 2, "telemetry.privacy_transformation": 5, "telemetry.sensitive_value": 5, "telemetry.temporal_absence": 1, "telemetry.temporal_deadline": 1, "telemetry.temporal_order": 1, "telemetry.temporal_response": 1, "telemetry.temporal_safety": 1}`
- Findings by severity: `{"error": 57, "info": 1, "warning": 9}`

| Case | Tags | Checks | Pass | Events | Findings | Validation pass | Label precision | Label recall | Label F1 | Runtime ms | Findings/K events | Import loss |
| --- | --- | --- | --- | ---: | ---: | --- | ---: | ---: | ---: | ---: | ---: | ---: |
| checkout-payment-timeout-pass | none | runtime,scenario | `true` | 5 | 0 | `true` | n/a | n/a | n/a | 1.199 | 0.0 | 0.0 |
| gitlab-2017-database-outage-reconstructed | none | runtime,scenario | `true` | 5 | 12 | `false` | 1.0 | 1.0 | 1.0 | 1.215 | 2400.0 | 0.0 |
| owasp-securetea-signin-current-static-and-hyperproperty | none | runtime,static | `true` | 3 | 6 | `false` | 1.0 | 1.0 | 1.0 | 4.353 | 2000.0 | 0.0 |
| otlp-collector-mixed-signals-pass | none | runtime | `true` | 3 | 0 | `true` | n/a | n/a | n/a | 0.461 | 0.0 | 0.0 |
| otlp-collector-coverage-analysis | otlp,collector,diagnostics | import_diagnostics | `true` | 0 | 4 | `true` | 1.0 | 1.0 | 1.0 | 0.033 | 0.0 | 3.0 |
| temporal-logic-properties-fail | none | runtime | `true` | 8 | 5 | `false` | 1.0 | 1.0 | 1.0 | 0.549 | 625.0 | 0.0 |
| benchmark-missing-correlation | correlation,diagnosability,runtime | runtime | `true` | 3 | 2 | `false` | 1.0 | 1.0 | 1.0 | 0.454 | 666.666667 | 0.0 |
| benchmark-cardinality-budget | cardinality,operability,runtime | runtime | `true` | 2 | 1 | `true` | 1.0 | 1.0 | 1.0 | 0.371 | 500.0 | 0.0 |
| benchmark-privacy-static-source | privacy,security,static,runtime | runtime,static | `true` | 1 | 6 | `false` | 1.0 | 1.0 | 1.0 | 0.998 | 6000.0 | 0.0 |
| benchmark-partial-otlp-diagnostics | otlp,import,diagnostics | import_diagnostics | `true` | 0 | 1 | `true` | 1.0 | 1.0 | 1.0 | 0.01 | 0.0 | 0.333333 |
| benchmark-unsafe-transformations-and-payload-preview | privacy,security,runtime,static,transformation,payload-preview | runtime,static | `true` | 1 | 15 | `false` | 1.0 | 1.0 | 1.0 | 1.198 | 15000.0 | 0.0 |
| synthetic-microservices-checkout-pass | microservices,correlation,scenario,runtime | runtime | `true` | 30 | 0 | `true` | n/a | n/a | n/a | 6.427 | 0.0 | 0.0 |
| reconstructed-incident-blind-spots | incident-readiness,reconstruction,runtime | runtime | `true` | 7 | 15 | `false` | 1.0 | 1.0 | 1.0 | 1.774 | 2142.857143 | 0.0 |

## Top remediations

| Severity | Semantic property | Owner | Effort | Benefit | Findings | Remediation |
| --- | --- | --- | --- | --- | ---: | --- |
| error | diagnosability | contract service owner | medium | restores incident question evidence | 17 | Attach the required attribute/tag/field to the signal. |
| error | privacy-security | contract service owner | medium | reduces sensitive telemetry exposure | 5 | Do not emit raw PII, credentials, or bearer tokens in telemetry. |
| error | schema | contract service owner | medium | improves benchmark semantic coverage | 4 | Normalize the field to one of the declared allowed values. |
| warning | diagnosability | contract service owner | small-to-medium | restores incident question evidence | 2 | Include a trace_id, request_id, or configured correlation field in error logs. |
| warning | input | contract service owner | small-to-medium | bounds importer claim validity | 2 | Inspect collector/exporter dropped-count fields before relying on complete contract evidence. |
| warning | operability | contract service owner | small-to-medium | reduces noisy or costly telemetry | 1 | Bucket, hash, drop, or bound labels with excessive cardinality. |
| warning | privacy-security | contract service owner | medium | reduces sensitive telemetry exposure | 1 | Replace raw payload/body previews with allowlisted sanitized previews or omit them. |
| info | input | contract service owner | small-to-medium | bounds importer claim validity | 1 | Document unsupported top-level OTLP fields as validity threats or add bounded importer support. |
