# Benchmark: built-in telemetry contracts benchmark

- Pass: `true`
- Contracts: 3
- Events: 10
- Findings: 14
- Runtime: 3.624 ms
- Findings by code: `{"scenario.missing_field": 3, "static.secret_logging": 2, "telemetry.allowed_values": 4, "telemetry.missing_field": 3, "telemetry.numeric_max": 2}`
- Findings by severity: `{"error": 14}`

| Case | Checks | Pass | Events | Findings | Validation pass | Label precision | Label recall | Runtime ms |
| --- | --- | --- | ---: | ---: | --- | ---: | ---: | ---: |
| checkout-payment-timeout-pass | runtime,scenario | `true` | 5 | 0 | `true` | n/a | n/a | 1.016 |
| gitlab-2017-database-outage-reconstructed | runtime,scenario | `true` | 5 | 12 | `false` | 1.0 | 1.0 | 0.843 |
| owasp-securetea-signin-current-static | static | `true` | 0 | 2 | `false` | 1.0 | 1.0 | 0.862 |

