# Benchmark: built-in telemetry contracts benchmark

- Pass: `true`
- Cases: 15
- Contracts: 25
- Events: 72
- Findings: 74
- Runtime: 216.462 ms
- Runtime per K events: 3006.416667 ms
- Findings per K events: 1027.777778
- Import loss rate: 1.0
- Label precision/recall/F1: 1.0 / 1.0 / 1.0
- Findings by code: `{"otlp.dropped_evidence": 2, "otlp.malformed_record": 1, "otlp.unsupported_metric": 1, "otlp.unsupported_top_level": 1, "scenario.missing_field": 3, "static.missing_correlation": 3, "static.missing_error_status": 1, "static.missing_exception_recording": 1, "static.missing_remediation_field": 1, "static.pii_logging": 3, "static.secret_logging": 5, "static.unbounded_label": 2, "static.unsafe_payload_preview": 2, "telemetry.allowed_values": 4, "telemetry.cardinality": 1, "telemetry.correlation_missing": 2, "telemetry.forbidden_pattern": 2, "telemetry.hyper_pii_disclosure": 4, "telemetry.missing_field": 17, "telemetry.missing_signal": 1, "telemetry.numeric_max": 2, "telemetry.privacy_transformation": 5, "telemetry.sensitive_value": 5, "telemetry.temporal_absence": 1, "telemetry.temporal_deadline": 1, "telemetry.temporal_order": 1, "telemetry.temporal_response": 1, "telemetry.temporal_safety": 1}`
- Findings by severity: `{"error": 58, "info": 1, "warning": 15}`

| Case | Tags | Checks | Pass | Events | Findings | Validation pass | Label precision | Label recall | Label F1 | Runtime ms | Findings/K events | Import loss |
| --- | --- | --- | --- | ---: | ---: | --- | ---: | ---: | ---: | ---: | ---: | ---: |
| checkout-payment-timeout-pass | none | runtime,scenario | `true` | 5 | 0 | `true` | n/a | n/a | n/a | 4.827 | 0.0 | 0.0 |
| gitlab-2017-database-outage-reconstructed | none | runtime,scenario | `true` | 5 | 12 | `false` | 1.0 | 1.0 | 1.0 | 4.739 | 2400.0 | 0.0 |
| owasp-securetea-signin-current-static-and-hyperproperty | none | runtime,static | `true` | 3 | 6 | `false` | 1.0 | 1.0 | 1.0 | 9.157 | 2000.0 | 0.0 |
| otlp-collector-mixed-signals-pass | none | runtime | `true` | 3 | 0 | `true` | n/a | n/a | n/a | 2.001 | 0.0 | 0.0 |
| otlp-collector-coverage-analysis | otlp,collector,diagnostics | import_diagnostics | `true` | 0 | 4 | `true` | 1.0 | 1.0 | 1.0 | 0.068 | 0.0 | 3.0 |
| temporal-logic-properties-fail | none | runtime | `true` | 8 | 5 | `false` | 1.0 | 1.0 | 1.0 | 1.874 | 625.0 | 0.0 |
| benchmark-missing-correlation | correlation,diagnosability,runtime | runtime | `true` | 3 | 2 | `false` | 1.0 | 1.0 | 1.0 | 1.528 | 666.666667 | 0.0 |
| benchmark-cardinality-budget | cardinality,operability,runtime | runtime | `true` | 2 | 1 | `true` | 1.0 | 1.0 | 1.0 | 18.139 | 500.0 | 0.0 |
| benchmark-privacy-static-source | privacy,security,static,runtime | runtime,static | `true` | 1 | 6 | `false` | 1.0 | 1.0 | 1.0 | 39.49 | 6000.0 | 0.0 |
| benchmark-partial-otlp-diagnostics | otlp,import,diagnostics | import_diagnostics | `true` | 0 | 1 | `true` | 1.0 | 1.0 | 1.0 | 0.034 | 0.0 | 0.333333 |
| benchmark-unsafe-transformations-and-payload-preview | privacy,security,runtime,static,transformation,payload-preview | runtime,static | `true` | 1 | 15 | `false` | 1.0 | 1.0 | 1.0 | 4.013 | 15000.0 | 0.0 |
| path-sensitive-checkout-pass | path-sensitive,runtime,slo-debugging | runtime | `true` | 4 | 0 | `true` | n/a | n/a | n/a | 1.11 | 0.0 | 0.0 |
| current-public-static-patterns | public-code,static,privacy,operability | static | `true` | 0 | 7 | `false` | 1.0 | 1.0 | 1.0 | 2.828 | 0.0 | 0.0 |
| synthetic-microservices-checkout-pass | microservices,correlation,scenario,runtime | runtime | `true` | 30 | 0 | `true` | n/a | n/a | n/a | 43.066 | 0.0 | 0.0 |
| reconstructed-incident-blind-spots | incident-readiness,reconstruction,runtime | runtime | `true` | 7 | 15 | `false` | 1.0 | 1.0 | 1.0 | 3.843 | 2142.857143 | 0.0 |

## Top remediations

| Severity | Semantic property | Owner | Effort | Benefit | Findings | Remediation |
| --- | --- | --- | --- | --- | ---: | --- |
| error | diagnosability | contract service owner | medium | restores incident question evidence | 17 | Attach the required attribute/tag/field to the signal. |
| error | privacy-security | contract service owner | medium | reduces sensitive telemetry exposure | 5 | Remove the sensitive value from logs or log only a redacted/hash surrogate. |
| error | schema | contract service owner | medium | improves benchmark semantic coverage | 4 | Normalize the field to one of the declared allowed values. |
| warning | diagnosability | contract service owner | small-to-medium | restores incident question evidence | 3 | Include a trace_id, request_id, or configured correlation field in error logs. |
| warning | input | contract service owner | small-to-medium | bounds importer claim validity | 2 | Inspect collector/exporter dropped-count fields before relying on complete contract evidence. |
| warning | operability | contract service owner | small-to-medium | reduces noisy or costly telemetry | 2 | Avoid user-controlled/high-cardinality metric labels or add bucketing. |
| warning | privacy-security | contract service owner | medium | reduces sensitive telemetry exposure | 2 | Replace raw payload/body previews with allowlisted sanitized previews or omit them. |
| info | input | contract service owner | small-to-medium | bounds importer claim validity | 1 | Document unsupported top-level OTLP fields as validity threats or add bounded importer support. |
