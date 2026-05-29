# Benchmark: built-in telemetry contracts benchmark

- Pass: `true`
- Contracts: 5
- Events: 24
- Findings: 22
- Runtime: 10.095 ms
- Findings by code: `{"scenario.missing_field": 3, "static.secret_logging": 2, "telemetry.allowed_values": 4, "telemetry.hyper_pii_disclosure": 3, "telemetry.missing_field": 3, "telemetry.numeric_max": 2, "telemetry.temporal_absence": 1, "telemetry.temporal_deadline": 1, "telemetry.temporal_order": 1, "telemetry.temporal_response": 1, "telemetry.temporal_safety": 1}`
- Findings by severity: `{"error": 22}`

| Case | Checks | Pass | Events | Findings | Validation pass | Label precision | Label recall | Runtime ms |
| --- | --- | --- | ---: | ---: | --- | ---: | ---: | ---: |
| checkout-payment-timeout-pass | runtime,scenario | `true` | 5 | 0 | `true` | n/a | n/a | 1.484 |
| gitlab-2017-database-outage-reconstructed | runtime,scenario | `true` | 5 | 12 | `false` | 1.0 | 1.0 | 1.577 |
| owasp-securetea-signin-current-static-and-hyperproperty | runtime,static | `true` | 3 | 5 | `false` | 1.0 | 1.0 | 2.02 |
| otlp-collector-mixed-signals-pass | runtime | `true` | 3 | 0 | `true` | n/a | n/a | 0.788 |
| temporal-logic-properties-fail | runtime | `true` | 8 | 5 | `false` | 1.0 | 1.0 | 0.831 |

