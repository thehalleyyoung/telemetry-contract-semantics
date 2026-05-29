# Finding taxonomy

- Schema version: `1.0`
- Rules: 61
- Categories: `{"contract": 22, "diagnosability": 13, "input": 1, "operability": 3, "preservation": 3, "privacy-security": 6, "scenario": 2, "schema": 9, "static-coverage": 2}`
- Default severities: `{"error": 56, "warning": 5}`
- SARIF levels: `{"error": 56, "warning": 5}`

## Rule catalog

| Code | Category | Severity | Formal clause | SARIF | CI fail-on | Disclosure | Owner | Remediation |
| --- | --- | --- | --- | --- | --- | --- | --- | --- |
| contract.allowed_values_type | contract | error | WF.allowed-values | error | error | internal | contract service owner | Declare allowed_values as an array. |
| contract.conditional_requirement | contract | error | WF.conditional | error | error | internal | contract service owner | Declare conditional requirements with an if field condition and then fields list. |
| contract.duplicate_field | contract | error | WF.unique-field | error | error | internal | contract service owner | Declare each field name in only one of fields, attributes, or tags for a signal. |
| contract.duplicate_signal | contract | error | WF.unique-signal | error | error | internal | contract service owner | Keep one contract definition per signal name and kind. |
| contract.field_definitions | contract | error | WF.field-definitions | error | error | internal | contract service owner | Declare reusable field definitions as an object of field specs. |
| contract.field_ref | contract | error | WF.field-reference | error | error | internal | contract service owner | Reference an existing field definition or inline the field spec. |
| contract.field_ref_cycle | contract | error | WF.field-reference-acyclic | error | error | internal | contract service owner | Remove cyclic field-definition references. |
| contract.field_type | contract | error | WF.field-type | error | error | internal | contract service owner | Use one of string, integer, number, boolean, object, array, or null. |
| contract.forbidden_patterns_type | contract | error | WF.forbidden-pattern | error | error | internal | contract service owner | Declare forbidden_patterns as a string, object, or array of strings/objects. |
| contract.invalid_regex | contract | error | WF.regex | error | error | internal | contract service owner | Fix the regular expression in the contract. |
| contract.numeric_bound_type | contract | error | WF.numeric-bound | error | error | internal | contract service owner | Declare min and max bounds as numbers. |
| contract.numeric_bounds | contract | error | WF.numeric-interval | error | error | internal | contract service owner | Ensure min is less than or equal to max. |
| contract.policy_stub | contract | error | WF.policy-stub | error | error | internal | contract service owner | Declare sampling and retention policy stubs with machine-readable rates, strategies, and day counts. |
| contract.privacy_policy | privacy-security | error | WF.privacy-policy | error | error | responsible-disclosure | contract service owner | Declare a known privacy classification and an allowed transformation such as redacted, hashed, tokenized, bucketed, or omitted. |
| contract.required_type | contract | error | WF.required-boolean | error | error | internal | contract service owner | Use a boolean for required flags. |
| contract.schema | contract | error | WF.schema | error | error | internal | contract service owner | Update the contract so it conforms to docs/contract.schema.json. |
| contract.section_type | contract | error | WF.signal-section | error | error | internal | contract service owner | Use arrays for spans, metrics, and logs sections. |
| contract.sensitive_field_unclassified | schema | warning | WF.privacy-classification | warning | warning | internal | contract service owner | Classify sensitive fields with sensitivity and forbid raw-secret patterns. |
| contract.service | contract | error | WF.service | error | error | internal | contract service owner | Add a non-empty service name. |
| contract.severity_policy | contract | error | WF.severity-policy | error | error | internal | contract service owner | Use a known log severity threshold such as WARN, ERROR, or FATAL. |
| contract.signal_name | contract | error | WF.signal-name | error | error | internal | contract service owner | Give each signal a stable telemetry name. |
| contract.signal_type | contract | error | WF.signal-object | error | error | internal | contract service owner | Describe each signal as an object. |
| contract.temporal_sequence | contract | error | WF.temporal-sequence | error | error | internal | contract service owner | Declare temporal sequences with valid steps, kinds, group_by keys, and positive windows. |
| contract.unit | schema | error | WF.unit | error | error | internal | contract service owner | Use a supported unit such as ms, bytes, percent, count, timestamp_ms, or usd. |
| contract.version | contract | error | WF.version | error | error | internal | contract service owner | Declare contract version 1.0. |
| input.load_error | input | error | INPUT.parse | error | error | internal | contract service owner | Fix the referenced input path or file format. |
| preservation.contract_obligation | preservation | error | PRES.runtime-obligation | error | error | internal | contract service owner | Change or configure the transformation so transformed telemetry still satisfies obligations that held before transformation. |
| preservation.scenario_field | preservation | error | PRES.adequacy-field | error | error | internal | contract service owner | Keep the transformed field, or provide an approved surrogate that still answers the selected incident question. |
| preservation.scenario_signal | preservation | error | PRES.adequacy-signal | error | error | internal | contract service owner | Keep at least one transformed signal witness for each selected diagnosability requirement. |
| scenario.missing_field | diagnosability | error | ADEQ.required-field | error | error | internal | contract service owner | Emit the field needed to answer the scenario question. |
| scenario.missing_signal | diagnosability | error | ADEQ.required-signal | error | error | internal | contract service owner | Emit the signal needed to answer the scenario question. |
| scenario.not_found | scenario | error | SCENARIO.selection | error | error | internal | contract service owner | Add or select a scenario that matches the incident question. |
| scenario.requirement_type | scenario | error | SCENARIO.requirement-wf | error | error | internal | contract service owner | Describe scenario requirements as objects. |
| static.missing_correlation | diagnosability | error | STATIC.correlation-evidence | error | error | internal | contract service owner | Include a trace_id, request_id, or configured correlation field in error logs. |
| static.missing_instrumentation | static-coverage | error | STATIC.signal-literal | error | error | internal | contract service owner | Add source instrumentation with the expected stable telemetry name. |
| static.no_sources | static-coverage | error | STATIC.source-domain | error | error | internal | contract service owner | Pass source files or directories to the static checker. |
| static.secret_logging | privacy-security | error | STATIC.raw-sensitive-log | error | error | responsible-disclosure | contract service owner | Remove the sensitive value from logs or log only a redacted/hash surrogate. |
| static.unbounded_label | operability | warning | STATIC.cardinality-risk | warning | warning | internal | contract service owner | Avoid user-controlled/high-cardinality metric labels or add bucketing. |
| telemetry.allowed_values | schema | error | SAT.allowed-values | error | error | internal | contract service owner | Normalize the field to one of the declared allowed values. |
| telemetry.cardinality | operability | warning | SAT.cardinality-bound | warning | warning | internal | contract service owner | Bucket, hash, drop, or bound labels with excessive cardinality. |
| telemetry.cardinality_policy | operability | warning | SAT.cardinality-policy | warning | warning | internal | contract service owner | Declare a max cardinality or explicitly allow unbounded values. |
| telemetry.conditional_missing_field | diagnosability | error | SAT.conditional-obligation | error | error | internal | contract service owner | When the triggering field is present, emit all fields required by the conditional requirement. |
| telemetry.correlation_mismatch | diagnosability | error | SAT.correlation-intersection | error | error | internal | contract service owner | Propagate at least one shared correlation key value across the required signal kinds. |
| telemetry.correlation_missing | diagnosability | error | SAT.correlation-presence | error | error | internal | contract service owner | Emit a trace_id, span_id, request_id, or configured correlation key on correlated signals. |
| telemetry.field_type | schema | error | SAT.field-type | error | error | internal | contract service owner | Emit the field using the contract's declared primitive type. |
| telemetry.forbidden_pattern | privacy-security | error | SAT.forbidden-pattern | error | error | responsible-disclosure | contract service owner | Redact, hash, or omit values matching forbidden sensitive patterns. |
| telemetry.log_message | diagnosability | error | SAT.log-message | error | error | internal | contract service owner | Use a stable log message or event name matching the contract. |
| telemetry.log_severity | diagnosability | error | SAT.log-severity | error | error | internal | contract service owner | Emit the log at the severity required for alerting and search. |
| telemetry.log_severity_min | diagnosability | error | SAT.log-severity-threshold | error | error | internal | contract service owner | Raise the emitted log severity to meet the contract's minimum severity policy. |
| telemetry.missing_field | diagnosability | error | SAT.required-field | error | error | internal | contract service owner | Attach the required attribute/tag/field to the signal. |
| telemetry.missing_signal | diagnosability | error | SAT.required-signal | error | error | internal | contract service owner | Emit the required span, metric, or log on the exercised path. |
| telemetry.numeric_max | schema | error | SAT.numeric-upper-bound | error | error | internal | contract service owner | Investigate or clamp values above the declared maximum. |
| telemetry.numeric_min | schema | error | SAT.numeric-lower-bound | error | error | internal | contract service owner | Investigate or clamp values below the declared minimum. |
| telemetry.pattern | schema | error | SAT.regex | error | error | internal | contract service owner | Normalize the field so it matches the declared pattern. |
| telemetry.pattern_type | schema | error | SAT.regex-domain | error | error | internal | contract service owner | Emit a string value when a regex pattern is required. |
| telemetry.privacy_transformation | privacy-security | error | SAT.privacy-preservation | error | error | responsible-disclosure | contract service owner | Emit the field using the transformation required by the contract privacy policy. |
| telemetry.sensitive_unclassified | privacy-security | warning | SAT.sensitive-classification | warning | warning | responsible-disclosure | contract service owner | Classify the field sensitivity and redact or hash the emitted value. |
| telemetry.sensitive_value | privacy-security | error | SAT.raw-sensitive-value | error | error | responsible-disclosure | contract service owner | Do not emit raw PII, credentials, or bearer tokens in telemetry. |
| telemetry.temporal_missing_step | diagnosability | error | SAT.temporal-presence | error | error | internal | contract service owner | Emit every event required by the temporal sequence in the grouped incident window. |
| telemetry.temporal_window | diagnosability | error | SAT.temporal-window | error | error | internal | contract service owner | Emit the temporal sequence within the declared bounded window. |
| telemetry.unit | schema | error | SAT.unit | error | error | internal | contract service owner | Emit a value that satisfies the field's declared unit constraints. |

## Observed finding coverage

- Findings: 14
- Unknown codes: `[]`
- By code: `{"scenario.missing_field": 3, "static.secret_logging": 2, "telemetry.allowed_values": 4, "telemetry.missing_field": 3, "telemetry.numeric_max": 2}`
- By category: `{"diagnosability": 6, "privacy-security": 2, "schema": 6}`
- By formal clause: `{"ADEQ.required-field": 3, "SAT.allowed-values": 4, "SAT.numeric-upper-bound": 2, "SAT.required-field": 3, "STATIC.raw-sensitive-log": 2}`
- By SARIF level: `{"error": 14}`
- By service owner: `{"contract service owner": 14}`

| Source | Findings |
| --- | ---: |
| reports/current_impact.json | 14 |

| Code | Category | Formal clause | Severity | SARIF | Path |
| --- | --- | --- | --- | --- | --- |
| telemetry.allowed_values | schema | SAT.allowed-values | error | error | event[5].source |
| telemetry.numeric_max | schema | SAT.numeric-upper-bound | error | error | event[5].backup_age_hours |
| telemetry.allowed_values | schema | SAT.allowed-values | error | error | event[5].source_environment |
| telemetry.numeric_max | schema | SAT.numeric-upper-bound | error | error | event[1].value |
| telemetry.allowed_values | schema | SAT.allowed-values | error | error | event[3].value |
| telemetry.allowed_values | schema | SAT.allowed-values | error | error | event[2].target_role |
| telemetry.missing_field | diagnosability | SAT.required-field | error | error | event[2].correlation_id |
| telemetry.missing_field | diagnosability | SAT.required-field | error | error | event[2].command_guard_result |
| telemetry.missing_field | diagnosability | SAT.required-field | error | error | event[4].alert_delivered |
| scenario.missing_field | diagnosability | ADEQ.required-field | error | error | events[log=database.destructive_command].correlation_id |
| scenario.missing_field | diagnosability | ADEQ.required-field | error | error | events[log=database.destructive_command].command_guard_result |
| scenario.missing_field | diagnosability | ADEQ.required-field | error | error | events[log=backup.pg_dump.failed].alert_delivered |
| static.secret_logging | privacy-security | STATIC.raw-sensitive-log | error | error | case_studies/current/owasp_securetea_signin/Signin.js:27 |
| static.secret_logging | privacy-security | STATIC.raw-sensitive-log | error | error | case_studies/current/owasp_securetea_signin/Signin.js:48 |

